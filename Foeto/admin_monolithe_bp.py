"""FoetoPath — import des JSON exportés par les modules du Monolithe (Hub_HTML).

POST /admin/api/monolithe/import, un fichier par requête (champ « fichier »),
réservé aux rôles admin et admin_centre. Le JSON brut est gardé dans
module_data sous « monolithe_<module> », clichés écrits sur disque et base64
retiré. Ce que Luminarium sait lire est recopié dans ses propres modules :

  administratif       → fiche du cas, atcd_maternels, atcd_obstetricaux,
                        grossesse_en_cours, examens_prenataux
  biometrie_clinique  → macro_frais (terme, sexe, biometries)
  examen_clinique     → macro_frais.maceration (grade de Maroun)
  autopsie            → masses d'organes de macro_autopsie
  neuropath           → biometries de neuropath
  radio               → radio (même forme, squelette remonté d'un niveau)

  macro_placenta      → base PLACENTA (placenta.db), au format de la PWA
                        placenta : macro_frais + tranches_section, clichés
                        enregistrés dans placenta_photos

Le reste de l'examen clinique, de l'autopsie et de la neuropathologie
(constatations étape par étape) n'a pas d'équivalent champ à champ dans
Luminarium : il reste lisible dans monolithe_<module>.

Page /admin/monolithe : aperçu des fichiers (POST /api/monolithe/apercu),
confirmation, puis import un fichier à la fois avec progression.
"""

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, session

import db
import placenta_db as pdb
from auth_bp import role_required

admin_monolithe_bp = Blueprint("admin_monolithe", __name__)

MODULES = {"administratif", "examen_clinique", "biometrie_clinique", "radio",
           "autopsie", "neuropath", "macro_placenta", "micro"}
PLACENTA = {"macro_placenta"}   # le reste va dans la base fœtus
# Même règle que le Monolithe : le numéro devient un nom de répertoire.
NUMERO_OK = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _iso(d):
    """{annee, mois, jour} du Monolithe → 'AAAA-MM-JJ' (date incomplète → None)."""
    if isinstance(d, dict) and d.get("annee") and d.get("mois") and d.get("jour"):
        return f"{d['annee']:04d}-{d['mois']:02d}-{d['jour']:02d}"
    return None


def _oui(v):
    return v is True or str(v).strip().lower() in ("true", "oui", "1")


def _sans_vides(d):
    return {k: v for k, v in d.items() if v not in (None, "")}


def _fusionner(case_id, module, ajout):
    """Recopie les clés de `ajout` dans le module Luminarium sans écraser le reste."""
    data = db.get_module_data(case_id, module) or {}
    for k, v in ajout.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k].update(v)
        else:
            data[k] = v
    db.save_module_data(case_id, module, data)


def _champs(d):
    """Champs de toutes les étapes (autopsie, neuropath) indexés par id."""
    return {c["id"]: c for e in d.get("etapes") or [] for c in e.get("champs") or []
            if isinstance(c, dict) and "id" in c}


def _extraire_cliches(noeud, dossier_photos, prefixe, ecrits=None):
    """Écrit chaque cliché base64 sur disque et remplace le base64 par le nom du
    fichier. Retourne [(clé, chemin, libellé)]."""
    ecrits = [] if ecrits is None else ecrits
    if isinstance(noeud, list):
        for x in noeud:
            _extraire_cliches(x, dossier_photos, prefixe, ecrits)
        return ecrits
    if not isinstance(noeud, dict):
        return ecrits
    b64 = noeud.get("data_base64")
    if isinstance(b64, str) and b64:
        cle = re.sub(r"[^A-Za-z0-9._-]", "_", str(noeud.get("key") or f"cliche{len(ecrits) + 1}"))
        ext = ".png" if "png" in str(noeud.get("type")) else ".jpg"
        dossier_photos.mkdir(parents=True, exist_ok=True)
        chemin = dossier_photos / f"{prefixe}_{cle}{ext}"
        chemin.write_bytes(base64.b64decode(b64.split(",", 1)[-1]))
        noeud["data_base64"] = None
        noeud["fichier"] = chemin.name
        ecrits.append((cle, chemin, noeud.get("label") or ""))
    for v in noeud.values():
        if isinstance(v, (dict, list)):
            _extraire_cliches(v, dossier_photos, prefixe, ecrits)
    return ecrits


