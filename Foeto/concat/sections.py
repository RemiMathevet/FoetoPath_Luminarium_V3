"""Builders identité, examen externe, biométries fraiches, ouverture."""

from biometrics import sa_to_gc_class, calc_ds, interpret_ds
from reference_data import GC_MACRO

from ._utils import _prune, _get, _f, _finding
from .hpo import _lookup_hpo, _parse_comma_list, _items_to_findings


_FDR_KEYS = [
    ("fdr_hta", "HTA"), ("fdr_diabete", "Diabète"), ("fdr_tabac", "Tabac"),
    ("fdr_alcool", "Alcool"), ("fdr_consanguinite", "Consanguinité"),
]
_PRENATAL_NORMAL = {
    "normal", "normaux", "normale", "normales", "ras", "sans particularité",
    "", "46,xx", "46,xy", "46 xx", "46 xy",
}
_ECHO_KEYS = [("echo_t1", "Écho T1"), ("echo_t2", "Écho T2"), ("echo_t3", "Écho T3")]
_GENET_KEYS = [
    ("caryotype", "Caryotype"), ("acpa", "ACPA"),
    ("ngs", "NGS/Exome"), ("recherche_aneuploidie", "DPNI"),
]


def _build_identite(case: dict, macro_frais: dict, modules: dict) -> dict:
    """Section identite."""
    terme = macro_frais.get("terme", {})
    mac = macro_frais.get("maceration", {})
    atcd = modules.get("atcd_maternels", {})

    result = {
        "sexe": case.get("sexe") or macro_frais.get("sexe"),
        "terme_sa": terme.get("sa") if isinstance(terme, dict) else terme,
        "terme_jours": terme.get("jours", 0) if isinstance(terme, dict) else 0,
        "indication_examen": case.get("indication_examen"),
        "etat_conservation": macro_frais.get("etat"),
        "maceration_maroun": mac.get("maroun_score", 0) if isinstance(mac, dict) else mac,
        "service_demandeur": case.get("service_demandeur"),
        "medecin_referent": case.get("medecin_referent"),
        "nom_mere": case.get("nom_mere"),
    }

    if isinstance(atcd, dict):
        atcd_struct = {}
        for k in ("gestite", "parite", "groupe_sanguin", "rhesus",
                   "profession_mere"):
            if atcd.get(k):
                atcd_struct[k] = atcd[k]
        if atcd.get("atcd_medicaux"):
            atcd_struct["atcd_medicaux"] = atcd["atcd_medicaux"]
        if atcd.get("traitements"):
            atcd_struct["traitements"] = atcd["traitements"]
        fdr_pos, fdr_neg = [], []
        for fdr_key, label in _FDR_KEYS:
            val = atcd.get(fdr_key)
            if val and str(val).lower() not in ("non", "false", "0", ""):
                fdr_pos.append(label if val in (True, "true", "oui", "Oui")
                               else f"{label} : {val}")
            else:
                fdr_neg.append(label)
        if fdr_pos:
            atcd_struct["fdr_positifs"] = fdr_pos
        if fdr_neg:
            atcd_struct["fdr_negatifs"] = fdr_neg
        if atcd_struct:
            result["antecedents_maternels"] = atcd_struct

    gross = modules.get("grossesse_en_cours", {})
    if isinstance(gross, dict):
        gross_clean = _prune(gross)
        if gross_clean:
            result["grossesse"] = gross_clean

    exam = modules.get("examens_prenataux", {})
    if isinstance(exam, dict):
        pren_norm, pren_anorm = [], []
        for key, label in _ECHO_KEYS:
            status = exam.get(f"{key}_status", "")
            details = exam.get(f"{key}_details", "")
            if not status:
                continue
            if str(status).strip().lower() in _PRENATAL_NORMAL:
                pren_norm.append(label)
            else:
                pren_anorm.append(f"{label} : {status}"
                                  + (f" — {details}" if details else ""))
        for key, label in _GENET_KEYS:
            val = exam.get(key, "")
            if not val:
                continue
            if str(val).strip().lower() in _PRENATAL_NORMAL | {"non fait", "non réalisé"}:
                pren_norm.append(label)
            else:
                pren_anorm.append(f"{label} : {val}")
        if exam.get("anomalies_suspectees"):
            pren_anorm.append(f"Suspectées : {exam['anomalies_suspectees']}")
        if exam.get("anomalies_confirmees"):
            pren_anorm.append(f"Confirmées : {exam['anomalies_confirmees']}")
        exam_struct = {}
        if pren_norm:
            exam_struct["normaux"] = pren_norm
        if pren_anorm:
            exam_struct["anormaux"] = pren_anorm
        if exam_struct:
            result["examens_prenataux"] = exam_struct

    return result


