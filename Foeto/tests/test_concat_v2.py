#!/usr/bin/env python3
"""
Test unitaire pour concat (v2.1).

Vérifie que le JSON v2.1 produit à partir du cas de test "Remi" :
  - Contient 14 codes HPO dans hpo_summary
  - Schema foetopath_llm_export_v2.1
  - thorax_forme Normal présent dans radiologie
  - isthme hypoplasique converti en HPO dans gros_vaisseaux
  - tvi absent de examen_in_situ.thorax
  - ratio_masse_corporelle_pct pour organes fixés sans z-score
  - CHAOS alert quand LBWR élevé + atrésie laryngée
  - N'a aucune valeur null dans l'arbre entier

Usage : python test_concat_v2.py
"""

import json
import sys
import os

# Ajouter le dossier courant au path
sys.path.insert(0, os.path.dirname(__file__))

from concat import build_v2
from concat._utils import _prune


# ══════════════════════════════════════════════════════════════════════════
# Données de test (cas "Remi" simplifié)
# ══════════════════════════════════════════════════════════════════════════

CASE = {
    "id": 1,
    "numero_dossier": "Remi",
    "sexe": "M",
    "terme_issue": "34",
    "type_issue": None,
    "date_deces": None,
    "date_examen": None,
    "indication_examen": "Hypertrophie musculaire généralisée",
    "nom_mere": "MATHEVET",
    "medecin_referent": None,
    "service_demandeur": "gynecologie",
    "dossier_macro_path": None,
}