# ── Correspondances module par module ──────────────────────────────────────

def _fiche_cas(d):
    ide, cir, iss = d.get("identite") or {}, d.get("circuit") or {}, d.get("issue") or {}
    sa, j = iss.get("terme_sa"), iss.get("terme_j")
    return _sans_vides({
        "nom_mere": ide.get("nom_mere"), "prenom_mere": ide.get("prenom_mere"),
        "nom_naissance_mere": ide.get("nom_naiss"), "prenom_foetus": ide.get("prenom_foetus"),
        "ipp": ide.get("ipp"), "ipp_fetus": ide.get("ipp_fetus"), "ins": ide.get("ins"),
        "opposition": ide.get("opposition"), "case_id_externe": ide.get("id_ext"),
        "ddn_mere": _iso(ide.get("ddn_mere")),
        "sexe": iss.get("sexe"), "type_issue": iss.get("type_issue"),
        "terme_issue": f"{sa}+{j or 0}" if sa is not None else None,
        "indication_examen": iss.get("indication"),
        "service_demandeur": cir.get("service"), "ville_maternite": cir.get("ville_maternite"),
        "ddn_foetus": _iso(cir.get("date_naissance")), "date_deces": _iso(cir.get("date_deces")),
    })


def _administratif(case_id, d):
    am, ao = d.get("atcd_mat") or {}, d.get("atcd_obs") or {}
    gr, pn = d.get("grossesse") or {}, d.get("prenatal") or {}
    fdr = am.get("fdr") or {}
    _fusionner(case_id, "atcd_maternels", {
        "profession_mere": am.get("profession_mere"),
        "gestite": ao.get("gestite"), "parite": ao.get("parite"),
        "groupe_sanguin": am.get("groupe_sanguin"), "rhesus": am.get("rhesus"),
        "fdr_hta": bool(fdr.get("hta")), "fdr_diabete": bool(fdr.get("diabete")),
        "fdr_tabac": bool(fdr.get("tabac")), "fdr_alcool": bool(fdr.get("alcool")),
        "fdr_consanguinite": _oui(am.get("consanguinite")),
        "atcd_medicaux": am.get("atcd_medicaux"), "traitements": am.get("traitements"),
    })
    _fusionner(case_id, "grossesse_en_cours", {
        "mode_conception": gr.get("mode_conception"), "amp_type": gr.get("amp_type"),
        "ddg": _iso(gr.get("ddg")), "risque_t21": gr.get("risque_t21"),
        "bhcg": gr.get("bhcg"), "pappa": gr.get("pappa"), "lcc": gr.get("lcc"),
        "cn": gr.get("cn"), "lieu_suivi": gr.get("lieu_suivi"),
        "histoire_clinique": gr.get("histoire_clinique"),
    })
    _fusionner(case_id, "examens_prenataux", {
        **{f"echo_t{i}_status": pn.get(f"echo_t{i}") for i in (1, 2, 3)},
        **{f"echo_t{i}_details": pn.get(f"echo_t{i}_details") for i in (1, 2, 3)},
        "anomalies_suspectees": pn.get("autres_examens"),
    })
    lignes = [{"date": _iso(g.get("date_fin")), "issue": f.get("issue"),
               "terme_accouchement": f.get("terme"), "voie_accouchement": g.get("voie"),
               "sexe": f.get("sexe"), "percentile_audipog": f.get("percentile")}
              for g in ao.get("grossesses") or [] for f in g.get("foetus") or [{}]]
    if lignes:
        db.save_module_data(case_id, "atcd_obstetricaux", lignes)


def _biometrie_clinique(case_id, d):
    _fusionner(case_id, "macro_frais", _sans_vides({
        "type": "macro_frais", "etat": "Frais", "terme": d.get("terme"),
        "sexe": d.get("sexe"), "biometries": _sans_vides(d.get("mesures") or {}),
    }))


