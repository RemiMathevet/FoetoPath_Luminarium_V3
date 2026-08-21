#!/usr/bin/env python3
"""
FoetoPath — Templates Jinja2 pour les comptes-rendus.

Templates disponibles :
  - soffoet    : CR type SOFFOET (basé sur le modèle officiel)
  - court      : CR synthétique court
  - neuropath  : CR neuropathologique
  - radio      : CR radiologique

Chaque template reçoit un contexte construit par build_cr_context()
à partir des données du cas (admin + modules + calculs).

Les templates Jinja2 sont stockés dans templates/cr/ en tant que fichiers .jinja2
"""

from cr_helpers import (
    get_available_templates as _get_templates,
    get_template_changelog as _get_changelog,
    get_all_versions_info as _get_versions,
    render_cr as _render,
)


# ══════════════════════════════════════════════════════════════════════════
# Construction du contexte pour les templates
# ══════════════════════════════════════════════════════════════════════════

def build_cr_context(case: dict, modules: dict, computed: dict = None) -> dict:
    """
    Construit le contexte unifié pour les templates Jinja2.

    Args:
        case: données admin du cas (table cases)
        modules: dict {module_name: data} (tous les modules)
        computed: résultats des calculs biométriques (computed_biometrics)

    Returns:
        Dict prêt à passer aux templates
    """
    macro_frais = modules.get("macro_frais", {})
    macro_autopsie = modules.get("macro_autopsie", {})
    atcd_mat = modules.get("atcd_maternels", {})
    atcd_obs_raw = modules.get("atcd_obstetricaux", {})
    atcd_obs = atcd_obs_raw if isinstance(atcd_obs_raw, list) else atcd_obs_raw.get("grossesses", [])
    gross = modules.get("grossesse_en_cours", {})
    exam_pren = modules.get("examens_prenataux", {})
    radio = modules.get("radio", {})
    histo = modules.get("histologie", {}) or modules.get("histo", {})

    bio = macro_frais.get("biometries", {})
    morpho = macro_frais.get("morphologie", {})
    terme = macro_frais.get("terme", {})

    # Calculs
    calc_bio = {}
    calc_org = {}
    calc_ind = {}
    calc_ratios = {}
    alertes = []
    if computed:
        results = computed.get("results", computed)
        calc_bio = results.get("biometries_gc", {}).get("mesures", {})
        calc_org = results.get("organes_gc", {}).get("organes", {})
        calc_ind = results.get("organes_individuels", {}).get("organes_pairs", {})
        calc_ratios = results.get("ratios", {})
        alertes = results.get("alertes", [])

    # Ouverture / autopsie
    ouverture = macro_autopsie.get("ouverture", {})
    voies_aeriennes = macro_autopsie.get("voies_aeriennes", {})
    thorax = macro_autopsie.get("thorax", {})
    coeur = macro_autopsie.get("coeur", {})
    poumons = macro_autopsie.get("poumons", {})
    digestif = macro_autopsie.get("digestif", {})
    retro = macro_autopsie.get("retroperitoine", {})
    neuro = macro_autopsie.get("neuro", {})
    prelevements = macro_autopsie.get("prelevements", {})
    macro_fixe = modules.get("macro_fixe", {})

    # ── Trophicité fœtale (basée sur DS du poids) ──
    trophicite = "non évaluable"
    masse_info = calc_bio.get("masse", {})
    if masse_info and masse_info.get("ds") is not None:
        ds_masse = masse_info["ds"]
        if ds_masse < -2:
            trophicite = "hypotrophe"
        elif ds_masse > 2:
            trophicite = "macrosome"
        else:
            trophicite = "eutrophe"

    # ── Agrégation de TOUTES les anomalies pour la conclusion ──
    all_anomalies = []

    # 1. Anomalies morphologiques externes (macro frais)
    for key, item in morpho.items():
        if isinstance(item, dict) and item.get("status") == "anormal":
            desc_parts = []
            if item.get("details"):
                desc_parts.extend(item["details"] if isinstance(item["details"], list) else [item["details"]])
            if item.get("text"):
                desc_parts.append(item["text"])
            label = key.replace("_", " ").capitalize()
            detail = ", ".join(desc_parts) if desc_parts else "anomalie non précisée"
            all_anomalies.append(f"{label} : {detail}")

    # 2. Alertes biométriques (organes hors normes)
    for a in alertes:
        all_anomalies.append(a)

    # 3. Anomalies internes (champs texte libres autopsie)
    if ouverture.get("ogi") and ouverture["ogi"].lower() not in ("normal", "normaux", "ras"):
        all_anomalies.append(f"OGI : {ouverture['ogi']}" + (f" — {ouverture['ogi_detail']}" if ouverture.get("ogi_detail") else ""))
    if voies_aeriennes.get("detail"):
        all_anomalies.append(f"Voies aériennes : {voies_aeriennes['detail']}")
    if thorax.get("tsa") and isinstance(thorax["tsa"], dict) and thorax["tsa"].get("etat") and thorax["tsa"]["etat"].lower() not in ("normaux", "normal", "ras"):
        all_anomalies.append(f"TSA : {thorax['tsa']['etat']}" + (f" — {thorax['tsa']['detail']}" if thorax["tsa"].get("detail") else ""))
    if coeur.get("og_retours"):
        all_anomalies.append(f"Retours veineux OG : {coeur['og_retours']}")
    if coeur.get("vg_ej") and isinstance(coeur["vg_ej"], dict) and coeur["vg_ej"].get("civ_diam"):
        all_anomalies.append(f"CIV : {coeur['vg_ej']['civ_diam']} mm")
    if coeur.get("vg_av") and isinstance(coeur["vg_av"], dict) and coeur["vg_av"].get("detail"):
        all_anomalies.append(f"Valve mitrale : {coeur['vg_av']['detail']}")
    if digestif.get("estomac") and isinstance(digestif["estomac"], dict) and digestif["estomac"].get("contenu"):
        all_anomalies.append(f"Contenu gastrique : {digestif['estomac']['contenu']}")
    if digestif.get("tube_dig") and isinstance(digestif["tube_dig"], dict) and digestif["tube_dig"].get("detail"):
        all_anomalies.append(f"Tube digestif : {digestif['tube_dig']['detail']}")
    if neuro.get("detail"):
        all_anomalies.append(f"Neuro : {neuro['detail']}")

    # 4. Lésions macro fixé
    fixe_organes = macro_fixe.get("organes", {})
    for org_id, org in fixe_organes.items():
        if isinstance(org, dict) and org.get("lesion_desc"):
            label = org_id.replace("_", " ").capitalize()
            all_anomalies.append(f"{label} (fixé) : {org['lesion_desc']}")

    # 5. Anomalies prénatales
    if exam_pren.get("anomalies_suspectees"):
        all_anomalies.append(f"Prénatal (suspectées) : {exam_pren['anomalies_suspectees']}")
    if exam_pren.get("anomalies_confirmees"):
        all_anomalies.append(f"Prénatal (confirmées) : {exam_pren['anomalies_confirmees']}")

    # ── Date/heure autopsie depuis EXIF photo avant ouverture ──
    date_autopsie_exif = None
    macro_path = case.get("dossier_macro_path")
    dossier = case.get("numero_dossier")
    if macro_path and dossier:
        from utils.file_ops import find_photo_avant_ouverture, extract_exif_datetime
        photo = find_photo_avant_ouverture(macro_path, dossier)
        if photo:
            date_autopsie_exif = extract_exif_datetime(photo)

    return {
        # Admin
        "case": case,
        "numero": case.get("numero_dossier", ""),
        "nom_mere": case.get("nom_mere", ""),
        "prenom_mere": case.get("prenom_mere", ""),
        "ddn_mere": case.get("ddn_mere", ""),
        "sexe": case.get("sexe") or macro_frais.get("sexe", ""),
        "type_issue": case.get("type_issue", ""),
        "terme_sa": terme.get("sa") if isinstance(terme, dict) else terme,
        "terme_j": terme.get("jours", 0) if isinstance(terme, dict) else 0,
        "date_deces": case.get("date_deces", ""),
        "date_examen": case.get("date_examen", ""),
        "date_autopsie_exif": date_autopsie_exif,
        "indication": case.get("indication_examen", ""),
        "medecin": case.get("medecin_referent", ""),
        "service": case.get("service_demandeur", ""),

        # ATCD
        "atcd_mat": atcd_mat,
        "atcd_obs": atcd_obs,
        "grossesse": gross,
        "exam_prenataux": exam_pren,

        # Macro frais
        "etat": macro_frais.get("etat", ""),
        "maceration": macro_frais.get("maceration", {}),
        "bio": bio,
        "morpho": morpho,
        "commentaire_frais": macro_frais.get("commentaire", ""),
        "anomalies_frais": macro_frais.get("anomalies", []),

        # Calculs biométriques
        "calc_bio": calc_bio,
        "calc_org": calc_org,
        "calc_ind": calc_ind,
        "calc_ratios": calc_ratios,
        "alertes": alertes,
        "lbwr": calc_ratios.get("_lbwr", {}),
        "trophicite": trophicite,
        "all_anomalies": all_anomalies,

        # Autopsie
        "ouverture": ouverture,
        "voies_aeriennes": voies_aeriennes,
        "thorax": thorax,
        "coeur": coeur,
        "poumons": poumons,
        "digestif": digestif,
        "retroperitoine": retro,
        "neuro": neuro,
        "prelevements": prelevements,
        "commentaire_autopsie": macro_autopsie.get("commentaire", ""),
        "macro_fixe": macro_fixe,

        # Photos
        "photos_frais": macro_frais.get("photos", []),
        "photos_autopsie": macro_autopsie.get("photos", []),

        # Radiologie
        "radio": radio,
        "rad_terme_sa": radio.get("terme", {}).get("sa") if isinstance(radio.get("terme"), dict) else radio.get("terme"),
        "rad_aspect_general": radio.get("aspect_general", ""),
        "rad_cotes": radio.get("cotes", {}),
        "rad_thorax_forme": radio.get("thorax_forme", ""),
        "rad_vertebres": radio.get("vertebres", {}),
        "rad_aspect_os": radio.get("aspect_os", {}),
        "rad_biometries": radio.get("biometries", {}),
        "rad_os_longs": radio.get("biometries", {}).get("os_longs", {}),
        "rad_scores": radio.get("scores_staturaux", {}),
        "rad_maturation": radio.get("maturation_osseuse", []),
        "rad_remarques": radio.get("remarques", ""),
        "rad_hpo_codes": radio.get("hpo_codes", []),

        # Histologie (stub)
        "histo": histo,
        "histo_organes": histo.get("organes", []),
        "histo_lesions": histo.get("lesions", []),
    }


