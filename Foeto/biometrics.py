#!/usr/bin/env python3
"""
FoetoPath — Moteur de calcul biométrique.

Classes :
  - OrganExtractor : extraction des masses depuis le JSON macro_autopsie
  - DSCalculator   : calcul des DS par rapport aux références
  - RatioCalculator: ratios organe/masse corporelle + LBWR
  - ReportRenderer : génération du texte via Jinja2

Les données de référence sont dans reference_data.py (séparé pour maintenance).
"""

import json
import math
from typing import Any, Optional

from reference_data import (
    GC_MACRO, GC_ORGANES,
    GC_POUMON_INDIVIDUEL, GC_REIN_INDIVIDUEL, GC_SURRENALE_INDIVIDUELLE,
    MAROUN,
    ORGAN_LABELS, BIO_LABELS,
)


# ══════════════════════════════════════════════════════════════════════════
# Utilitaires
# ══════════════════════════════════════════════════════════════════════════

def sa_to_gc_class(sa: int) -> Optional[str]:
    """Convertit un terme SA en classe bi-hebdomadaire Guihard-Costa."""
    if sa < 13:
        return None
    for low in range(13, 42, 2):
        if low <= sa <= low + 1:
            return f"{low}-{low + 1}"
    return None


def calc_ds(value: float, moy: float, sd: float) -> Optional[float]:
    """Calcule l'écart en déviations standard."""
    if sd == 0 or value is None or moy is None:
        return None
    return round((value - moy) / sd, 2)


def pooled_ds(ds_d: float, ds_g: float) -> float:
    """DS combiné pour organes pairs : signe(moyenne) * √(mean(ds²))."""
    mean_ds = (ds_d + ds_g) / 2
    rms = math.sqrt((ds_d**2 + ds_g**2) / 2)
    return round(math.copysign(rms, mean_ds), 2)


def interpret_ds(ds: Optional[float]) -> str:
    if ds is None:
        return "non calculable"
    a = abs(ds)
    if a <= 1:
        return "normal"
    direction = "augmenté" if ds > 0 else "diminué"
    if a <= 2:
        return f"modérément {direction}"
    return f"significativement {direction}"


# ══════════════════════════════════════════════════════════════════════════
# OrganExtractor
# ══════════════════════════════════════════════════════════════════════════

class OrganExtractor:
    """
    Navigue la structure du JSON macro_autopsie et extrait les masses.

    Propriétés :
      .masses           → tout (individuels + combinés), sans None
      .combined         → organes uniques + sommes D+G
      .individual_pairs → uniquement les D/G séparés
    """

    def __init__(self, data: dict):
        self.data = data
        self._m = {}
        self._extract()

    @staticmethod
    def _get(obj, *keys):
        for k in keys:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(k)
        return obj

    @staticmethod
    def _f(val):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _extract(self):
        d = self.data
        m = self._m
        _g, _f = self._get, self._f

        # Organes uniques
        m["coeur"]    = _f(_g(d, "coeur", "masse"))
        m["thymus"]   = _f(_g(d, "thorax", "thymus", "masse"))
        m["foie"]     = _f(_g(d, "digestif", "foie", "masse"))
        m["rate"]     = _f(_g(d, "digestif", "rate", "masse"))
        m["pancreas"] = _f(_g(d, "digestif", "pancreas", "masse"))
        m["cerveau"]  = _f(_g(d, "neuro", "masse_cerveau"))

        # Organes pairs
        m["poumon_d"]     = _f(_g(d, "poumons", "masse_d"))
        m["poumon_g"]     = _f(_g(d, "poumons", "masse_g"))
        m["rein_d"]       = _f(_g(d, "retroperitoine", "reins", "masse_d"))
        m["rein_g"]       = _f(_g(d, "retroperitoine", "reins", "masse_g"))
        m["surrenale_d"]  = _f(_g(d, "retroperitoine", "surrenales", "masse_d"))
        m["surrenale_g"]  = _f(_g(d, "retroperitoine", "surrenales", "masse_g"))

        # Sommes D+G
        for combined, k_d, k_g in [
            ("poumons",     "poumon_d",    "poumon_g"),
            ("reins",       "rein_d",      "rein_g"),
            ("surrenales",  "surrenale_d", "surrenale_g"),
        ]:
            vd, vg = m.get(k_d), m.get(k_g)
            if vd is not None and vg is not None:
                m[combined] = round(vd + vg, 2)
            elif vd is not None:
                m[combined] = vd
            elif vg is not None:
                m[combined] = vg

    @property
    def masses(self) -> dict:
        return {k: v for k, v in self._m.items() if v is not None}

    @property
    def combined(self) -> dict:
        keys = {"coeur", "thymus", "poumons", "foie", "rate", "pancreas",
                "surrenales", "reins", "cerveau"}
        return {k: v for k, v in self._m.items() if k in keys and v is not None}

    @property
    def individual_pairs(self) -> dict:
        keys = {"poumon_d", "poumon_g", "rein_d", "rein_g",
                "surrenale_d", "surrenale_g"}
        return {k: v for k, v in self._m.items() if k in keys and v is not None}