def _examen_clinique(case_id, d):
    ret = d.get("retention") or {}
    if ret.get("maroun") is None:
        return
    # Genest : le Monolithe donne un palier de durée, Luminarium des critères
    # cochés. Aucun critère n'est inventé : le palier va dans genest_palier.
    _fusionner(case_id, "macro_frais", {"type": "macro_frais", "etat": "Frais", "maceration": {
        "maroun_score": ret["maroun"],
        "genest_palier": ret.get("genest_libelle"), "genest_h": ret.get("genest_h")}})


# id de champ Monolithe → chemin dans macro_autopsie (pair : chemin des masses _d/_g)
_MASSES = {
    "thymus_masse": ("thorax", "thymus"), "coeur_masse": ("coeur",),
    "foie_masse": ("digestif", "foie"), "rate_masse": ("digestif", "rate"),
    "pancreas_masse": ("digestif", "pancreas"),
}
_MASSES_PAIRES = {
    "poumons_masse": ("poumons",), "reins_masse": ("retroperitoine", "reins"),
    "surrenales_masse": ("retroperitoine", "surrenales"),
}


def _poser(racine, chemin, valeurs):
    noeud = racine
    for k in chemin:
        noeud = noeud.setdefault(k, {})
    noeud.update(valeurs)


def _autopsie(case_id, d):
    ch, ajout = _champs(d), {}
    for cid, chemin in _MASSES.items():
        g = (ch.get(cid) or {}).get("grammes")
        if g is not None:
            _poser(ajout, chemin, {"masse": g})
    for cid, chemin in _MASSES_PAIRES.items():
        c = ch.get(cid) or {}
        _poser(ajout, chemin, _sans_vides({"masse_d": c.get("droite"), "masse_g": c.get("gauche")}))
    g = (ch.get("cerveau_masse") or {}).get("grammes")
    if g is not None:
        ajout["neuro"] = {"masse_cerveau": g}
    ajout = {k: v for k, v in ajout.items() if v}
    if ajout:
        _fusionner(case_id, "macro_autopsie", {"type": "macro_autopsie", **ajout})


_NEURO = {"masse_enc": "masse_encephale", "masse_cerv": "masse_cervelet",
          "DOFD": "DOFD", "DOFG": "DOFG", "DT": "DT", "DTC": "DTC", "CC": "CC"}


def _neuropath(case_id, d):
    ch = _champs(d)
    bio = _sans_vides({lumi: (ch.get(mono) or {}).get("valeur") for mono, lumi in _NEURO.items()})
    ajout = {"type": "neuropath", "sa": str(d.get("terme_sa") or "")}
    if bio:
        ajout["biometries"] = bio
    oeil = {f"oeil{n}": _sans_vides({k: (ch.get(f"oeil_{c}_{k}") or {}).get("valeur")
                                       for k in ("dt", "dap", "dc")})
            for n, c in ((1, "d"), (2, "g"))}
    if any(oeil.values()):
        ajout["oculaire"] = oeil
    _fusionner(case_id, "neuropath", ajout)


def _radio(case_id, d):
    ajout = {"type": "radio", **(d.get("squelette") or {})}
    for k in ("terme", "biometries", "scores_staturaux", "maturation_osseuse", "remarques"):
        if d.get(k) is not None:
            ajout[k] = d[k]
    ajout["hpo_codes"] = d.get("hpo") or []
    _fusionner(case_id, "radio", ajout)


RECOPIE = {"administratif": _administratif, "biometrie_clinique": _biometrie_clinique,
           "examen_clinique": _examen_clinique, "autopsie": _autopsie,
           "neuropath": _neuropath, "radio": _radio}


# ── Placenta : vers placenta.db, au format de la PWA placenta ──────────────