# ══════════════════════════════════════════════════════════════════════════
# Helpers Jinja2
# ══════════════════════════════════════════════════════════════════════════

def _ds_text(calc_dict, key):
    """Formatte un résultat DS : 'valeur unité (±X.XX DS)'"""
    if not calc_dict or key not in calc_dict:
        return "#"
    m = calc_dict[key]
    return f"{m['valeur']:.1f} {m.get('unite', 'g')} ({m['ds']:+.2f} DS)"


def _morpho_text(morpho, key):
    """Extrait le texte d'un item morpho : normal ou description."""
    item = morpho.get(key, {})
    if not isinstance(item, dict):
        return str(item) if item else "pas de particularité"
    if item.get("status") == "normal":
        return "pas de particularité"
    parts = []
    if item.get("details"):
        parts.extend(item["details"] if isinstance(item["details"], list) else [item["details"]])
    if item.get("text"):
        parts.append(item["text"])
    return ", ".join(parts) if parts else "anomalie non précisée"


def _age_mere(ddn_mere, date_accouchement):
    """Calcule l'âge de la mère à l'accouchement en années."""
    if not ddn_mere or not date_accouchement:
        return ""
    from datetime import date
    def _parse(s):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return date.fromisoformat(s) if fmt == "%Y-%m-%d" else date(int(s[6:]), int(s[3:5]), int(s[:2]))
            except Exception:
                continue
        return None
    d1 = _parse(str(ddn_mere))
    d2 = _parse(str(date_accouchement))
    if not d1 or not d2:
        return ""
    age = d2.year - d1.year - ((d2.month, d2.day) < (d1.month, d1.day))
    return f"{age} ans"