# ══════════════════════════════════════════════════════════════════════════
# DSCalculator
# ══════════════════════════════════════════════════════════════════════════

class DSCalculator:

    def __init__(self, terme_sa: int):
        self.terme_sa = terme_sa
        self.gc_class = sa_to_gc_class(terme_sa)

    # ── Biométries corporelles ──
    def biometries(self, macro_frais: dict) -> dict:
        if not self.gc_class or self.gc_class not in GC_MACRO:
            return {"error": f"Pas de données GC pour {self.terme_sa} SA"}

        ref = GC_MACRO[self.gc_class]
        bio = macro_frais.get("biometries", macro_frais.get("biometrie", macro_frais))

        field_map = {"masse": "masse", "vt": "VT", "vc": "VC", "pc": "PC", "pied": "pied"}
        mesures = {}

        for app_key, gc_key in field_map.items():
            val = bio.get(app_key)
            if val is not None and gc_key in ref:
                r = ref[gc_key]
                ds = calc_ds(float(val), r["moy"], r["sd"])
                mesures[gc_key] = {
                    "valeur": float(val),
                    "moyenne": r["moy"], "sd": r["sd"],
                    "ds": ds, "interpretation": interpret_ds(ds),
                    "unite": "g" if gc_key == "masse" else "mm",
                }

        return {"reference": "Guihard-Costa 2002", "classe": self.gc_class, "mesures": mesures}

    # ── Organes combinés D+G ──
    def organes_combines(self, extractor: OrganExtractor) -> dict:
        if not self.gc_class or self.gc_class not in GC_ORGANES:
            return {"error": f"Pas de données GC organes pour {self.terme_sa} SA"}

        ref = GC_ORGANES[self.gc_class]
        organes = {}

        for key, masse in extractor.combined.items():
            if key in ref:
                r = ref[key]
                ds = calc_ds(masse, r["moy"], r["sd"])
                organes[key] = {
                    "valeur": masse,
                    "label": ORGAN_LABELS.get(key, key),
                    "moyenne": r["moy"], "sd": r["sd"],
                    "ds": ds, "interpretation": interpret_ds(ds),
                    "unite": "g",
                }

        return {"reference": "Guihard-Costa 2002", "classe": self.gc_class, "organes": organes}

    # ── Organes pairs individuels D / G ──
    def organes_individuels(self, extractor: OrganExtractor) -> dict:
        if not self.gc_class:
            return {}

        pair_tables = {
            "poumon":    GC_POUMON_INDIVIDUEL,
            "rein":      GC_REIN_INDIVIDUEL,
            "surrenale": GC_SURRENALE_INDIVIDUELLE,
        }

        organes_pairs = {}
        pairs = extractor.individual_pairs

        for base, ref_table in pair_tables.items():
            if self.gc_class not in ref_table:
                continue

            r = ref_table[self.gc_class]
            key_d, key_g = f"{base}_d", f"{base}_g"
            val_d, val_g = pairs.get(key_d), pairs.get(key_g)

            ds_d_val, ds_g_val = None, None

            for key, val, side in [(key_d, val_d, "D"), (key_g, val_g, "G")]:
                if val is not None:
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
                        "ref_note": "dérivé (moy/2, sd/√2)",
                    }

            # DS poolé
            if ds_d_val is not None and ds_g_val is not None:
                ds_p = pooled_ds(ds_d_val, ds_g_val)
                combined_key = f"{base}s" if base != "surrenale" else "surrenales"
                organes_pairs[f"_{combined_key}_pooled"] = {
                    "ds_d": ds_d_val, "ds_g": ds_g_val,
                    "ds_pooled": ds_p,
                    "interpretation": interpret_ds(ds_p),
                    "method": "√(mean(ds²))",
                }

        return {"reference": "Guihard-Costa 2002 (dérivé)", "organes_pairs": organes_pairs}

    # ── Organes Maroun (stratifié par macération) ──
    def organes_maroun(self, extractor: OrganExtractor, maceration_grade: int = 0) -> dict:
        ref_sa = MAROUN.get(self.terme_sa)
        if not ref_sa:
            return {"error": f"Pas de données Maroun pour {self.terme_sa} SA"}

        g = maceration_grade
        grade_01_2_3 = "0 1" if g <= 1 else ("2" if g == 2 else "3")
        grade_01_23 = "0 1" if g <= 1 else "2 3"

        organ_map = {
            "cerveau":     ("brain",    None),
            "coeur":       ("heart",    None),
            "foie":        ("liver",    grade_01_2_3),
            "thymus":      ("thymus",   grade_01_2_3),
            "poumons":     ("lungs",    grade_01_23),
            "rate":        ("spleen",   grade_01_23),
            "reins":       ("kidneys",  grade_01_23),
            "surrenales":  ("adrenals", grade_01_23),
        }

        mean = ref_sa["Mean"]
        sd = ref_sa["SD"]
        organes = {}

        for fr_key, masse in extractor.combined.items():
            if fr_key not in organ_map:
                continue
            en_base, suffix = organ_map[fr_key]
            maroun_key = f"{en_base} {suffix}" if suffix else en_base
            m, s = mean.get(maroun_key), sd.get(maroun_key)
            if m is None or s is None:
                continue
            ds = calc_ds(masse, m, s)
            organes[fr_key] = {
                "valeur": masse,
                "label": ORGAN_LABELS.get(fr_key, fr_key),
                "moyenne": m, "sd": s,
                "ds": ds, "interpretation": interpret_ds(ds),
                "unite": "g",
                "maroun_key": maroun_key,
            }

        return {
            "reference": "Maroun 2017",
            "terme_sa": self.terme_sa,
            "maceration_grade": maceration_grade,
            "organes": organes,
        }


