"""
FoetoPath — Export JSON concaténé pour LLM.

Produit un JSON :
  - ordonné narrativement (déroulé réel d'une autopsie fœtale)
  - sans bruit (aucun champ vide, null, ou bloc sans information diagnostique)
  - HPO-complet (chaque anomalie → un code HPO inline)
  - interprété (z-scores commentés, discordances signalées)
  - consommable par un LLM pour du diagnostic différentiel

Schéma : foetopath_llm_export_v2.2 / v3
"""

import re
from datetime import datetime, timezone

from ._utils import _prune, _get, _f
from .hpo import (
    _collect_hpo_recursive,
    _collect_constatations_libres_recursive,
    _extract_hpo_findings,
)
from .sections import (
    _build_identite,
    _build_examen_externe,
    _build_biometries_fraiches,
    _build_ouverture,
)
from .radiology import _build_radiologie
from .organs import (
    _build_examen_in_situ,
    _build_organes_fixes,
    _build_neuropathologie,
)
from .ratios import _build_ratios_diagnostiques
from .alerts import (
    _build_alertes,
    _build_semiologie_litteraire,
    _build_contradictions,
)


def build_v2(case_id: int, case: dict, modules_data: dict) -> dict:
    """
    Construit le JSON concaténé v2 pour export LLM.

    Args:
        case_id: ID du cas
        case: données admin du cas (table cases)
        modules_data: dict {module_name: data}

    Returns:
        Dict JSON v2 prêt à sérialiser
    """
    dossier = case.get("numero_dossier", "")
    macro_frais = modules_data.get("macro_frais", {})
    macro_autopsie = modules_data.get("macro_autopsie", {})
    macro_fixe = modules_data.get("macro_fixe", {})
    neuropath = modules_data.get("neuropath", {})
    radio = modules_data.get("radio", {})

    # Terme SA
    terme_sa = None
    terme_obj = macro_frais.get("terme", {})
    if isinstance(terme_obj, dict):
        terme_sa = terme_obj.get("sa")
    elif isinstance(terme_obj, (int, float)):
        terme_sa = int(terme_obj)
    if not terme_sa:
        bio = macro_frais.get("biometries", macro_frais.get("biometrie", {}))
        terme_sa = bio.get("terme_sa") or bio.get("terme")
    if not terme_sa and case.get("terme_issue"):
        m = re.match(r"(\d+)", str(case["terme_issue"]))
        if m:
            terme_sa = int(m.group(1))
    if terme_sa:
        terme_sa = int(terme_sa)

    # Masse corporelle
    masse_corporelle = _f(_get(macro_frais, "biometries", "masse"))

    # Collecter tous les HPO findings PWA de tous les modules
    all_hpo_findings = []
    for mod_data in modules_data.values():
        if isinstance(mod_data, dict):
            all_hpo_findings.extend(_extract_hpo_findings(mod_data))

    # ── Construction ordonnée narrativement ──

    meta = {
        "case_id": case_id,
        "numero_dossier": dossier,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "2.3.0",
        "schema": "foetopath_llm_export_v2.3",
    }

    identite = _build_identite(case, macro_frais, modules_data)
    examen_externe = _build_examen_externe(macro_frais, macro_autopsie, all_hpo_findings)

    biometries = {}
    if terme_sa:
        biometries = _build_biometries_fraiches(macro_frais, terme_sa)

    radiologie = _build_radiologie(radio, terme_sa or 0)
    ouverture = _build_ouverture(macro_autopsie)
    examen_in_situ = _build_examen_in_situ(macro_autopsie, all_hpo_findings)

    organes_fixes = _build_organes_fixes(
        macro_autopsie, macro_fixe, terme_sa or 0,
        masse_corporelle or 0, all_hpo_findings)

    ratios_diag = _build_ratios_diagnostiques(
        macro_frais, macro_autopsie, macro_fixe, neuropath, radio,
        masse_corporelle or 0, terme_sa or 0)

    neuropathologie = _build_neuropathologie(neuropath, terme_sa or 0, all_hpo_findings)

    histo = modules_data.get("histologie", {})
    histologie = {}
    if isinstance(histo, dict):
        if histo.get("organes"):
            histologie["organes_examines"] = histo["organes"]
        if histo.get("lesions"):
            histologie["lesions"] = histo["lesions"]
        if histo.get("commentaire"):
            histologie["commentaire"] = histo["commentaire"]

    result = {
        "_meta": meta,
        "identite": identite,
        "examen_externe": examen_externe,
        "biometries_fraiches": biometries,
        "radiologie": radiologie,
        "ouverture_cavites": ouverture,
        "examen_in_situ": examen_in_situ,
        "organes_fixes": organes_fixes,
        "ratios_diagnostiques": ratios_diag,
        "neuropathologie": neuropathologie,
        "histologie": histologie,
    }

    # hpo_summary — agrégation récursive (R2)
    all_hpo = _collect_hpo_recursive(result)
    seen = set()
    unique_hpo = []
    for h in all_hpo:
        if h["code"] not in seen:
            seen.add(h["code"])
            unique_hpo.append(h)

    result["hpo_summary"] = {
        "total_count": len(unique_hpo),
        "codes": unique_hpo,
    }

    alertes = _build_alertes(biometries, organes_fixes, radiologie,
                             examen_externe, ouverture, examen_in_situ,
                             ratios_diag)
    if alertes:
        result["alertes"] = alertes

    result = _prune(result) or {}
    result["_meta"] = meta

    return result