_ISSUE_LABELS = {
    "NAISSANCE_VIVANTE": "Naissance vivante",
    "IMG": "IMG", "FCS": "FCS", "MFIU": "MFIU",
    "MPN": "Mort per-natale", "MNN": "Mort néonatale",
    "GEU": "GEU", "ISG": "ISG",
}

_BIO_LABELS = {
    "masse": "Masse corporelle", "VT": "Vertex-talon", "VC": "Vertex-coccyx",
    "PC": "Périmètre crânien", "pied": "Pied",
}
_ORGAN_LABELS = {
    "coeur": "Cœur", "thymus": "Thymus",
    "poumons": "Poumons (D+G)", "poumon_d": "Poumon D", "poumon_g": "Poumon G",
    "foie": "Foie", "rate": "Rate", "pancreas": "Pancréas",
    "surrenales": "Surrénales (D+G)", "surrenale_d": "Surrénale D", "surrenale_g": "Surrénale G",
    "reins": "Reins (D+G)", "rein_d": "Rein D", "rein_g": "Rein G",
    "cerveau": "Cerveau",
}


def _bio_row(label, m):
    v = f"{m['valeur']:.1f} {m.get('unite', 'g')}"
    moy = f"{m['moyenne']:.1f}" if m.get("moyenne") is not None else ""
    ds = f"{m['ds']:+.2f}" if m.get("ds") is not None else ""
    return f"<tr><td>{label}</td><td>{v}</td><td>{moy}</td><td>{ds}</td></tr>\n"


_BIO_TABLE_STYLE = "border-collapse:collapse;font-size:12px;margin:6px 0"
_BIO_HDR = "<tr><th>Mesure</th><th>Valeur</th><th>Moyenne</th><th>DS</th></tr>"


def _table_bio_ext(calc_bio):
    """Biométries examen externe (masse, VT, VC, PC, pied) — Guihard-Costa."""
    if not calc_bio:
        return ""
    rows = ""
    for key in ("masse", "VT", "VC", "PC", "pied"):
        if key in calc_bio and isinstance(calc_bio[key], dict):
            rows += _bio_row(_BIO_LABELS.get(key, key), calc_bio[key])
    if not rows:
        return ""
    return f"<table border='1' cellpadding='4' cellspacing='0' style='{_BIO_TABLE_STYLE}'>\n{_BIO_HDR}\n{rows}</table>"