def _placenta_pwa(d, photos):
    """macro_placenta du Monolithe → (macro_frais, tranches_section) de la PWA.
    Les clés de champs et de clichés du Monolithe reprennent déjà celles de la PWA."""
    ch = {k: v for s in d.get("sections") or [] for k, v in (s.get("champs") or {}).items()}
    part = ch.get("cordon_particularites") or []
    commun = {"dossier": d["dossier"], "timestamp": d.get("exported_at")}
    macro = {**commun, "type": "macro_frais",
             "terme": {"sa": ch.get("terme_sa"), "jours": ch.get("terme_jours") or 0,
                       "source": ch.get("terme_source")},
             "foetus": {"masse_g": ch.get("masse_foetale"), "sexe": ch.get("sexe"),
                        "indication_terme": ch.get("indication"),
                        "indication_autre": ch.get("indication_detail")},
             "biometrie": {"grand_axe_cm": ch.get("grand_axe"), "petit_axe_cm": ch.get("petit_axe"),
                           "epaisseur_cm": ch.get("epaisseur"), "masse_paree_g": ch.get("masse")},
             "forme": ch.get("forme"), "completude": ch.get("completude") or [],
             "plaque_choriale": {"etats": ch.get("etat_choriale") or [],
                                 "remarques": ch.get("remarques_choriale")},
             "plaque_basale": {"etats": ch.get("etat_basale") or [],
                               "remarques": ch.get("remarques_basale")},
             "cordon": {"insertion": ch.get("cordon_insertion"),
                        "longueur_cm": ch.get("cordon_longueur"),
                        "spiralisation": ch.get("cordon_spiralisation"),
                        "palmure_amniotique": "Palmure amniotique" in part,
                        "striction": "Striction" in part, "particularites": part,
                        "remarques": ch.get("remarques_cordon")},
             "membranes": {"insertion": ch.get("membranes_insertion"),
                           "marginee_pct": ch.get("membranes_marginee_pct"),
                           "aspect": ch.get("membranes_aspect"),
                           "remarques": ch.get("remarques_membranes")}}
    tranches = {**commun, "type": "tranches_section",
                "vue_ensemble": {"photo_key": "tranches_vue_ensemble",
                                 "captured": "tranches_vue_ensemble" in photos},
                "tranche_groups": [{"group": t.get("groupe"),
                                    "photos": [{"key": k, "captured": k in photos}
                                               for k in t.get("photos") or []]}
                                   for t in d.get("tranches") or []],
                "lesions": [{**l, "photo_captured": l.get("photo_key") in photos}
                            for l in d.get("lesions") or []],
                "commentaire": ch.get("remarques_tranches")}
    return macro, tranches


def _importer_placenta(d, dossier, user):
    from placenta_bp import _data_root
    photos_dir = _data_root() / "Placentas" / dossier / "photos"
    ecrits = _extraire_cliches(d, photos_dir, dossier)   # {dossier}_{clé}, comme la PWA
    macro, tranches = _placenta_pwa(d, {cle for cle, _, _ in ecrits})
    existant = pdb.get_case_by_numero(dossier)
    if existant:   # le commentaire se saisit dans le hub : ne pas l'effacer
        for nom, mod in (("macro_frais", macro), ("tranches_section", tranches)):
            prev = pdb.get_module_data(existant["id"], nom) or {}
            if prev.get("commentaire") and not mod.get("commentaire"):
                mod["commentaire"] = prev["commentaire"]
    case_id = pdb.import_from_macro_frais_json(macro, user=user)
    pdb.save_module_data(case_id, "tranches_section", tranches, user=user)
    pdb.save_module_data(case_id, "monolithe_macro_placenta", d, user=user)
    for cle, chemin, libelle in ecrits:
        module = "tranches_section" if cle.startswith(("tr_", "lesion_", "tranches_")) else "macro_frais"
        pdb.save_photo(case_id, cle, chemin.name, label=libelle, module=module,
                       file_path=str(chemin), size_bytes=chemin.stat().st_size, user=user)
    if ecrits:
        pdb.update_case(case_id, {"dossier_photos_path": str(photos_dir)}, user=user)
    return case_id, existant is None, len(ecrits)


