"""Moteur de calcul biometrique pediatrique — reference Molina 2019.

Reference: Molina DK et al. Am J Forensic Med Pathol 2019;40:318-328
1759 deces traumatiques, 0-12 ans, 4 centres USA

Deux modes de calcul:
  1. Par age (jours) -> bracket mensuel (1m-23m) ou annuel (2a-12a)
  2. Par taille (cm) -> bracket de 5cm (<40 a >=165)

Les moy/sd sont estimes depuis les IC95 publies (moy = milieu, sd = largeur/3.92).
"""

import math
from typing import Optional

from reference_data import (
    MOLINA_ORGANES_AGE, MOLINA_POUMONS, MOLINA_REINS, MOLINA_META,
    MOLINA_ORGANES_TAILLE, MOLINA_POUMONS_TAILLE, MOLINA_REINS_TAILLE,
    ORGAN_LABELS,
)


def _safe_float(val) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return None


def calc_ds(value: float, moy: float, sd: float) -> Optional[float]:
    if sd == 0 or value is None or moy is None:
        return None
    return round((value - moy) / sd, 2)


def interpret_ds(ds: Optional[float]) -> str:
    if ds is None:
        return "non calculable"
    a = abs(ds)
    if a <= 1:
        return "normal"
    direction = "augmente" if ds > 0 else "diminue"
    if a <= 2:
        return f"moderement {direction}"
    return f"significativement {direction}"


def pooled_ds(ds_d: float, ds_g: float) -> float:
    mean_ds = (ds_d + ds_g) / 2
    rms = math.sqrt((ds_d**2 + ds_g**2) / 2)
    return round(math.copysign(rms, mean_ds), 2)


# ── Age -> Molina bracket ──

_AGE_BRACKETS = (
    [(f"{m}m", m * 30.44) for m in range(1, 24)]
    + [(f"{y}a", y * 365.25) for y in range(2, 13)]
)


def age_days_to_bracket(age_days) -> Optional[str]:
    if age_days is None or age_days < 15:
        return None
    if age_days > 5475:
        return None
    best_key, best_dist = None, float("inf")
    for key, center in _AGE_BRACKETS:
        dist = abs(age_days - center)
        if dist < best_dist:
            best_dist = dist
            best_key = key
    return best_key


def age_bracket_label(bracket: str) -> str:
    if not bracket:
        return ""
    if bracket.endswith("m"):
        return f"{bracket[:-1]} mois"
    if bracket.endswith("a"):
        return f"{bracket[:-1]} ans"
    return bracket


# ── Height -> Molina bracket ──