def _table_bio_int(calc_org):
    """Masses d'organes examen interne — Guihard-Costa."""
    if not calc_org:
        return ""
    rows = ""
    for key in ("cerveau", "coeur", "thymus", "poumons", "poumon_d", "poumon_g",
                 "foie", "rate", "pancreas", "surrenales", "surrenale_d", "surrenale_g",
                 "reins", "rein_d", "rein_g"):
        if key in calc_org and isinstance(calc_org[key], dict):
            rows += _bio_row(_ORGAN_LABELS.get(key, key), calc_org[key])
    if not rows:
        return ""
    return f"<table border='1' cellpadding='4' cellspacing='0' style='{_BIO_TABLE_STYLE}'>\n{_BIO_HDR}\n{rows}</table>"


def _table_biometries(calc_bio, calc_org):
    """Tableau combiné biométries + organes (rétrocompatibilité)."""
    parts = []
    ext = _table_bio_ext(calc_bio)
    if ext:
        parts.append(ext)
    interne = _table_bio_int(calc_org)
    if interne:
        parts.append(interne)
    return "\n".join(parts)


def _table_atcd_obs(atcd_obs):
    """Rend la liste des ATCD obstétricaux en tableau HTML."""
    if not atcd_obs:
        return ""
    hdr = "<tr><th>Date</th><th>Issue</th><th>Terme</th><th>Voie</th><th>Sexe</th><th>Percentile</th><th>Remarques</th></tr>"
    rows = ""
    for g in atcd_obs:
        if not isinstance(g, dict):
            continue
        issue = _ISSUE_LABELS.get(g.get("issue", ""), g.get("issue", ""))
        sexe = {"M": "M", "F": "F", "I": "Ind."}.get(g.get("sexe", ""), g.get("sexe", ""))
        perc = g.get("percentile_audipog", "")
        terme = g.get("terme_accouchement", "")
        if terme:
            terme = f"{terme} SA"
        rows += (f"<tr><td>{g.get('date', '')}</td><td>{issue}</td>"
                 f"<td>{terme}</td><td>{g.get('voie_accouchement', '')}</td>"
                 f"<td>{sexe}</td><td>{perc}</td>"
                 f"<td>{g.get('remarques', '')}</td></tr>\n")
    return f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;font-size:12px'>\n{hdr}\n{rows}</table>"


def _table_os_longs(os_longs):
    """Tableau HTML des os longs avec z-scores Chitty."""
    if not os_longs:
        return ""
    hdr = "<tr><th>Os</th><th>D (mm)</th><th>G (mm)</th><th>Moyenne</th><th>Z-score</th></tr>"
    rows = ""
    for name, bone in os_longs.items():
        if not isinstance(bone, dict):
            continue
        d = bone.get("droite", "—")
        g = bone.get("gauche", "—")
        moy = bone.get("moyenne")
        z = bone.get("zscore_chitty")
        moy_s = f"{moy}" if moy is not None else "—"
        z_s = f"{z:+.2f}" if z is not None else "—"
        rows += f"<tr><td>{name}</td><td>{d}</td><td>{g}</td><td>{moy_s}</td><td>{z_s}</td></tr>\n"
    if not rows:
        return ""
    return f"<table border='1' cellpadding='4' cellspacing='0' style='{_BIO_TABLE_STYLE}'>\n{hdr}\n{rows}</table>"


def _table_maturation(maturation):
    """Tableau HTML des points de maturation osseuse."""
    if not maturation:
        return ""
    hdr = "<tr><th>SA</th><th>Point</th><th>Statut</th></tr>"
    rows = ""
    for m in maturation:
        if not isinstance(m, dict):
            continue
        status = m.get("status", "?")
        icon = "+" if status == "present" else "-"
        rows += f"<tr><td>{m.get('sa', '?')}</td><td>{m.get('label', '?')}</td><td>{icon} {status}</td></tr>\n"
    if not rows:
        return ""
    return f"<table border='1' cellpadding='4' cellspacing='0' style='{_BIO_TABLE_STYLE}'>\n{hdr}\n{rows}</table>"


# ══════════════════════════════════════════════════════════════════════════
# Genest — critères de rétention in utero
# ══════════════════════════════════════════════════════════════════════════