def _build_examen_externe(macro_frais: dict, macro_autopsie: dict,
                          all_hpo_findings: list) -> dict:
    """Section examen_externe : R5."""
    morpho = macro_frais.get("morphologie", {})

    cranio_keys = {"crane", "fontanelles", "yeux", "nez", "bouche", "oreilles"}
    membres_keys = {"membres_sup", "membres_inf", "mains", "pieds_morpho"}
    oge_keys = {"oge", "anus"}
    teguments_keys = {"teguments", "pilosite", "cheveux", "ongles"}
    autres_keys = {"aspect_general", "symetrie", "proportions", "cou",
                   "thorax", "abdomen", "dos", "cordon"}

    def _morpho_findings(keys: set) -> list:
        findings = []
        for k in keys:
            item = morpho.get(k, {})
            if not isinstance(item, dict):
                continue
            if item.get("status") != "anormal":
                continue
            details = item.get("details", [])
            if isinstance(details, str):
                details = [details]
            text = item.get("text", "")

            items_list = [d for d in details if d] + ([text] if text else [])
            if not items_list:
                items_list = [f"{k.replace('_', ' ').capitalize()} : anomalie"]

            for desc in items_list:
                code, label = _lookup_hpo(desc)
                findings.append(_finding(desc, code, label))
        return findings

    result = {
        "morphologie_cranio_faciale": _morpho_findings(cranio_keys),
        "membres": _morpho_findings(membres_keys),
        "teguments": _morpho_findings(teguments_keys),
        "autres": _morpho_findings(autres_keys),
    }

    oge_findings = _morpho_findings(oge_keys)

    ogi_detail = _get(macro_autopsie, "ouverture", "ogi_detail")
    if ogi_detail:
        items = _parse_comma_list(ogi_detail)
        oge_findings.extend(_items_to_findings(items, all_hpo_findings))

    result["organes_genitaux_externes"] = oge_findings

    return result


def _build_biometries_fraiches(macro_frais: dict, terme_sa: int) -> dict:
    """Section biometries_fraiches avec z-scores GC inline."""
    gc_class = sa_to_gc_class(terme_sa)
    if not gc_class or gc_class not in GC_MACRO:
        return {"terme_reference_sa": terme_sa, "erreur": f"Pas de référence GC pour {terme_sa} SA"}

    ref = GC_MACRO[gc_class]
    bio = macro_frais.get("biometries", macro_frais.get("biometrie", {}))

    field_map = [
        ("masse", "masse", "masse", "g"),
        ("vt", "vertex_talon", "VT", "mm"),
        ("vc", "vertex_coccyx", "VC", "mm"),
        ("pc", "perimetre_cranien", "PC", "mm"),
        ("pied", "pied", "pied", "mm"),
    ]

    mesures = []
    for app_key, param_name, gc_key, unite in field_map:
        val = _f(bio.get(app_key))
        if val is not None and gc_key in ref:
            r = ref[gc_key]
            ds = calc_ds(val, r["moy"], r["sd"])
            mesures.append({
                "parametre": param_name,
                "valeur": val,
                "unite": unite,
                "moyenne_ref": r["moy"],
                "sd_ref": r["sd"],
                "zscore": ds,
                "interpretation": interpret_ds(ds),
                "reference": "Guihard-Costa 2002",
            })

    brutes_keys = ["bip", "fo", "dici", "dice", "fpg", "fpd", "dim",
                   "sternum", "main", "pt", "pa"]
    brutes = {}
    for k in brutes_keys:
        val = _f(bio.get(k))
        if val is not None:
            brutes[k] = val

    concordance = {"terme_clinique_sa": terme_sa}
    for m in mesures:
        if m["parametre"] == "pied" and m["zscore"] is not None:
            if abs(m["zscore"]) <= 2:
                concordance["terme_pied_concordant"] = True
            else:
                concordance["terme_pied_discordant_ds"] = m["zscore"]
        if m["parametre"] == "vertex_talon" and m["zscore"] is not None:
            if abs(m["zscore"]) <= 2:
                concordance["terme_vt_concordant"] = True
            else:
                concordance["terme_vt_discordant_ds"] = m["zscore"]

    result = {
        "terme_reference_sa": terme_sa,
        "classe_gc": gc_class,
        "mesures": mesures,
    }
    if brutes:
        result["biometries_brutes_complementaires"] = brutes
    if len(concordance) > 1:
        result["concordance_terme"] = concordance

    return result


def _build_ouverture(macro_autopsie: dict) -> dict:
    """Section ouverture_cavites."""
    ouv = macro_autopsie.get("ouverture", {})
    if not isinstance(ouv, dict):
        return {}

    result = {}
    if ouv.get("situs"):
        result["situs"] = ouv["situs"]
    if ouv.get("diaphragme"):
        result["diaphragme"] = ouv["diaphragme"]

    epanch = ouv.get("epanchements", {})
    if isinstance(epanch, dict):
        positifs = {k: v for k, v in epanch.items() if v and v > 0}
        if positifs:
            result["epanchements"] = positifs
        else:
            result["aucun_epanchement"] = True

    return result