def _importer_foetus(d, dossier, module, user):
    fiche = _fiche_cas(d) if module == "administratif" else {}
    existant = db.get_case_by_numero(dossier)
    if existant:
        case_id = existant["id"]
        db.update_case(case_id, {**fiche, "modified_by": user})
    else:
        if module == "biometrie_clinique":
            t = d.get("terme") or {}
            fiche = _sans_vides({"sexe": d.get("sexe"),
                                 "terme_issue": f"{t['sa']}+{t.get('jours') or 0}" if t.get("sa") else None})
        case_id = db.create_case({**fiche, "numero_dossier": dossier,
                                  "created_by": user, "modified_by": user})

    data_root = db.get_setting("data_root")
    base = (Path(data_root) / "Foetus" / dossier if data_root
            else Path(existant["dossier_macro_path"]) if existant and existant.get("dossier_macro_path")
            else db.get_db_path().parent / "Foetus" / dossier)
    ecrits = _extraire_cliches(d, base / "photos", f"{dossier}_{module}")

    db.save_module_data(case_id, f"monolithe_{module}", d)
    if module in RECOPIE:
        RECOPIE[module](case_id, d)
    if ecrits:
        db.update_case(case_id, {"dossier_macro_path": str(base)})
    return case_id, existant is None, len(ecrits)


def _verifier(module, dossier):
    """Message d'erreur, ou None si le fichier est importable."""
    if module not in MODULES:
        return f"pas un export du Monolithe (module « {module} »)"
    if not NUMERO_OK.match(dossier):
        return f"numéro de dossier invalide « {dossier} »"
    return None


@admin_monolithe_bp.route("/monolithe")
@role_required("admin", "admin_centre")
def page_monolithe():
    return render_template("monolithe_import.html")


@admin_monolithe_bp.route("/api/monolithe/apercu", methods=["POST"])
@role_required("admin", "admin_centre")
def api_monolithe_apercu():
    """Pour chaque {dossier, module} : base visée, cas existant, import précédent."""
    sortie = []
    for f in (request.get_json(silent=True) or {}).get("fichiers") or []:
        module, dossier = f.get("module"), str(f.get("dossier") or "").strip().upper()
        ligne = {"dossier": dossier, "module": module, "erreur": _verifier(module, dossier)}
        if not ligne["erreur"]:
            placenta = module in PLACENTA
            base = pdb if placenta else db
            cas = base.get_case_by_numero(dossier)
            prec = base.get_module_data(cas["id"], f"monolithe_{module}") if cas else None
            ligne.update(base_cible="placenta" if placenta else "foetus",
                         cas_existant=bool(cas),
                         deja_importe=(prec or {}).get("exported_at") if prec else None)
        sortie.append(ligne)
    return jsonify({"fichiers": sortie})


@admin_monolithe_bp.route("/api/monolithe/import", methods=["POST"])
@role_required("admin", "admin_centre")
def api_monolithe_import():
    # Clichés pleine résolution en base64 : un export dépasse vite les 50 Mo globaux.
    # Levée ici seulement, après le contrôle du rôle (Flask >= 3.1).
    request.max_content_length = 150 * 1024 * 1024
    f = request.files.get("fichier")
    if not f:
        return jsonify({"error": "Aucun fichier"}), 400
    try:
        d = json.load(f.stream)
    except (ValueError, UnicodeDecodeError):
        return jsonify({"error": f"{f.filename} : JSON illisible"}), 400
    if not isinstance(d, dict):
        d = {}
    module, dossier = d.get("module"), str(d.get("dossier") or "").strip().upper()
    erreur = _verifier(module, dossier)
    if erreur:
        return jsonify({"error": f"{f.filename} : {erreur}"}), 400

    user = session.get("username", "")
    d["dossier"] = dossier
    d["_submitted_by"] = user
    d["_submitted_at"] = datetime.now(timezone.utc).isoformat()
    d["_submitted_via"] = "monolithe"
    if module in PLACENTA:
        case_id, cree, n = _importer_placenta(d, dossier, user)
    else:
        case_id, cree, n = _importer_foetus(d, dossier, module, user)
    return jsonify({"status": "ok", "dossier": dossier, "module": module,
                    "base": "placenta" if module in PLACENTA else "foetus",
                    "case_id": case_id, "cree": cree, "cliches": n,
                    "recopie": module in RECOPIE or module in PLACENTA})