_GENEST_ITEMS = [
    (0, "Toute desquamation", "≥ 3h"),
    (1, "Desquamation ≥ 1 cm", "≥ 6h"),
    (2, "Décoloration cordon (brun/rouge)", "≥ 6h"),
    (3, "Desquamation face, dos ou abdomen", "≥ 12h"),
    (4, "Desquamation ≥ 5% surface", "≥ 18h"),
    (5, "Desquamation ≥ 2 zones / 11", "≥ 18h"),
    (6, "Coloration cutanée brune/ocre", "≥ 24h"),
    (7, "Desquamation modérée ou sévère", "≥ 24h"),
    (8, "Compression crânienne", "≥ 36h"),
    (9, "Desquamation > 10% surface", "≥ 48h"),
    (10, "Desquamation > 75% surface", "≥ 72h"),
    (11, "Bouche largement ouverte", "≥ 1 sem."),
    (12, "Momification", "≥ 2 sem."),
    (13, "Coloration cutanée ocre", "≥ 4 sem."),
]
_GENEST_BY_ID = {g[0]: g for g in _GENEST_ITEMS}
_TIME_ORDER = ["≥ 3h", "≥ 6h", "≥ 12h", "≥ 18h", "≥ 24h",
               "≥ 36h", "≥ 48h", "≥ 72h", "≥ 1 sem.", "≥ 2 sem.", "≥ 4 sem."]


def _table_genest(maceration):
    """Tableau HTML des critères Genest cochés + estimation rétention."""
    indices = maceration.get("genest", [])
    if not indices:
        return ""
    hdr = "<tr><th>Critère</th><th>Délai minimum</th></tr>"
    rows = ""
    max_time_idx = -1
    for idx in sorted(indices):
        g = _GENEST_BY_ID.get(idx)
        if not g:
            continue
        rows += f"<tr><td>{g[1]}</td><td>{g[2]}</td></tr>\n"
        ti = _TIME_ORDER.index(g[2]) if g[2] in _TIME_ORDER else -1
        if ti > max_time_idx:
            max_time_idx = ti
    if not rows:
        return ""
    estimation = _TIME_ORDER[max_time_idx] if max_time_idx >= 0 else "?"
    return (f"<table border='1' cellpadding='4' cellspacing='0' style='{_BIO_TABLE_STYLE}'>\n"
            f"{hdr}\n{rows}</table>\n"
            f"<div><b>Estimation de rétention : {estimation}</b></div>")


def _genest_retention(maceration):
    """Retourne l'estimation max de rétention sous forme de texte."""
    indices = maceration.get("genest", [])
    if not indices:
        return ""
    max_time_idx = -1
    for idx in indices:
        g = _GENEST_BY_ID.get(idx)
        if g and g[2] in _TIME_ORDER:
            ti = _TIME_ORDER.index(g[2])
            if ti > max_time_idx:
                max_time_idx = ti
    return _TIME_ORDER[max_time_idx] if max_time_idx >= 0 else ""


# ══════════════════════════════════════════════════════════════════════════
# Helpers normal / anormal — retournent {normales: [...], anomalies: [...]}
# ══════════════════════════════════════════════════════════════════════════

_NORMAL_WORDS = {"normal", "normaux", "normale", "normales", "ras", "rdp",
                 "sans particularité", "pas de particularité", ""}


def _is_normal(val):
    if not val:
        return True
    return str(val).strip().lower() in _NORMAL_WORDS


def _split_morpho(morpho):
    normales, anomalies = [], []
    for key, item in morpho.items():
        label = key.replace("_", " ").capitalize()
        if not isinstance(item, dict):
            continue
        if item.get("status") == "normal":
            normales.append(label)
        elif item.get("status") == "anormal":
            parts = []
            if item.get("details"):
                parts.extend(item["details"] if isinstance(item["details"], list) else [item["details"]])
            if item.get("text"):
                parts.append(item["text"])
            anomalies.append(f"{label} : {', '.join(parts)}" if parts else label)
    return {"normales": normales, "anomalies": anomalies}


def _split_radio(radio):
    normales, anomalies = [], []
    if not radio:
        return {"normales": normales, "anomalies": anomalies}

    vert = radio.get("vertebres", {})
    if isinstance(vert, dict):
        aspects = vert.get("aspects", [])
        if not aspects or aspects == ["Normal"]:
            normales.append("Rachis")
        else:
            anomalies.append(f"Rachis : {', '.join(aspects)}")

    os = radio.get("aspect_os", {})
    if isinstance(os, dict):
        aspects = os.get("aspects", [])
        if not aspects or aspects == ["Normal"]:
            normales.append("Aspect des os")
        else:
            anomalies.append(f"Aspect des os : {', '.join(aspects)}")

    cotes = radio.get("cotes", {})
    if isinstance(cotes, dict) and (cotes.get("droite") or cotes.get("gauche")):
        if cotes.get("droite") and cotes.get("gauche") and cotes["droite"] != cotes["gauche"]:
            anomalies.append(f"Côtes asymétriques (D:{cotes['droite']}, G:{cotes['gauche']})")
        else:
            normales.append(f"Côtes ({cotes.get('droite') or cotes.get('gauche')} paires)")

    if radio.get("thorax_forme"):
        v = radio["thorax_forme"]
        if _is_normal(v):
            normales.append("Thorax forme normale")
        else:
            anomalies.append(f"Thorax : {v}")

    os_longs = radio.get("biometries", {}).get("os_longs", {})
    for name, bone in os_longs.items():
        if not isinstance(bone, dict):
            continue
        z = bone.get("zscore_chitty")
        if z is not None and abs(z) > 2:
            anomalies.append(f"{name} (Z={z:+.2f})")
        elif z is not None:
            normales.append(f"{name} (Z={z:+.2f})")

    mat = radio.get("maturation_osseuse", [])
    for m in mat:
        if not isinstance(m, dict):
            continue
        if m.get("status") == "absent":
            anomalies.append(f"Maturation absente : {m.get('label', '?')} ({m.get('sa')} SA)")
        else:
            normales.append(f"{m.get('label', '?')} ({m.get('sa')} SA)")

    return {"normales": normales, "anomalies": anomalies}