# ══════════════════════════════════════════════════════════════════════════
# RatioCalculator
# ══════════════════════════════════════════════════════════════════════════

class RatioCalculator:

    def __init__(self, masse_corporelle: float, terme_sa: int = 0):
        self.masse = masse_corporelle
        self.terme_sa = terme_sa

    def compute(self, extractor: OrganExtractor) -> dict:
        if not self.masse or self.masse <= 0:
            return {"error": "Masse corporelle non disponible"}

        ratios = {}
        for key, masse in extractor.combined.items():
            label = ORGAN_LABELS.get(key, key)
            ratio = round(masse / self.masse, 4)
            ratios[key] = {
                "label": label, "masse_organe": masse,
                "ratio": ratio, "pourcentage": round(ratio * 100, 2),
            }

        # LBWR
        poumons = extractor.combined.get("poumons")
        lbwr, lbwr_alert = None, None
        if poumons is not None:
            lbwr = round(poumons / self.masse, 4)
            threshold = 0.012 if self.terme_sa < 28 else 0.015
            if lbwr < threshold:
                lbwr_alert = f"Hypoplasie pulmonaire (LBWR {lbwr:.4f} < {threshold})"

        ratios["_lbwr"] = {"label": "LBWR (De Paepe)", "valeur": lbwr, "alerte": lbwr_alert}
        return ratios


# ══════════════════════════════════════════════════════════════════════════
# Fonction principale
# ══════════════════════════════════════════════════════════════════════════

def compute_all(terme_sa: int, macro_frais: dict = None, macro_autopsie: dict = None,
                maceration_grade: int = 0) -> dict:
    calc = DSCalculator(terme_sa)
    results = {
        "terme_sa": terme_sa,
        "maceration_grade": maceration_grade,
        "gc_classe": calc.gc_class,
        "biometries_gc": {},
        "organes_gc": {},
        "organes_maroun": {},
        "organes_individuels": {},
        "ratios": {},
        "alertes": [],
    }

    if macro_frais:
        results["biometries_gc"] = calc.biometries(macro_frais)

    if macro_autopsie:
        extractor = OrganExtractor(macro_autopsie)
        results["organes_gc"] = calc.organes_combines(extractor)
        results["organes_maroun"] = calc.organes_maroun(extractor, maceration_grade)
        results["organes_individuels"] = calc.organes_individuels(extractor)

        masse = None
        if macro_frais:
            bio = macro_frais.get("biometries", macro_frais.get("biometrie", {}))
            masse = bio.get("masse")
        if masse:
            results["ratios"] = RatioCalculator(float(masse), terme_sa).compute(extractor)

    # Alertes
    lbwr = results.get("ratios", {}).get("_lbwr", {})
    if lbwr.get("alerte"):
        results["alertes"].append(lbwr["alerte"])

    for key, val in results.get("organes_maroun", {}).get("organes", {}).items():
        if val.get("ds") is not None and abs(val["ds"]) > 2:
            results["alertes"].append(f"{val.get('label', key)} (Maroun) : {val['ds']:+.1f} DS ({val['interpretation']})")

    for key, val in results.get("organes_gc", {}).get("organes", {}).items():
        if val.get("ds") is not None and abs(val["ds"]) > 2:
            results["alertes"].append(f"{val.get('label', key)} : {val['ds']:+.1f} DS ({val['interpretation']})")

    for key, val in results.get("organes_individuels", {}).get("organes_pairs", {}).items():
        if key.startswith("_"):
            continue
        if val.get("ds") is not None and abs(val["ds"]) > 2:
            results["alertes"].append(f"{val.get('label', key)} : {val['ds']:+.1f} DS ({val['interpretation']})")

    for key, val in results.get("biometries_gc", {}).get("mesures", {}).items():
        if val.get("ds") is not None and abs(val["ds"]) > 2:
            results["alertes"].append(f"{key} : {val['ds']:+.1f} DS ({val['interpretation']})")

    return results