def height_to_bracket(height_cm) -> Optional[str]:
    if height_cm is None or height_cm <= 0:
        return None
    if height_cm < 40:
        return "<40"
    if height_cm >= 165:
        return ">=165"
    lower = int(height_cm // 5) * 5
    return f"{lower}-{lower + 5}"


# ── Generic section computation ──

def _compute_section(ref_table, bracket, organ_masses, combined_poumons, combined_reins):
    """Compute DS for organs against a Molina reference bracket.

    Returns (organes_combined, organes_pairs) dicts.
    """
    if not bracket or bracket not in ref_table:
        return {}, {}

    ref = ref_table[bracket]

    organes_combined = {}
    for key in ("cerveau", "coeur", "foie", "rate"):
        val = _safe_float(organ_masses.get(key))
        if val is not None and key in ref:
            r = ref[key]
            ds = calc_ds(val, r["moy"], r["sd"])
            organes_combined[key] = {
                "valeur": val,
                "label": ORGAN_LABELS.get(key, key),
                "moyenne": r["moy"], "sd": r["sd"],
                "ds": ds, "interpretation": interpret_ds(ds),
                "unite": "g",
            }

    for base, combined_ref_table, combined_key in [
        ("poumon", combined_poumons, "poumons"),
        ("rein", combined_reins, "reins"),
    ]:
        vd = _safe_float(organ_masses.get(f"{base}_d"))
        vg = _safe_float(organ_masses.get(f"{base}_g"))
        total = None
        if vd is not None and vg is not None:
            total = round(vd + vg, 2)
        elif vd is not None:
            total = vd
        elif vg is not None:
            total = vg

        combined_ref = combined_ref_table.get(bracket) if combined_ref_table else None
        if total is not None and combined_ref:
            ds = calc_ds(total, combined_ref["moy"], combined_ref["sd"])
            organes_combined[combined_key] = {
                "valeur": total,
                "label": ORGAN_LABELS.get(combined_key, combined_key),
                "moyenne": combined_ref["moy"], "sd": combined_ref["sd"],
                "ds": ds, "interpretation": interpret_ds(ds),
                "unite": "g",
            }

    organes_pairs = {}
    for base in ("poumon", "rein"):
        key_d, key_g = f"{base}_d", f"{base}_g"
        if key_d not in ref and key_g not in ref:
            continue

        ds_d_val, ds_g_val = None, None
        for key, side in [(key_d, "D"), (key_g, "G")]:
            val = _safe_float(organ_masses.get(key))
            if val is not None and key in ref:
                r = ref[key]
                ds = calc_ds(val, r["moy"], r["sd"])
                if key == key_d:
                    ds_d_val = ds
                else:
                    ds_g_val = ds
                organes_pairs[key] = {
                    "valeur": val,
                    "label": ORGAN_LABELS.get(key, f"{base.capitalize()} {side}"),
                    "moyenne": r["moy"], "sd": r["sd"],
                    "ds": ds, "interpretation": interpret_ds(ds),
                    "unite": "g",
                }

        if ds_d_val is not None and ds_g_val is not None:
            ds_p = pooled_ds(ds_d_val, ds_g_val)
            combined_key = f"{base}s"
            organes_pairs[f"_{combined_key}_pooled"] = {
                "ds_d": ds_d_val, "ds_g": ds_g_val,
                "ds_pooled": ds_p,
                "interpretation": interpret_ds(ds_p),
                "method": "v(mean(ds2))",
            }

    return organes_combined, organes_pairs


# ── Ratios ──

def compute_ratios(poids_g, organ_masses):
    if not poids_g or poids_g <= 0:
        return {}

    combined = {}
    for key in ("coeur", "foie", "rate", "cerveau"):
        val = _safe_float(organ_masses.get(key))
        if val is not None:
            combined[key] = val

    for base in ("poumon", "rein"):
        vd = _safe_float(organ_masses.get(f"{base}_d"))
        vg = _safe_float(organ_masses.get(f"{base}_g"))
        combined_key = f"{base}s"
        if vd is not None and vg is not None:
            combined[combined_key] = round(vd + vg, 2)
        elif vd is not None:
            combined[combined_key] = vd
        elif vg is not None:
            combined[combined_key] = vg

    ratios = {}
    for key, masse in combined.items():
        label = ORGAN_LABELS.get(key, key)
        ratio = round(masse / poids_g, 4)
        ratios[key] = {
            "label": label, "masse_organe": masse,
            "ratio": ratio, "pourcentage": round(ratio * 100, 2),
        }
    return ratios


# ── Orchestrateur ──

def compute_pediatric_all(age_days, gender, poids_g, taille_cm=None, organes=None):
    age_bracket = age_days_to_bracket(age_days)
    taille_bracket = height_to_bracket(taille_cm)

    results = {
        "mode": "pediatrique",
        "age_days": age_days,
        "age_bracket": age_bracket,
        "age_bracket_label": age_bracket_label(age_bracket),
        "poids_g": poids_g,
        "taille_cm": taille_cm,
        "taille_bracket": taille_bracket,
        "organes_age": {},
        "organes_age_individuels": {},
        "organes_taille": {},
        "organes_taille_individuels": {},
        "ratios": {},
        "alertes": [],
    }

    if not organes:
        return results

    if age_bracket:
        org_c, org_p = _compute_section(
            MOLINA_ORGANES_AGE, age_bracket, organes,
            MOLINA_POUMONS, MOLINA_REINS,
        )
        if org_c:
            meta = MOLINA_META.get(age_bracket, {})
            results["organes_age"] = {
                "reference": "Molina 2019 (par age)",
                "classe": age_bracket_label(age_bracket),
                "n": meta.get("n"),
                "organes": org_c,
            }
        if org_p:
            results["organes_age_individuels"] = {
                "reference": "Molina 2019 (par age)",
                "organes_pairs": org_p,
            }

    if taille_bracket:
        org_c_t, org_p_t = _compute_section(
            MOLINA_ORGANES_TAILLE, taille_bracket, organes,
            MOLINA_POUMONS_TAILLE, MOLINA_REINS_TAILLE,
        )
        if org_c_t:
            results["organes_taille"] = {
                "reference": "Molina 2019 (par taille)",
                "classe": f"{taille_bracket} cm",
                "organes": org_c_t,
            }
        if org_p_t:
            results["organes_taille_individuels"] = {
                "reference": "Molina 2019 (par taille)",
                "organes_pairs": org_p_t,
            }

    if poids_g:
        results["ratios"] = compute_ratios(poids_g, organes)

    for section_key in ("organes_age", "organes_taille"):
        section = results.get(section_key, {})
        for key, val in section.get("organes", {}).items():
            if val.get("ds") is not None and abs(val["ds"]) > 2:
                ref = section.get("reference", "")
                results["alertes"].append(
                    f"{val.get('label', key)} : {val['ds']:+.1f} DS ({val['interpretation']}) [{ref}]"
                )

    for section_key in ("organes_age_individuels", "organes_taille_individuels"):
        section = results.get(section_key, {})
        for key, val in section.get("organes_pairs", {}).items():
            if key.startswith("_"):
                continue
            if val.get("ds") is not None and abs(val["ds"]) > 2:
                ref = section.get("reference", "")
                results["alertes"].append(
                    f"{val.get('label', key)} : {val['ds']:+.1f} DS ({val['interpretation']}) [{ref}]"
                )

    return results


# ── Rapport texte ──

def render_pediatric_report(results):
    lines = ["BIOMETRIES PEDIATRIQUES — MASSES D'ORGANES", "=" * 50, ""]

    if results.get("age_days") is not None:
        label = results.get("age_bracket_label", "")
        lines.append(f"Age au deces : {results['age_days']} jours ({label})")
    if results.get("poids_g"):
        lines.append(f"Poids corporel : {results['poids_g']:.0f} g")
    if results.get("taille_cm"):
        lines.append(f"Taille : {results['taille_cm']:.1f} cm (bracket {results.get('taille_bracket', '?')})")
    lines.append("")

    for section_key, title in [
        ("organes_age", "PAR AGE"),
        ("organes_taille", "PAR TAILLE"),
    ]:
        section = results.get(section_key, {})
        organes = section.get("organes", {})
        if not organes:
            continue
        ref = section.get("reference", "")
        classe = section.get("classe", "")
        lines.append(f"MASSES D'ORGANES — {title} (ref. {ref}, {classe})")
        lines.append("-" * 50)
        for key, o in organes.items():
            ds_str = f"{o['ds']:+.2f} DS" if o.get("ds") is not None else "—"
            lines.append(
                f"  {o['label']:20s} : {o['valeur']:8.2f} g  "
                f"(moy: {o['moyenne']:.1f}, sd: {o['sd']:.1f})  ->  {ds_str}  [{o['interpretation']}]"
            )
        lines.append("")

    for section_key, title in [
        ("organes_age_individuels", "PAIRS PAR AGE"),
        ("organes_taille_individuels", "PAIRS PAR TAILLE"),
    ]:
        section = results.get(section_key, {})
        pairs = section.get("organes_pairs", {})
        if not pairs:
            continue
        lines.append(f"ORGANES {title}")
        lines.append("-" * 50)
        for key, o in pairs.items():
            if key.startswith("_"):
                lines.append(
                    f"  DS poole {key[1:].replace('_pooled', '')} : "
                    f"{o['ds_pooled']:+.2f}  (D: {o['ds_d']:+.2f}, G: {o['ds_g']:+.2f})  "
                    f"[{o['interpretation']}]"
                )
            else:
                ds_str = f"{o['ds']:+.2f} DS" if o.get("ds") is not None else "—"
                lines.append(
                    f"  {o['label']:20s} : {o['valeur']:8.2f} g  "
                    f"(moy: {o['moyenne']:.1f}, sd: {o['sd']:.1f})  ->  {ds_str}"
                )
        lines.append("")

    ratios = results.get("ratios", {})
    if ratios:
        lines.append("RATIOS ORGANE / MASSE CORPORELLE")
        lines.append("-" * 50)
        for key, r in ratios.items():
            lines.append(f"  {r['label']:20s} : {r['masse_organe']:.2f} g  ->  {r['pourcentage']:.2f}%")
        lines.append("")

    alertes = results.get("alertes", [])
    if alertes:
        lines.append("!! ALERTES")
        lines.append("-" * 30)
        for a in alertes:
            lines.append(f"  * {a}")

    return "\n".join(lines)