_AUTOPSIE_CHECKS = [
    ("ouverture", "situs", "Situs"),
    ("ouverture", "diaphragme", "Diaphragme"),
    ("ouverture", "ogi", "OGI"),
    ("voies_aeriennes", "detail", "Voies aériennes"),
    ("thorax", "tvi", "TVI"),
    ("thorax", "pericarde", "Péricarde"),
    ("poumons", "morpho", "Poumons morphologie"),
    ("poumons", "docimasie", "Docimasie"),
    ("digestif", "meconium", "Méconium"),
    ("digestif", "anus", "Anus"),
    ("retroperitoine", "voies_urin", "Voies urinaires"),
    ("retroperitoine", "vessie", "Vessie"),
    ("retroperitoine", "gonades_pos", "Gonades"),
    ("neuro", "gyration", "Gyration"),
    ("neuro", "moelle", "Moelle"),
]


def _split_autopsie(ctx):
    normales, anomalies = [], []

    for section, field, label in _AUTOPSIE_CHECKS:
        data = ctx.get(section, {})
        val = data.get(field) if isinstance(data, dict) else None
        if val is None:
            continue
        if _is_normal(val):
            normales.append(label)
        else:
            anomalies.append(f"{label} : {val}")

    # Nested dicts with "etat" or "aspect"
    tsa = ctx.get("thorax", {}).get("tsa", {})
    if isinstance(tsa, dict) and tsa.get("etat"):
        if _is_normal(tsa["etat"]):
            normales.append("TSA")
        else:
            anomalies.append(f"TSA : {tsa['etat']}" + (f" — {tsa['detail']}" if tsa.get("detail") else ""))

    for org_key, org_label in [("thymus", "Thymus"), ("foie", "Foie"),
                                ("rate", "Rate"), ("pancreas", "Pancréas")]:
        section = "thorax" if org_key == "thymus" else "digestif"
        organ = ctx.get(section, {}).get(org_key, {})
        if isinstance(organ, dict) and organ.get("aspect"):
            if _is_normal(organ["aspect"]):
                normales.append(org_label)
            else:
                anomalies.append(f"{org_label} : {organ['aspect']}")

    reins = ctx.get("retroperitoine", {}).get("reins", {})
    if isinstance(reins, dict) and reins.get("aspects"):
        val = reins["aspects"] if isinstance(reins["aspects"], str) else ", ".join(reins["aspects"])
        if _is_normal(val):
            normales.append("Reins")
        else:
            anomalies.append(f"Reins : {val}")

    surr = ctx.get("retroperitoine", {}).get("surrenales", {})
    if isinstance(surr, dict) and surr.get("aspects"):
        val = surr["aspects"] if isinstance(surr["aspects"], str) else ", ".join(surr["aspects"])
        if _is_normal(val):
            normales.append("Surrénales")
        else:
            anomalies.append(f"Surrénales : {val}")

    coeur = ctx.get("coeur", {})
    if isinstance(coeur, dict):
        coeur_normal = True
        coeur_details = []
        for ck, cl in [("quatre_cav", "4 cavités"), ("foramen_ovale", "Foramen ovale"),
                        ("gros_vx", "Gros vaisseaux"), ("crosse", "Crosse")]:
            v = coeur.get(ck)
            if v and not _is_normal(v):
                coeur_normal = False
                coeur_details.append(f"{cl}: {v}")
        if coeur.get("vg_ej", {}).get("civ_diam"):
            coeur_normal = False
            coeur_details.append(f"CIV {coeur['vg_ej']['civ_diam']} mm")
        if coeur_normal and any(coeur.get(k) for k in ("quatre_cav", "foramen_ovale", "gros_vx")):
            normales.append("Cœur")
        elif coeur_details:
            anomalies.append(f"Cœur : {', '.join(coeur_details)}")

    neuro = ctx.get("neuro", {})
    if isinstance(neuro, dict) and neuro.get("detail"):
        anomalies.append(f"Neuro : {neuro['detail']}")

    return {"normales": normales, "anomalies": anomalies}