# ══════════════════════════════════════════════════════════════════════════
# Template Jinja2
# ══════════════════════════════════════════════════════════════════════════

REPORT_TEMPLATE = """\
EXAMEN FŒTOPATHOLOGIQUE — BIOMÉTRIES ET MASSES D'ORGANES
=========================================================
Terme : {{ terme_sa }} SA | Classe GC : {{ gc_classe or 'N/A' }}
{% if maceration_grade %}Score de macération (Maroun) : {{ maceration_grade }}{% endif %}

{% if biometries_gc and biometries_gc.mesures %}
BIOMÉTRIES CORPORELLES (réf. Guihard-Costa 2002)
-------------------------------------------------
{% for key, m in biometries_gc.mesures.items() %}
{{ "%-12s"|format(key) }} : {{ "%8.1f"|format(m.valeur) }} {{ m.unite }}  (moy: {{ "%.1f"|format(m.moyenne) }}, sd: {{ "%.1f"|format(m.sd) }})  →  {{ "%+.2f"|format(m.ds) }} DS  [{{ m.interpretation }}]
{% endfor %}
{% endif %}
{% if organes_maroun and organes_maroun.organes %}

MASSES D'ORGANES — MAROUN 2017 (macération {{ maceration_grade }})
-------------------------------------------------------------------
{% for key, o in organes_maroun.organes.items() %}
{{ "%-18s"|format(o.label) }} : {{ "%8.2f"|format(o.valeur) }} g  (moy: {{ "%.2f"|format(o.moyenne) }}, sd: {{ "%.2f"|format(o.sd) }})  →  {{ "%+.2f"|format(o.ds) }} DS  [{{ o.interpretation }}]
{% endfor %}
{% endif %}
{% if organes_gc and organes_gc.organes %}

MASSES D'ORGANES — COMBINÉS (réf. Guihard-Costa 2002)
-------------------------------------------------------
{% for key, o in organes_gc.organes.items() %}
{{ "%-18s"|format(o.label) }} : {{ "%8.2f"|format(o.valeur) }} g  (moy: {{ "%.2f"|format(o.moyenne) }}, sd: {{ "%.2f"|format(o.sd) }})  →  {{ "%+.2f"|format(o.ds) }} DS  [{{ o.interpretation }}]
{% endfor %}
{% endif %}
{% if organes_individuels and organes_individuels.organes_pairs %}

MASSES D'ORGANES — PAIRS INDIVIDUELS (réf. dérivée GC : moy/2, sd/√2)
------------------------------------------------------------------------
{% for key, o in organes_individuels.organes_pairs.items() if not key.startswith('_') %}
{{ "%-18s"|format(o.label) }} : {{ "%8.2f"|format(o.valeur) }} g  (moy: {{ "%.2f"|format(o.moyenne) }}, sd: {{ "%.2f"|format(o.sd) }})  →  {{ "%+.2f"|format(o.ds) }} DS  [{{ o.interpretation }}]
{% endfor %}
{% for key, o in organes_individuels.organes_pairs.items() if key.startswith('_') %}
  DS poolé {{ key[1:].replace('_pooled','') }} : {{ "%+.2f"|format(o.ds_pooled) }}  (D: {{ "%+.2f"|format(o.ds_d) }}, G: {{ "%+.2f"|format(o.ds_g) }})  [{{ o.interpretation }}]  — méthode : {{ o.method }}
{% endfor %}
{% endif %}
{% if ratios and ratios.keys()|list|length > 1 %}

RATIOS ORGANE / MASSE CORPORELLE
----------------------------------
{% for key, r in ratios.items() if not key.startswith('_') %}
{{ "%-18s"|format(r.label) }} : {{ "%.2f"|format(r.masse_organe) }} g  →  {{ "%.2f"|format(r.pourcentage) }}%
{% endfor %}
{% if ratios._lbwr and ratios._lbwr.valeur %}
LBWR (De Paepe) : {{ "%.4f"|format(ratios._lbwr.valeur) }}{% if ratios._lbwr.alerte %}  ⚠ {{ ratios._lbwr.alerte }}{% endif %}
{% endif %}
{% endif %}
{% if alertes %}

⚠ ALERTES
----------
{% for a in alertes %}
• {{ a }}
{% endfor %}
{% endif %}
"""


def render_report(results: dict) -> str:
    try:
        from jinja2 import Template
    except ImportError:
        return json.dumps(results, indent=2, ensure_ascii=False)
    return Template(REPORT_TEMPLATE).render(**results)