MODULES = {
    "atcd_maternels": {
        "profession_mere": None,
        "gestite": None,
        "parite": None,
        "fdr_hta": False,
        "fdr_diabete": False,
        "fdr_tabac": False,
        "fdr_alcool": False,
        "fdr_consanguinite": False,
    },
    "examens_prenataux": {
        "echo_t1_status": None,
        "anomalies_suspectees": None,
    },
    "grossesse_en_cours": {
        "mode_conception": None,
    },
    "macro_frais": {
        "dossier": "Remi",
        "timestamp": "2026-04-04T11:17:32.937Z",
        "type": "macro_frais",
        "terme": {"sa": 34, "jours": 0},
        "sexe": "M",
        "etat": "Frais",
        "maceration": {"maroun_score": 0, "genest": []},
        "biometries": {
            "masse": 450,
            "pied": 67,
            "vt": None, "vc": None, "pc": None,
            "bip": 82, "fo": 102,
            "dici": 18, "fpd": 18, "fpg": 18,
        },
        "morphologie": {
            "crane": {"status": None, "details": [], "text": None},
            "yeux": {"status": None, "details": [], "text": None},
            "oge": {"status": "anormal", "details": ["Ambigus"], "text": None},
        },
        "hpo": {"findings": [], "source": "pwa_macro"},
    },
    "macro_autopsie": {
        "dossier": "Remi",
        "timestamp": "2026-03-29T06:59:07.381Z",
        "type": "macro_autopsie",
        "sa_from_frais": 34,
        "ouverture": {
            "situs": None,
            "epanchements": {"pleural_d": 0, "pleural_g": 0, "peritoine": 0, "pericarde": 0},
            "ogi": None,
            "ogi_detail": "Cryptorchidie bilatérale, Ambiguïté génitale",
            "diaphragme": "Intègre",
        },
        "voies_aeriennes": {"detail": "Atrésie laryngée"},
        "thorax": {
            "thymus": {"masse": None, "aspect": None},
            "tvi": "Présent",
            "pericarde": ["Normal"],
            "tsa": {"etat": None, "detail": "Coarctation de l'aorte"},
        },
        "coeur": {"masse": 35, "gros_vx": None, "crosse": None,
                  "isthme": "Hypoplasique"},
        "poumons": {"morpho": [], "masse_d": 34, "masse_g": 23},
        "digestif": {
            "foie": {"masse": None},
            "rate": {"masse": None},
            "pancreas": {"masse": None},
        },
        "retroperitoine": {
            "surrenales": {"masse_d": 3, "masse_g": 3},
            "reins": {"masse_d": 4, "masse_g": 8},
        },
        "neuro": {"masse_cerveau": None, "detail": None},
        "hpo": {
            "findings": [
                {"code": "HP:0008750", "term": "Laryngeal atresia",
                 "source_field": "airway_detail", "source_value": "Atrésie laryngée"},
                {"code": "HP:0001680", "term": "Coarctation of aorta",
                 "source_field": "tsa_detail", "source_value": "Coarctation de l'aorte"},
            ],
            "source": "pwa_macro",
        },
    },
    "macro_fixe": {
        "dossier": "Remi",
        "type": "macro_fixe",
        "organes": {
            "thymus": {"masse_fixee": 34, "cassettes": "1", "lesion_desc": None},
            "coeur": {"masse_fixee": None, "cassettes": "2", "lesion_desc": None},
            "rein_d": {
                "masse_fixee": None, "cassettes": None,
                "lesion_desc": "Kystes — dysplasie multikystique, Gros reins bilatéraux",
            },
        },
        "hpo": {
            "findings": [
                {"code": "HP:0000003", "term": "Multicystic kidney dysplasia",
                 "source_field": "lesion_desc_rein_d",
                 "source_value": "Kystes — dysplasie multikystique"},
                {"code": "HP:0000105", "term": "Enlarged kidney",
                 "source_field": "lesion_desc_rein_d",
                 "source_value": "Gros reins bilatéraux"},
            ],
            "source": "pwa_macro",
        },
    },
    "neuropath": {
        "type": "neuropath",
        "sa": "34",
        "descriptions": {
            "meninges": {"status": "Normal"},
            "gyration": {"status": "Anormal"},
        },
        "biometries": {"masse_encephale": None},
        "zscores": {},
        "tranches_hd": [
            {"numero": 1, "constatations": ["Dilatation ventriculaire"]},
            {"numero": 2, "constatations": ["Heterotopie nodulaire", "Dilatation ventriculaire"]},
            {"numero": 3, "constatations": []},
        ],
        "tranches_hg": [],
        "hpo_codes": [
            {"code": "HP:0002536", "term": "Abnormal cortical gyration", "source": "Gyration"},
        ],
    },
    "radio": {
        "type": "imagerie_radio",
        "terme": {"sa": 34, "jours": 0},
        "cotes": {"droite": 12, "gauche": 11},
        "thorax_forme": "Normal",
        "vertebres": {"aspects": ["Hemivertebres"]},
        "aspect_os": {"aspects": ["Fractures", "Incurves"]},
        "biometries": {
            "bip_osseux_mm": 55,
            "pc_radio_mm": 230,
            "os_longs": {
                "Femur": {"droite": 67, "gauche": None, "moyenne": 67, "zscore_chitty": 0.7},
            },
        },
        "scores_staturaux": {"hadlock_sa": 27.6, "adalian_sa": 36},
        "hpo_codes": [
            {"code": "HP:0002937", "term": "Hemivertebrae", "source_value": "Hemivertebres"},
            {"code": "HP:0002757", "term": "Recurrent fractures", "source_value": "Fractures"},
            {"code": "HP:0006487", "term": "Bowed long bones", "source_value": "Incurves"},
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _check_no_null(obj, path=""):
    """Vérifie récursivement qu'aucune valeur n'est null."""
    errors = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v is None:
                errors.append(f"{path}.{k} is null")
            else:
                errors.extend(_check_no_null(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if item is None:
                errors.append(f"{path}[{i}] is null")
            else:
                errors.extend(_check_no_null(item, f"{path}[{i}]"))
    return errors


def _check_no_empty(obj, path=""):
    """Vérifie qu'il n'y a pas de chaînes vides, listes vides, ou dicts vides."""
    errors = []
    if isinstance(obj, dict):
        if not obj and path:
            errors.append(f"{path} is empty dict")
        for k, v in obj.items():
            if isinstance(v, str) and v.strip() == "":
                errors.append(f"{path}.{k} is empty string")
            else:
                errors.extend(_check_no_empty(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        if not obj and path:
            errors.append(f"{path} is empty list")
        for i, item in enumerate(obj):
            errors.extend(_check_no_empty(item, f"{path}[{i}]"))
    return errors


# ══════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════

def test_build_v2():
    result = build_v2(1, CASE, MODULES)

    passed = 0
    failed = 0
    total = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name} — {detail}")

    print("\n" + "=" * 60)
    print("TEST : concat.build_v2()")
    print("=" * 60)

    # 1. Structure de base
    print("\n── Structure ──")
    check("_meta présent", "_meta" in result)
    check("schema = foetopath_llm_export_v2.2",
          result.get("_meta", {}).get("schema") == "foetopath_llm_export_v2.2")
    check("version = 2.2.0",
          result.get("_meta", {}).get("version") == "2.2.0")

    # 2. Sections obligatoires
    print("\n── Sections narratives ──")
    expected_sections = ["identite", "examen_externe", "biometries_fraiches",
                         "radiologie", "ouverture_cavites", "examen_in_situ",
                         "organes_fixes", "ratios_diagnostiques",
                         "neuropathologie", "hpo_summary"]
    for s in expected_sections:
        check(f"Section '{s}' présente", s in result, f"manquante")

    # 3. Pas d'anciens noms de modules au premier niveau
    print("\n── Pas d'anciens noms ──")
    check("Pas de 'macro_autopsie' au 1er niveau",
          "macro_autopsie" not in result)
    check("Pas de 'macro_fixe' au 1er niveau",
          "macro_fixe" not in result)
    check("Pas de 'macro_frais' au 1er niveau",
          "macro_frais" not in result)
    check("Pas de 'modules' au 1er niveau",
          "modules" not in result)
    check("Pas de 'biometrics_zscores' au 1er niveau",
          "biometrics_zscores" not in result)

    # 4. HPO summary
    print("\n── HPO Summary ──")
    hpo_summary = result.get("hpo_summary", {})
    hpo_count = hpo_summary.get("total_count", 0)
    hpo_codes = [h["code"] for h in hpo_summary.get("codes", [])]
    # 13 codes uniques (HP:0008750 et HP:0008668 sont des variantes pour
    # Laryngeal atresia ; seul HP:0008750 apparaît car fourni par le PWA)
    check(f"≥ 13 codes HPO (trouvé: {hpo_count})", hpo_count >= 13,
          f"codes: {hpo_codes}")

    # HPO spécifiques attendus (14 codes)
    expected_hpo = [
        ("HP:0000062", "Ambiguous genitalia"),
        ("HP:0000028", "Cryptorchidism"),
        ("HP:0008668", "Laryngeal atresia"),
        ("HP:0001680", "Coarctation of aorta"),
        ("HP:0004387", "Hypoplastic aortic arch"),  # R7 : isthme hypoplasique
        ("HP:0002536", "Abnormal cortical gyration"),
        ("HP:0002937", "Hemivertebrae"),
        ("HP:0002757", "Recurrent fractures"),
        ("HP:0006487", "Bowed long bones"),
        ("HP:0002119", "Ventriculomegaly"),
        ("HP:0007165", "Periventricular nodular heterotopia"),
        ("HP:0000003", "Multicystic kidney dysplasia"),
        ("HP:0000105", "Enlarged kidney"),
    ]
    for code, label in expected_hpo:
        # Accepter aussi HP:0008750 comme variante pour laryngeal atresia
        present = code in hpo_codes
        if code == "HP:0008668" and not present:
            present = "HP:0008750" in hpo_codes  # PWA utilise HP:0008750
        check(f"HPO {code} ({label})", present,
              f"absent du summary. Codes présents: {hpo_codes}")

    # 5. Discordance staturale
    print("\n── Radiologie ──")
    scores = result.get("radiologie", {}).get("scores_staturaux", {})
    check("scores_staturaux.discordance présent",
          "discordance" in scores,
          f"clés: {list(scores.keys())}")
    if "discordance" in scores:
        check("Discordance mentionne Hadlock",
              "Hadlock" in scores["discordance"] or "hadlock" in scores["discordance"].lower())

    # 6. Asymétrie costale
    cotes = result.get("radiologie", {}).get("squelette_axial", {}).get("cotes", {})
    check("Asymétrie costale détectée", cotes.get("asymetrie") == True)

    # 7. Alertes
    print("\n── Alertes ──")
    alertes = result.get("alertes", [])
    check("Alertes présentes", len(alertes) > 0, "liste vide")
    check("Alerte masse -5.57 DS",
          any("masse" in a.lower() and "DS" in a for a in alertes))

    # 8. Aucune valeur null
    print("\n── Nettoyage (R1) ──")
    null_errors = _check_no_null(result)
    check(f"Aucune valeur null ({len(null_errors)} trouvées)",
          len(null_errors) == 0,
          "; ".join(null_errors[:5]))

    # 9. Identité
    print("\n── Identité ──")
    identite = result.get("identite", {})
    check("sexe = M", identite.get("sexe") == "M")
    check("terme_sa = 34", identite.get("terme_sa") == 34)
    check("indication_examen présente", "indication_examen" in identite)
    check("Pas d'ATCD maternels négatifs",
          "antecedents_maternels" not in identite,
          "devrait être absent car tous les FDR sont False")

    # 10. Examen externe
    print("\n── Examen externe ──")
    ext = result.get("examen_externe", {})
    oge = ext.get("organes_genitaux_externes", [])
    check(f"OGE findings ≥ 2 (trouvé: {len(oge)})", len(oge) >= 2,
          f"trouvé: {oge}")

    # 11. Neuropathologie
    print("\n── Neuropathologie ──")
    neuro = result.get("neuropathologie", {})
    coupes = neuro.get("coupes_hemispheres", {})
    hd = coupes.get("droit", [])
    check("Tranches HD non vides uniquement", len(hd) == 2,
          f"attendu 2 (T1+T2), trouvé {len(hd)}")
    check("Pas de tranches HG vides",
          "gauche" not in coupes,
          "devrait être absent car toutes vides")

    # 12. Ouverture
    print("\n── Ouverture ──")
    ouv = result.get("ouverture_cavites", {})
    check("aucun_epanchement = True",
          ouv.get("aucun_epanchement") == True)
    check("diaphragme = Intègre", ouv.get("diaphragme") == "Intègre")

    # 13. Biométries
    print("\n── Biométries ──")
    bio = result.get("biometries_fraiches", {})
    mesures = bio.get("mesures", [])
    check("Au moins 1 mesure avec z-score", len(mesures) >= 1)
    if mesures:
        m0 = mesures[0]
        check("Mesure masse a zscore = -5.57",
              m0.get("zscore") == -5.57,
              f"trouvé: {m0.get('zscore')}")
        check("Mesure a 'reference' inline",
              "reference" in m0)

    # 14. v2.1 : thorax_forme Normal conservé
    print("\n── v2.1 : thorax_forme ──")
    axial = result.get("radiologie", {}).get("squelette_axial", {})
    check("thorax_forme présent dans squelette_axial",
          "thorax_forme" in axial, f"clés: {list(axial.keys())}")
    check("thorax_forme = Normal",
          axial.get("thorax_forme") == "Normal")

    # 15. v2.1 : isthme absent de coeur_in_situ (R7 → déplacé dans gros_vaisseaux)
    print("\n── v2.1 : R7 isthme ──")
    thorax_is = result.get("examen_in_situ", {}).get("thorax", {})
    coeur_is = thorax_is.get("coeur_in_situ", {})
    check("isthme absent de coeur_in_situ",
          "isthme" not in coeur_is,
          f"clés coeur_in_situ: {list(coeur_is.keys())}")
    gv = thorax_is.get("gros_vaisseaux", [])
    has_isthme_hpo = any(
        f.get("hpo") == "HP:0004387" for f in gv if isinstance(f, dict)
    )
    check("HP:0004387 (Hypoplastic aortic arch) dans gros_vaisseaux",
          has_isthme_hpo, f"gros_vaisseaux: {gv}")

    # 16. v2.1 : tvi absent
    print("\n── v2.1 : tvi supprimé ──")
    check("tvi absent de examen_in_situ.thorax",
          "tvi" not in thorax_is,
          f"clés thorax: {list(thorax_is.keys())}")

    # 17. v2.1 : ratio masse corporelle pour thymus fixé
    print("\n── v2.1 : ratio thymus ──")
    organes = result.get("organes_fixes", {}).get("organes", [])
    thymus_entry = None
    for o in organes:
        if o.get("organe") == "thymus":
            thymus_entry = o
            break
    check("Thymus trouvé dans organes_fixes",
          thymus_entry is not None)
    if thymus_entry:
        check("Thymus a masse_fixee_g",
              "masse_fixee_g" in thymus_entry)
        check("Thymus a ratio_masse_corporelle_pct",
              "ratio_masse_corporelle_pct" in thymus_entry,
              f"clés thymus: {list(thymus_entry.keys())}")

    # 18. v2.1 : LBWR élevé / CHAOS
    print("\n── v2.1 : LBWR / CHAOS ──")
    poumons_entry = None
    for o in organes:
        if o.get("organe") == "poumons":
            poumons_entry = o
            break
    if poumons_entry:
        check("Poumons a lbwr", "lbwr" in poumons_entry,
              f"clés poumons: {list(poumons_entry.keys())}")
        lbwr_val = poumons_entry.get("lbwr", 0)
        check(f"LBWR > 0.035 (trouvé: {lbwr_val})", lbwr_val > 0.035)
        check("LBWR alerte CHAOS présente",
              poumons_entry.get("lbwr_alerte") and "CHAOS" in poumons_entry.get("lbwr_alerte", ""))
    check("Alerte CHAOS dans alertes globales",
          any("CHAOS" in a for a in alertes),
          f"alertes: {alertes}")

    # 19. v2.2 : Ratios diagnostiques
    print("\n── v2.2 : Ratios diagnostiques ──")
    ratios = result.get("ratios_diagnostiques", [])
    check("ratios_diagnostiques présent", len(ratios) > 0, "liste vide")

    # Indexer par nom de ratio pour les vérifications
    ratio_by_name = {}
    for r in ratios:
        ratio_by_name[r.get("ratio", "")] = r

    # Index céphalique: BIP 82 / FO 102 = 0.8039 → normal (0.74-0.83)
    ic = ratio_by_name.get("Index céphalique (BIP / FO)")
    check("Index céphalique calculé", ic is not None)
    if ic:
        check(f"IC = {ic['resultat']:.4f} (normal)", ic["interpretation"] == "normal")

    # DICI / FP: 18 / 18 = 1.0 → normal (0.85-1.15)
    dici_r = ratio_by_name.get("DICI / FP moyenne")
    check("DICI/FP calculé", dici_r is not None)
    if dici_r:
        check(f"DICI/FP = {dici_r['resultat']:.4f} (normal)", dici_r["interpretation"] == "normal")

    # Fémur / Pied: 67 / 67 = 1.0 → normal (0.85-1.10)
    fp = ratio_by_name.get("Fémur / Pied")
    check("Fémur/Pied calculé", fp is not None)
    if fp:
        check(f"Fémur/Pied = {fp['resultat']:.4f} (normal)", fp["interpretation"] == "normal")

    # LBWR: (34+23) / 450 = 0.1267 → anormal_haut (> 0.035)
    lbwr_r = ratio_by_name.get("LBWR (Poumons / Masse corporelle)")
    check("LBWR calculé dans ratios", lbwr_r is not None)
    if lbwr_r:
        check(f"LBWR = {lbwr_r['resultat']:.4f} (anormal_haut)",
              lbwr_r["interpretation"] == "anormal_haut")

    # Poumon D / G: 34 / 23 = 1.478 → normal (1.0-1.8)
    pdg = ratio_by_name.get("Poumon D / Poumon G")
    check("Poumon D/G calculé", pdg is not None)
    if pdg:
        check(f"Poumon D/G = {pdg['resultat']:.4f} (~1.48, normal)",
              pdg["interpretation"] == "normal")

    # Rein D / G: 4 / 8 = 0.5 → anormal_bas (< 0.7)
    rdg = ratio_by_name.get("Rein D / Rein G")
    check("Rein D/G calculé", rdg is not None)
    if rdg:
        check(f"Rein D/G = {rdg['resultat']:.4f} (anormal_bas)",
              rdg["interpretation"] == "anormal_bas")

    # Rein D / Surrénale D: 4 / 3 = 1.333 → anormal_bas (< 2.0)
    rsd = ratio_by_name.get("Rein D / Surrénale D")
    check("Rein D / Surrénale D calculé", rsd is not None)
    if rsd:
        check(f"Rein/Surr D = {rsd['resultat']:.4f} (anormal_bas)",
              rsd["interpretation"] == "anormal_bas")

    # Cœur / Masse: 35 / 450 = 0.0778 → anormal_haut (> 0.015)
    cm = ratio_by_name.get("Cœur / Masse corporelle")
    check("Cœur/Masse calculé", cm is not None)
    if cm:
        check(f"Cœur/Masse = {cm['resultat']:.4f} (anormal_haut)",
              cm["interpretation"] == "anormal_haut")
        check("Cœur/Masse a HPO cardiomégalie",
              cm.get("hpo") == "HP:0001640")

    # Thymus / Masse: 34 / 450 = 0.0756 → anormal_haut (> 0.010)
    tm = ratio_by_name.get("Thymus / Masse corporelle")
    check("Thymus/Masse calculé", tm is not None)
    if tm:
        check(f"Thymus/Masse = {tm['resultat']:.4f} (anormal_haut)",
              tm["interpretation"] == "anormal_haut")

    # Reins / Masse: (4+8) / 450 = 0.0267 → anormal_haut (> 0.015)
    rm = ratio_by_name.get("Reins (D+G) / Masse corporelle")
    check("Reins/Masse calculé", rm is not None)
    if rm:
        check(f"Reins/Masse = {rm['resultat']:.4f} (anormal_haut)",
              rm["interpretation"] == "anormal_haut")

    # 20. Vérifier que les ratios anormaux génèrent des alertes
    print("\n── v2.2 : Alertes ratios ──")
    check("Alerte Cœur/Masse dans alertes",
          any("Cœur" in a and "Masse" in a for a in alertes),
          f"alertes: {alertes}")
    check("Alerte Rein D/G dans alertes",
          any("Rein D" in a and "Rein G" in a for a in alertes),
          f"alertes: {alertes}")

    # 21. Structure du ratio (format attendu)
    print("\n── v2.2 : Structure ratio ──")
    if ratios:
        r0 = ratios[0]
        check("Ratio a 'ratio' (nom)", "ratio" in r0)
        check("Ratio a 'numerateur'", "numerateur" in r0)
        check("Ratio a 'denominateur'", "denominateur" in r0)
        check("Ratio a 'resultat'", "resultat" in r0)
        check("Ratio a 'interpretation'", "interpretation" in r0)
        check("Numérateur a 'parametre' et 'valeur'",
              "parametre" in r0.get("numerateur", {}) and "valeur" in r0.get("numerateur", {}))

    # ── Résumé ──
    print("\n" + "=" * 60)
    print(f"RÉSULTAT : {passed}/{total} tests passés", end="")
    if failed:
        print(f" ({failed} échoués)")
    else:
        print(" — TOUT OK ✓")
    print("=" * 60)

    # Exporter le JSON pour inspection
    output_path = os.path.join(os.path.dirname(__file__), "test_output_v2.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nJSON exporté → {output_path}")
    print(f"Taille : {len(json.dumps(result, ensure_ascii=False))} chars")

    return failed == 0


def test_build_v3():
    from concat import build_v3

    result = build_v3(1, CASE, MODULES)

    passed = 0
    failed = 0
    total = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name} — {detail}")

    print("\n" + "=" * 60)
    print("TEST : concat.build_v3()")
    print("=" * 60)

    # ── Structure v3 ──
    print("\n── Structure v3 ──")
    check("_meta présent", "_meta" in result)
    check("schema = foetopath_llm_export_v3",
          result.get("_meta", {}).get("schema") == "foetopath_llm_export_v3")
    check("version = 3.0.0",
          result.get("_meta", {}).get("version") == "3.0.0")
    check("brief présent", "brief" in result)
    check("dossier_complet présent", "dossier_complet" in result)

    brief = result.get("brief", {})
    dossier = result.get("dossier_complet", {})

    # ── Brief ──
    print("\n── Brief : identité ──")
    id_brief = brief.get("identite", {})
    check("sexe = M", id_brief.get("sexe") == "M")
    check("terme_sa = 34", id_brief.get("terme_sa") == 34)
    check("indication_examen présente", "indication_examen" in id_brief)
    check("etat_conservation présent", "etat_conservation" in id_brief)
    check("Pas de nom_mere dans brief", "nom_mere" not in id_brief)

    print("\n── Brief : alertes ──")
    alertes = brief.get("alertes", [])
    check("Alertes présentes", len(alertes) > 0)
    check("Alerte masse DS", any("masse" in a.lower() for a in alertes))

    print("\n── Brief : zscores_anormaux ──")
    zs = brief.get("zscores_anormaux", [])
    check("Au moins 2 zscores anormaux", len(zs) >= 2, f"trouvé: {len(zs)}")
    # Vérifier que seuls les |z| >= 2 sont inclus
    all_above_2 = all(abs(z.get("zscore", 0)) >= 2.0 for z in zs)
    check("Tous les zscores ont |z| >= 2", all_above_2)

    print("\n── Brief : ratios_anormaux ──")
    ra = brief.get("ratios_anormaux", [])
    check("Au moins 3 ratios anormaux", len(ra) >= 3, f"trouvé: {len(ra)}")
    # Vérifier structure
    if ra:
        check("Ratio a 'ratio'", "ratio" in ra[0])
        check("Ratio a 'resultat'", "resultat" in ra[0])
        check("Ratio a 'interpretation'", "interpretation" in ra[0])

    print("\n── Brief : hpo_summary ──")
    hpo = brief.get("hpo_summary", {})
    check("total_count >= 13", hpo.get("total_count", 0) >= 13)
    # Vérifier format compact (pas de source)
    codes = hpo.get("codes", [])
    if codes:
        check("HPO compact : code + label uniquement",
              "code" in codes[0] and "label" in codes[0] and "source" not in codes[0])

    print("\n── Brief : semiologie_litteraire ──")
    semio = brief.get("semiologie_litteraire", [])
    check("Au moins 3 phrases sémiologiques", len(semio) >= 3,
          f"trouvé: {len(semio)}: {semio}")

    # Vérifier les règles spécifiques
    check("Règle CHAOS présente",
          any("CHAOS" in s for s in semio), f"phrases: {semio}")
    check("Règle migration neuronale",
          any("migration" in s.lower() for s in semio))
    check("Règle axe génito-surrénalien",
          any("génito" in s.lower() or "surrénalien" in s.lower() for s in semio))

    print("\n── Brief : contradictions ──")
    contrad = brief.get("contradictions", [])
    check("Au moins 1 contradiction détectée", len(contrad) >= 1,
          f"trouvé: {len(contrad)}")
    if contrad:
        check("Contradiction a 'probleme'", "probleme" in contrad[0])
        check("Contradiction a 'reconciliation'", "reconciliation" in contrad[0])

    # ── Dossier complet ──
    print("\n── Dossier complet ──")
    check("_usage dans dossier", "_usage" in dossier)
    check("examen_externe dans dossier", "examen_externe" in dossier)
    check("biometries_fraiches dans dossier", "biometries_fraiches" in dossier)
    check("radiologie dans dossier", "radiologie" in dossier)
    check("ouverture_cavites dans dossier", "ouverture_cavites" in dossier)
    check("examen_in_situ dans dossier", "examen_in_situ" in dossier)
    check("organes_fixes dans dossier", "organes_fixes" in dossier)
    check("ratios_diagnostiques_complets dans dossier",
          "ratios_diagnostiques_complets" in dossier)
    check("neuropathologie dans dossier", "neuropathologie" in dossier)
    check("Pas de ratios_diagnostiques (renommé)", "ratios_diagnostiques" not in dossier)

    # Vérifier que le dossier n'a PAS de hpo_summary (c'est dans brief)
    check("Pas de hpo_summary dans dossier", "hpo_summary" not in dossier)
    check("Pas de alertes dans dossier", "alertes" not in dossier)

    # ── Résumé ──
    print("\n" + "=" * 60)
    print(f"RÉSULTAT : {passed}/{total} tests passés", end="")
    if failed:
        print(f" ({failed} échoués)")
    else:
        print(" — TOUT OK ✓")
    print("=" * 60)

    # Exporter le JSON v3 pour inspection
    output_path = os.path.join(os.path.dirname(__file__), "test_output_v3.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nJSON v3 exporté → {output_path}")
    print(f"Taille brief : {len(json.dumps(brief, ensure_ascii=False))} chars")
    print(f"Taille dossier_complet : {len(json.dumps(dossier, ensure_ascii=False))} chars")
    print(f"Taille totale : {len(json.dumps(result, ensure_ascii=False))} chars")

    return failed == 0


if __name__ == "__main__":
    ok_v2 = test_build_v2()
    ok_v3 = test_build_v3()
    sys.exit(0 if (ok_v2 and ok_v3) else 1)