def build_v3(case_id: int, case: dict, modules_data: dict) -> dict:
    """
    Construit le JSON v3 pour le pipeline LLM deux passes.

    Structure :
      - _meta (version 3.0.0)
      - brief (pour Passe 1 — orientation syndromique)
      - dossier_complet (pour Passe 2 — génération CR)
    """
    v2 = build_v2(case_id, case, modules_data)

    macro_frais = modules_data.get("macro_frais", {})
    macro_fixe = modules_data.get("macro_fixe", {})

    hpo_summary = v2.get("hpo_summary", {})
    hpo_codes_set = {h["code"] for h in hpo_summary.get("codes", [])}

    ratios = v2.get("ratios_diagnostiques", [])

    # ── BRIEF ──
    identite_full = v2.get("identite", {})
    identite_brief = {
        "sexe": identite_full.get("sexe"),
        "terme_sa": identite_full.get("terme_sa"),
        "indication_examen": identite_full.get("indication_examen"),
        "etat_conservation": identite_full.get("etat_conservation"),
        "maceration_maroun": identite_full.get("maceration_maroun", 0),
    }

    alertes = v2.get("alertes", [])

    zscores_anormaux = []
    organes_fixes = v2.get("organes_fixes", {})
    for o in organes_fixes.get("organes", []):
        z = o.get("zscore")
        if z is not None and abs(z) >= 2.0:
            zscores_anormaux.append({
                "organe": o["organe"],
                "zscore": z,
                "interpretation": o.get("interpretation", ""),
            })
    biometries = v2.get("biometries_fraiches", {})
    for m in biometries.get("mesures", []):
        z = m.get("zscore")
        if z is not None and abs(z) >= 2.0:
            zscores_anormaux.append({
                "organe": m["parametre"],
                "zscore": z,
                "interpretation": m.get("interpretation", ""),
            })

    ratios_anormaux = []
    for r in ratios:
        interp = r.get("interpretation", "")
        if interp.startswith("anormal") or interp.startswith("critique"):
            entry = {
                "ratio": r["ratio"],
                "resultat": r["resultat"],
                "interpretation": r.get("signification_clinique", interp),
            }
            if r.get("hpo"):
                entry["hpo"] = r["hpo"]
            ratios_anormaux.append(entry)

    hpo_compact = {
        "total_count": hpo_summary.get("total_count", 0),
        "codes": [
            {"code": h["code"], "label": h.get("label", "")}
            for h in hpo_summary.get("codes", [])
        ],
    }

    semiologie = _build_semiologie_litteraire(
        hpo_codes_set, ratios, organes_fixes,
        v2.get("radiologie", {}), biometries)

    contradictions = _build_contradictions(
        hpo_codes_set, organes_fixes, ratios,
        macro_frais, macro_fixe)

    # ── DOSSIER COMPLET ──
    dossier = {}
    for key in ("examen_externe", "biometries_fraiches", "radiologie",
                "ouverture_cavites", "examen_in_situ", "organes_fixes",
                "ratios_diagnostiques", "neuropathologie", "histologie"):
        if key in v2:
            dossier[key] = v2[key]

    constatations_libres = _collect_constatations_libres_recursive(dossier)
    _seen = set()
    constatations_non_codees = []
    for c in constatations_libres:
        k = c["constatation"].lower()
        if k in _seen:
            continue
        _seen.add(k)
        constatations_non_codees.append(c)

    # ── Enrichissement brief: ATCD, prenatal, radio structurés ──
    atcd_struct = identite_full.get("antecedents_maternels", {})
    prenatal_struct = identite_full.get("examens_prenataux", {})

    radio_section = v2.get("radiologie", {})
    radio_anomalies = []
    for os_entry in (radio_section.get("squelette_appendiculaire", {})
                     .get("os_longs", [])):
        z = os_entry.get("zscore_chitty")
        if z is not None and abs(z) >= 2:
            radio_anomalies.append(
                f"{os_entry['os']} {os_entry.get('cote', '')}: "
                f"{os_entry['longueur_mm']}mm (z={z:+.1f})")
    disc = (radio_section.get("scores_staturaux", {})
            .get("discordance"))
    if disc:
        radio_anomalies.append(f"Discordance staturale: {disc}")
    axial = radio_section.get("squelette_axial", {})
    if axial.get("cotes", {}).get("asymetrie"):
        c = axial["cotes"]
        radio_anomalies.append(
            f"Asymétrie costale: {c.get('droite', '?')}D / "
            f"{c.get('gauche', '?')}G")
    for rachis_f in axial.get("rachis", []):
        if isinstance(rachis_f, dict) and rachis_f.get("hpo"):
            radio_anomalies.append(
                rachis_f.get("constatation", rachis_f.get("hpo_label", "")))

    brief = {
        "_usage": "PASSE 1 — orientation syndromique",
        "identite": identite_brief,
        "antecedents_maternels": atcd_struct,
        "examens_prenataux": prenatal_struct,
        "alertes": alertes,
        "zscores_anormaux": zscores_anormaux,
        "ratios_anormaux": ratios_anormaux,
        "radio_anomalies": radio_anomalies,
        "hpo_summary": hpo_compact,
        "constatations_non_codees": constatations_non_codees,
        "semiologie_litteraire": semiologie,
        "contradictions": contradictions,
    }

    if "ratios_diagnostiques" in dossier:
        dossier["ratios_diagnostiques_complets"] = dossier.pop("ratios_diagnostiques")

    dossier["_usage"] = "PASSE 2 — génération du compte-rendu"

    meta = {
        "case_id": case_id,
        "numero_dossier": case.get("numero_dossier", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "3.1.0",
        "schema": "foetopath_llm_export_v3.1",
    }

    result = {
        "_meta": meta,
        "brief": _prune(brief) or {},
        "dossier_complet": _prune(dossier) or {},
    }

    result["brief"]["_usage"] = brief["_usage"]
    result["dossier_complet"]["_usage"] = dossier["_usage"]

    return result