_FDR_KEYS = [
    ("fdr_hta", "HTA"),
    ("fdr_diabete", "Diabète"),
    ("fdr_tabac", "Tabac"),
    ("fdr_alcool", "Alcool"),
    ("fdr_consanguinite", "Consanguinité"),
]


def _split_fdr(atcd_mat):
    positifs, negatifs = [], []
    for key, label in _FDR_KEYS:
        val = atcd_mat.get(key)
        if not val or str(val).lower() in ("non", "false", "0", ""):
            negatifs.append(label)
        else:
            positifs.append(f"{label} : {val}" if val not in (True, "true", "oui", "Oui") else label)
    return {"positifs": positifs, "negatifs": negatifs}


_PRENATAL_NORMAL = {"normal", "normaux", "normale", "normales", "ras", "sans particularité", "",
                    "46,xx", "46,xy", "46 xx", "46 xy"}
_ECHO_KEYS = [("echo_t1", "Écho T1"), ("echo_t2", "Écho T2"), ("echo_t3", "Écho T3")]
_GENET_KEYS = [("caryotype", "Caryotype"), ("acpa", "ACPA"), ("ngs", "NGS/Exome"),
               ("recherche_aneuploidie", "DPNI")]


def _split_prenatal(exam_pren):
    normaux, anormaux = [], []
    for key, label in _ECHO_KEYS:
        status = exam_pren.get(f"{key}_status", "")
        details = exam_pren.get(f"{key}_details", "")
        if not status:
            continue
        if str(status).strip().lower() in _PRENATAL_NORMAL:
            normaux.append(label)
        else:
            anormaux.append(f"{label} : {status}" + (f" — {details}" if details else ""))

    for key, label in _GENET_KEYS:
        val = exam_pren.get(key, "")
        if not val:
            continue
        if str(val).strip().lower() in _PRENATAL_NORMAL | {"non fait", "non réalisé"}:
            normaux.append(label)
        else:
            anormaux.append(f"{label} : {val}")

    if exam_pren.get("anomalies_suspectees"):
        anormaux.append(f"Suspectées : {exam_pren['anomalies_suspectees']}")
    if exam_pren.get("anomalies_confirmees"):
        anormaux.append(f"Confirmées : {exam_pren['anomalies_confirmees']}")

    return {"normaux": normaux, "anormaux": anormaux}


def _split_fixe(macro_fixe):
    normales, anomalies = [], []
    organes = macro_fixe.get("organes", {})
    for org_id, org in organes.items():
        if not isinstance(org, dict):
            continue
        label = org_id.replace("_", " ").capitalize()
        if org.get("lesion_desc"):
            anomalies.append(f"{label} : {org['lesion_desc']}")
        else:
            normales.append(label)
    return {"normales": normales, "anomalies": anomalies}


def build_neuropath_context(case: dict, modules: dict) -> dict:
    """
    Construit le contexte pour le template neuropath
    a partir des donnees du cas et du module neuropath.
    """
    np_data = modules.get("neuropath", {})

    return {
        "numero": case.get("numero_dossier", ""),
        "date_examen": case.get("date_examen", ""),
        "np_sa": np_data.get("sa", ""),
        "np_descriptions": np_data.get("descriptions", {}),
        "np_bio": np_data.get("biometries", {}),
        "np_zscores": np_data.get("zscores", {}),
        "np_oculaire": np_data.get("oculaire", {}),
        "np_cerv": np_data.get("cervelet", {}),
        "np_aqueduc": np_data.get("aqueduc", {}),
        "np_cc": np_data.get("corps_calleux", {}),
        "np_thd": np_data.get("tranches_hd", []),
        "np_thg": np_data.get("tranches_hg", []),
        "np_hpo": np_data.get("hpo_codes", []),
    }


def build_radio_context(case: dict, modules: dict) -> dict:
    """
    Construit le contexte pour le template radio
    a partir des donnees du cas et du module radio.
    """
    rd = modules.get("radio", {})
    terme = rd.get("terme", {})

    return {
        "numero": case.get("numero_dossier", ""),
        "date_examen": case.get("date_examen", ""),
        "rad_terme_sa": terme.get("sa", ""),
        "rad_terme_jours": terme.get("jours", 0),
        "rad_aspect_general": rd.get("aspect_general", ""),
        "rad_cotes": rd.get("cotes", {}),
        "rad_thorax_forme": rd.get("thorax_forme", ""),
        "rad_vertebres": rd.get("vertebres", {}),
        "rad_aspect_os": rd.get("aspect_os", {}),
        "rad_biometries": rd.get("biometries", {}),
        "rad_os_longs": rd.get("biometries", {}).get("os_longs", {}),
        "rad_scores": rd.get("scores_staturaux", {}),
        "rad_maturation": rd.get("maturation_osseuse", []),
        "rad_remarques": rd.get("remarques", ""),
        "rad_hpo_codes": rd.get("hpo_codes", []),
    }


# ══════════════════════════════════════════════════════════════════════════
# Registre des templates — avec versioning
# ══════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "soffoet": {
        "label": "CR SOFFOET (type 1)",
        "description": "Compte-rendu type SOFFOET complet",
        "version": "2.0.0",
        "file": "soffoet.jinja2",
        "changelog": [
            {
                "version": "2.0.0",
                "date": "2026-03-29",
                "changes": [
                    "Conclusion refondée : terme, macération, trophicité, liste exhaustive anomalies",
                    "Intégration complète des champs texte libres PWA (voies aériennes, OGI, TSA, "
                    "valves cardiaques, estomac, tube digestif, neuro, gonades, vessie, voies urinaires)",
                    "Section 'Examen après fixation' (macro_fixe : lésions + cassettes)",
                    "Anomalies prénatales (suspectées / confirmées) dans résumé clinique et conclusion",
                    "Détail prélèvements spéciaux",
                ],
            },
            {
                "version": "1.0.0",
                "date": "2026-03-01",
                "changes": [
                    "Template SOFFOET initial — résumé clinique, aspect externe, biométries, "
                    "examen interne, prélèvements, conclusion",
                ],
            },
        ],
    },
    "court": {
        "label": "CR Court",
        "description": "Synthèse courte pour communication rapide",
        "version": "2.0.0",
        "file": "court.jinja2",
        "changelog": [
            {
                "version": "2.0.0",
                "date": "2026-03-29",
                "changes": [
                    "Conclusion refondée : terme, macération, trophicité, liste exhaustive anomalies",
                    "Ajout notes (frais / autopsie) et anomalies prénatales",
                ],
            },
            {
                "version": "1.0.0",
                "date": "2026-03-01",
                "changes": ["Template court initial — synthèse rapide"],
            },
        ],
    },
    "neuropath": {
        "label": "Brouillon CR neuropath",
        "description": "Compte-rendu neuropathologique (examen du cerveau fixé)",
        "version": "1.0.0",
        "file": "neuropath.jinja2",
        "changelog": [
            {
                "version": "1.0.0",
                "date": "2026-03-29",
                "changes": [
                    "Template neuropath initial — macroscopie, biométries cérébrales, "
                    "cervelet/CC/aqueduc, biométries oculaires, tranches HD/HG, codes HPO",
                ],
            },
        ],
    },
    "radio": {
        "label": "Brouillon CR radio",
        "description": "Compte-rendu d'imagerie radiologique (squelette, biométries osseuses, maturation)",
        "version": "1.0.0",
        "file": "radio.jinja2",
        "changelog": [
            {
                "version": "1.0.0",
                "date": "2026-03-29",
                "changes": [
                    "Template radio initial — aspect squelette, biométries os longs (Chitty), "
                    "scores staturaux (Hadlock/Adalian), maturation osseuse",
                ],
            },
        ],
    },
}


def get_available_templates() -> list[dict]:
    return _get_templates(TEMPLATES)


def get_template_changelog(template_id: str) -> list[dict]:
    return _get_changelog(TEMPLATES, template_id)


def get_all_versions_info() -> dict:
    return _get_versions(TEMPLATES)


def cr_helpers(context: dict) -> dict:
    return {
        "_ds": lambda key: _ds_text(context.get("calc_bio", {}), key),
        "_morpho": lambda key: _morpho_text(context.get("morpho", {}), key),
        "_table_atcd_obs": lambda: _table_atcd_obs(context.get("atcd_obs", [])),
        "table_biometries_externes": lambda: _table_bio_ext(context.get("calc_bio", {})),
        "table_biometries_internes": lambda: _table_bio_int(context.get("calc_org", {})),
        "_table_biometries": lambda: _table_biometries(context.get("calc_bio", {}), context.get("calc_org", {})),
        "table_os_longs": lambda: _table_os_longs(context.get("rad_os_longs", {})),
        "table_maturation": lambda: _table_maturation(context.get("rad_maturation", [])),
        "split_morpho": lambda: _split_morpho(context.get("morpho", {})),
        "split_radio": lambda: _split_radio(context.get("radio", {})),
        "split_autopsie": lambda: _split_autopsie(context),
        "split_fdr": lambda: _split_fdr(context.get("atcd_mat", {})),
        "split_prenatal": lambda: _split_prenatal(context.get("exam_prenataux", {})),
        "split_fixe": lambda: _split_fixe(context.get("macro_fixe", {})),
        "table_genest": lambda: _table_genest(context.get("maceration", {})),
        "genest_retention": lambda: _genest_retention(context.get("maceration", {})),
        "age_mere": _age_mere(context.get("ddn_mere"), context.get("date_deces") or context.get("date_examen")),
    }


def render_cr(template_id: str, context: dict) -> str:
    return _render(TEMPLATES, template_id, context, custom_helpers=cr_helpers(context))
