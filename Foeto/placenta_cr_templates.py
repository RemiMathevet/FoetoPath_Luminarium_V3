#!/usr/bin/env python3
"""
FoetoPath — Templates Jinja2 pour les comptes-rendus placentaires.

Templates disponibles :
  - standard  : CR placentaire standard (Amsterdam + FIPN)
  - court     : CR synthétique court

Chaque template reçoit un contexte construit par build_cr_context()
à partir des données du cas placenta (admin + modules).
"""

import logging
import os
import re
import sqlite3

from cr_helpers import (
    get_available_templates as _get_templates,
    get_template_changelog as _get_changelog,
    get_all_versions_info as _get_versions,
    render_cr as _render,
)

log = logging.getLogger(__name__)

from config import FOETO_DB_PATH as _FOETO_DB
_foeto_cr_cache: tuple | None = None
_GRADE_SUFFIX = re.compile(r"\.G\d+$")


def _load_foeto_cr():
    """(by_id, by_vid, sections) depuis foeto_base — dispatch CR DB-driven, caché."""
    global _foeto_cr_cache
    if _foeto_cr_cache is not None:
        return _foeto_cr_cache
    by_id, by_vid, sections = {}, {}, []
    if os.path.exists(_FOETO_DB):
        conn = sqlite3.connect(f"file:{_FOETO_DB}?mode=ro", uri=True)
        for tid, vid, desc, sec in conn.execute(
            "SELECT id, viewer_id, cr_description, cr_section FROM foeto_terms "
            "WHERE cr_section IS NOT NULL AND cr_description IS NOT NULL "
            "AND cr_description != ''"
        ):
            val = (desc, sec)
            if tid:
                by_id[tid] = val
            if vid:
                by_vid[vid] = val
        sections = conn.execute(
            "SELECT name, label_fr, texte_normal FROM foeto_structures "
            "WHERE type='cr_section' AND domain='placenta' ORDER BY sort_order"
        ).fetchall()
        conn.close()
    _foeto_cr_cache = (by_id, by_vid, sections)
    return _foeto_cr_cache


def _resolve_viewer_sign(token: str):
    """Token viewer → (cr_description, cr_section) ou None (STRUCT/legacy ignorés)."""
    t = (token or "").strip()
    if not t or t.startswith("STRUCT:"):
        return None
    by_id, by_vid, _ = _load_foeto_cr()
    base = _GRADE_SUFFIX.sub("", t)
    return by_id.get(base) or by_vid.get(t) or by_vid.get(base)


# ══════════════════════════════════════════════════════════════════════════
# Données de référence Redline (masse placentaire)
# ══════════════════════════════════════════════════════════════════════════

DONNEES_PLACENTA = {
    18: {"moyenne": 107, "sd": 23, "P10": 52, "P50": 89, "P90": 181, "source": "Extrapol"},
    19: {"moyenne": 113, "sd": 25, "P10": 56, "P50": 94, "P90": 196, "source": "Extrapol"},
    20: {"moyenne": 130, "sd": 26, "P10": 82, "P50": 110, "P90": 214, "source": "Extrapol"},
    21: {"moyenne": 150, "sd": 25, "P10": 95, "P50": 130, "P90": 230, "source": "Extrapol"},
    22: {"moyenne": 189, "sd": 89, "P10": 107, "P50": 166, "P90": 285, "source": "Redline"},
    23: {"moyenne": 190, "sd": 41, "P10": 127, "P50": 188, "P90": 262, "source": "Redline"},
    24: {"moyenne": 190, "sd": 42, "P10": 128, "P50": 192, "P90": 252, "source": "Redline"},
    25: {"moyenne": 197, "sd": 70, "P10": 128, "P50": 184, "P90": 299, "source": "Redline"},
    26: {"moyenne": 226, "sd": 100, "P10": 138, "P50": 200, "P90": 281, "source": "Redline"},
    27: {"moyenne": 240, "sd": 77, "P10": 130, "P50": 242, "P90": 332, "source": "Redline"},
    28: {"moyenne": 223, "sd": 66, "P10": 140, "P50": 214, "P90": 321, "source": "Redline"},
    29: {"moyenne": 269, "sd": 96, "P10": 161, "P50": 252, "P90": 352, "source": "Redline"},
    30: {"moyenne": 324, "sd": 88, "P10": 208, "P50": 316, "P90": 433, "source": "Redline"},
    31: {"moyenne": 314, "sd": 105, "P10": 175, "P50": 313, "P90": 417, "source": "Redline"},
    32: {"moyenne": 325, "sd": 77, "P10": 241, "P50": 318, "P90": 436, "source": "Redline"},
    33: {"moyenne": 351, "sd": 83, "P10": 252, "P50": 352, "P90": 446, "source": "Redline"},
    34: {"moyenne": 381, "sd": 84, "P10": 283, "P50": 382, "P90": 479, "source": "Redline"},
    35: {"moyenne": 411, "sd": 99, "P10": 291, "P50": 401, "P90": 544, "source": "Redline"},
    36: {"moyenne": 447, "sd": 110, "P10": 320, "P50": 440, "P90": 580, "source": "Redline"},
    37: {"moyenne": 467, "sd": 107, "P10": 349, "P50": 452, "P90": 607, "source": "Redline"},
    38: {"moyenne": 493, "sd": 103, "P10": 365, "P50": 484, "P90": 629, "source": "Redline"},
    39: {"moyenne": 500, "sd": 103, "P10": 379, "P50": 490, "P90": 635, "source": "Redline"},
    40: {"moyenne": 510, "sd": 100, "P10": 390, "P50": 501, "P90": 643, "source": "Redline"},
    41: {"moyenne": 524, "sd": 100, "P10": 403, "P50": 515, "P90": 655, "source": "Redline"},
    42: {"moyenne": 532, "sd": 99, "P10": 412, "P50": 525, "P90": 658, "source": "Redline"},
}

RATIO_FP = {
    21: {"moy": 2.64, "sd": 0.8}, 22: {"moy": 2.97, "sd": 0.8}, 23: {"moy": 3.3, "sd": 0.7},
    24: {"moy": 3.4, "sd": 1.0}, 25: {"moy": 4.0, "sd": 1.4}, 26: {"moy": 4.1, "sd": 1.2},
    27: {"moy": 4.5, "sd": 1.1}, 28: {"moy": 4.8, "sd": 1.0}, 29: {"moy": 5.2, "sd": 1.4},
    30: {"moy": 5.2, "sd": 1.1}, 31: {"moy": 5.5, "sd": 1.1}, 32: {"moy": 5.9, "sd": 1.2},
    33: {"moy": 6.0, "sd": 1.1}, 34: {"moy": 6.2, "sd": 1.0}, 35: {"moy": 6.4, "sd": 1.2},
    36: {"moy": 6.6, "sd": 1.1}, 37: {"moy": 6.8, "sd": 1.1}, 38: {"moy": 6.9, "sd": 1.1},
    39: {"moy": 7.1, "sd": 1.1}, 40: {"moy": 7.2, "sd": 1.1}, 41: {"moy": 7.2, "sd": 1.1},
    42: {"moy": 7.1, "sd": 1.1},
}

# Descriptions textuelles pour le CR micro
MICRO_DESCRIPTIONS = {
    "cordon_vx": {
        "3": "Le cordon présente 3 vaisseaux sur chacune de ses coupes.",
        "2": "Le cordon ne compte que deux vaisseaux sur chacune de ses coupes.",
    },
    "cordon_rif": {
        "0": "Absence de processus inflammatoire funiculaire.",
        "1": "On note la présence d'une inflammation polynucléaire neutrophile de la média de la veine ombilicale (RIF stade 1).",
        "2": "On note la présence d'une inflammation polynucléaire neutrophile de la média de la veine ombilicale et d'une artère ombilicale (RIF stade 2).",
        "3": "On note la présence d'une inflammation polynucléaire neutrophile de la média des 3 vaisseaux (RIF stade 3).",
    },
    "cordon_mavm": "On note une nécrose des myocytes de la média de l'un des vaisseaux (MAVM).",
    "memb_mfm": "Les membranes présentent quelques macrophages chargés de méconium épars au chorion.",
    "memb_mfm_plus": "Les membranes présentent de très nombreux macrophages chargés de méconium au chorion.",
    "memb_chorio1": "Les membranes présentent un infiltrat inflammatoire à PNN de la décidue sans extension au chorion ni nécrose de l'amnios (chorioamniotite stade 1).",
    "memb_chorio2": "Les membranes présentent un infiltrat inflammatoire à PNN de la décidue avec extensions au chorion sans nécrose de l'amnios (chorioamniotite stade 2).",
    "memb_chorio3": "Les membranes présentent un infiltrat inflammatoire à PNN de la décidue et du chorion avec nécrose de l'amnios (chorioamniotite stade 3).",
    "memb_neclamdec": "La décidue capsulaire présente de multiples plages de nécrose basale.",
    "memb_decchro": "On note la présence de quelques plasmocytes au sein de la décidue basale (déciduite chronique).",
    "memb_decchro_plus": "On note la présence de nombreux plasmocytes au sein de la décidue basale (déciduite chronique sévère).",
    "memb_sg": "Le chorion cellulaire est disséqué du chorion fibreux par de multiples effusions de sang frais.",
    "memb_sidero": "La décidue capsulaire présente de multiples sidérophages.",
    "pcho_chorio1": "Le toit de la chambre intervilleuse présente un infiltrat inflammatoire à PNN englué de fibrine, sans extension au chorion.",
    "pcho_chorio2": "Le toit de la chambre intervilleuse présente un infiltrat à PNN avec extensions au chorion.",
    "pcho_chorio3": "Le toit de la chambre intervilleuse présente un infiltrat à PNN avec extensions au chorion et nécrose.",
    "pcho_rif_allanto": "On note un infiltrat à PNN au sein de la média de quelques gros vaisseaux allanto-choriaux.",
    "villo_amv": "On note de multiples plages d'hypoplasie villositaire distale avec accélération de la maturation villositaire (AMV).",
    "villo_ansct": "On note une augmentation diffuse du nombre d'amas nucléaires syncytiotrophoblastiques (ANSCT).",
    "villo_hvd": "On note de multiples plages d'hypoplasie villositaire distale (HVD).",
    "villo_chorangio": "On note de multiples foyers de villosités distales hypervascularisées (chorangiose).",
    "villo_kit": "On note la présence de kystes d'inclusion trophoblastiques au sein du stroma de quelques villosités (KIT).",
    "villo_vtf": "On note de multiples foyers de villosités complètement sclérosées (VTF).",
    "villo_vue_bg": "On note de multiples foyers de moins de 10 villosités avec infiltrat lympho-histiocytaire (VUE bas grade).",
    "villo_vue_hg": "On note de multiples foyers de plus de 10 villosités avec infiltrat lympho-histiocytaire (VUE haut grade).",
    "villo_caryovs": "De multiples villosités présentent une caryorrhexie vaso-stromale.",
    "eiv_fibpv": "La fibrine périvillositaire est diffusément augmentée.",
    "eiv_nidf": "On note la présence de multiples travées NIDF.",
    "eiv_chi": "L'espace intervilleux présente une inflammation histiocytaire diffuse (CHI).",
    "eiv_calcif": "On note une augmentation diffuse du nombre de calcifications.",
    "pbas_artodec": "On note une nécrose fibrinoïde de la média de quelques artères utéro-placentaires (artérite décidue).",
    "pbas_decchro": "La plaque basale présente de multiples plasmocytes épars (déciduite chronique).",
    "pbas_abruptus": "La plaque basale est déchirée par de multiples petites effusions de sang frais (abruptus).",
}

# Labels pour les tissus normaux (quand aucune anomalie n'est cochée)
MICRO_NORMAL = {
    "cordon": "Le cordon est sans particularité histologique.",
    "membranes": "Les membranes sont sans particularité histologique.",
    "plaque_choriale": "La plaque choriale et les vaisseaux allanto-choriaux sont sans particularité.",
    "villosites": "Les villosités sont de maturation conforme au terme, de morphologie normale.",
    "espace_intervilleux": "L'espace intervilleux est libre d'inflammation, les globules rouges maternels sont de morphologie normale.",
    "plaque_basale": "La plaque basale est sans particularité.",
}

# Tissue labels for display
TISSUE_LABELS = {
    "cordon": "Cordon",
    "membranes": "Membranes",
    "plaque_choriale": "Plaque choriale",
    "villosites": "Villosités",
    "espace_intervilleux": "Espace intervilleux",
    "plaque_basale": "Plaque basale",
}


ANN_CLASS_TO_DIAG_KEY = {
    "chorio_1": "chorio 1",
    "chorio_2": "chorio 2",
    "chorio_3": "chorio 3",
    "rif_1": "rif 1",
    "rif_2": "rif 2",
    "rif_3": "rif 3",
    "chorioamniotite": "chorio",
    "fibrine": "fib pv augmentée",
    "calcification": "calcifs",
    "chorangiose": "chorangiose",
    "nidf": "nidf",
    "arteriopathie": "art dec",
    "hrp": "abruptus",
    "plasmocyte": "dec chro",
    "villosite_term": "vue bg",
    "villite": "vue bg",
    "intervillite": "chi",
    "schizocytes_maternels": "schizocytes maternels",
}

# Le dispatch tissu/compartiment -> section CR est porte par
# foeto_terms.cr_section (source de verite DB), consomme ci-dessous.

_CR_SECTION_ORGAN = {"cr_cordon": "cordon", "cr_membranes": "membranes"}


def build_viewer_micro_text(ann_data: dict) -> str:
    """Texte de microscopie systematique, DB-driven via foeto_terms.cr_section.

    Chaque token viewer (classe d'annotation ou diagnostic) est resolu vers sa
    section CR + description depuis foeto_base, puis dispatche dans les sections
    definies dans foeto_structures. Une section sans anomalie garde son texte
    normal. Les tokens legacy sans mapping FOETO sont ignores.
    """
    tissues_examined = set(ann_data.get("tissues_examined", []))
    if not tissues_examined:
        return ""

    _, _, sections = _load_foeto_cr()
    if not sections:
        return ""

    by_tissue = ann_data.get("annotations_by_tissue", {})
    diag_by_tissue = ann_data.get("diagnoses_by_tissue", {})

    sec_findings: dict[str, list[dict]] = {}

    def _add(token, count, nslides):
        res = _resolve_viewer_sign(token)
        if not res:
            return
        desc, sec = res
        bucket = sec_findings.setdefault(sec, [])
        for f in bucket:
            if f["text"] == desc:
                f["count"] += count
                f["nslides"] += nslides
                return
        bucket.append({"text": desc, "count": count, "nslides": nslides})

    for anns in by_tissue.values():
        for cls, info in anns.items():
            _add(cls, info.get("count", 1), len(info.get("slides", [])) or 1)
    for diags in diag_by_tissue.values():
        for d in diags:
            _add(d, 1, 1)

    lines = []
    for name, label, texte_normal in sections:
        req_organ = _CR_SECTION_ORGAN.get(name, "parenchyme")
        if req_organ not in tissues_examined:
            continue
        findings = sec_findings.get(name, [])
        if findings:
            parts = []
            for f in findings:
                if f["count"] > 1:
                    parts.append(
                        f"{f['text'].rstrip('.')} "
                        f"({f['count']} annotations sur {f['nslides']} lame(s))."
                    )
                else:
                    parts.append(f["text"])
            lines.append(f"{label} : {' '.join(parts)}")
        else:
            lines.append(f"{label} : {texte_normal}")

    return "\n".join(lines)


DIAG_FAMILY = {
    "chorio 1": ("chorio", 1), "chorio 2": ("chorio", 2), "chorio 3": ("chorio", 3),
    "rif 1": ("rif", 1), "rif 2": ("rif", 2), "rif 3": ("rif", 3),
    "vue bg": ("vue", 1), "vue hg": ("vue", 2),
}

FAMILY_CONCLUSION_TEXT = {
    ("chorio", 1): "Chorioamniotite aiguë de stade 1",
    ("chorio", 2): "Chorioamniotite aiguë de stade 2",
    ("chorio", 3): "Chorioamniotite aiguë de stade 3",
    ("rif", 1): "Réponse inflammatoire fœtale de stade 1",
    ("rif", 2): "Réponse inflammatoire fœtale de stade 2",
    ("rif", 3): "Réponse inflammatoire fœtale de stade 3",
    ("vue", 1): "Villite d'étiologie indéterminée de bas grade",
    ("vue", 2): "Villite d'étiologie indéterminée de haut grade",
}

STANDALONE_CONCLUSION_TEXT = {
    "art dec": "Artériopathie déciduale",
    "calcifs": "Calcifications augmentées",
    "hvd": "Hypoplasie villositaire distale",
    "fib pv augmentée": "Fibrine périvillositaire augmentée",
    "amv": "Accélération de la maturation villositaire",
    "ansct": "Augmentation des amas nucléaires syncytiotrophoblastiques",
    "chorangiose": "Chorangiose",
    "vtf": "Vasculopathie thrombotique fœtale",
    "chi": "Intervillite histiocytaire chronique",
    "nidf": "NIDF",
    "abruptus": "Abruptus",
    "dec chro": "Déciduite chronique",
    "nécrose laminaire déciduale": "Nécrose laminaire déciduale",
}

RECURRENT_TREATABLE = {
    "villite": {"vue", "vue bg", "vue hg"},
    "intervillite": {"chi"},
    "déciduite chronique": {"dec chro"},
    "vasculopathie thrombotique fœtale": {"vtf"},
    "artériopathie déciduale": {"art dec"},
}


def build_viewer_conclusion_items(ann_data: dict) -> str:
    """Build synthetic conclusion lines from viewer diagnoses and annotations.

    Graded families (chorio, rif, vue): keep only max grade across all tissues.
    Standalone diagnoses: one line each.
    Annotations mapped via ANN_CLASS_TO_DIAG_KEY contribute to found keys.
    Ends with 'Absence de :' for recurrent treatable pathologies not found.
    """
    diag_by_tissue = ann_data.get("diagnoses_by_tissue", {})
    ann_by_tissue = ann_data.get("annotations_by_tissue", {})

    all_diag_keys: set[str] = set()
    family_max: dict[str, int] = {}
    standalone_seen: set[str] = set()

    for tissue_diags in diag_by_tissue.values():
        for d in tissue_diags:
            key = d.strip().lower()
            if key in ("normal", "normales", ""):
                continue
            all_diag_keys.add(key)
            fam = DIAG_FAMILY.get(key)
            if fam:
                family, grade = fam
                if grade > family_max.get(family, 0):
                    family_max[family] = grade
            elif key in STANDALONE_CONCLUSION_TEXT:
                standalone_seen.add(key)

    for tissue_anns in ann_by_tissue.values():
        for cls in tissue_anns:
            mapped = ANN_CLASS_TO_DIAG_KEY.get(cls)
            if not mapped:
                continue
            all_diag_keys.add(mapped)
            fam = DIAG_FAMILY.get(mapped)
            if fam:
                family, grade = fam
                if grade > family_max.get(family, 0):
                    family_max[family] = grade
            elif mapped in STANDALONE_CONCLUSION_TEXT:
                standalone_seen.add(mapped)

    lines: list[str] = []
    for (family, grade), text in FAMILY_CONCLUSION_TEXT.items():
        if family_max.get(family) == grade:
            lines.append(text)

    for key in STANDALONE_CONCLUSION_TEXT:
        if key in standalone_seen:
            lines.append(STANDALONE_CONCLUSION_TEXT[key])

    absent = [label for label, keys in RECURRENT_TREATABLE.items()
              if not keys & all_diag_keys]
    if absent:
        lines.append("")
        lines.append("")
        lines.append(f"Absence de : {', '.join(absent)}")

    return "\n".join(lines)


def compute_zscore(terme, masse, masse_foetale=None):
    """Calcule le Z-score de la masse placentaire."""
    result = {
        "masse_ds": None, "percentile": None, "trophicite": None,
        "ref": None, "extrapolated": False,
        "ratio_fp": None, "ratio_ds": None,
    }
    if not terme or not masse:
        return result
    ref = DONNEES_PLACENTA.get(int(terme))
    if not ref:
        return result
    result["ref"] = ref
    ds = (masse - ref["moyenne"]) / ref["sd"]
    result["masse_ds"] = round(ds, 2)
    result["extrapolated"] = ref["source"] == "Extrapol"

    if masse <= ref["P10"]:
        result["percentile"] = "< P10"
    elif masse <= ref["P50"]:
        result["percentile"] = "P10-P50"
    elif masse <= ref["P90"]:
        result["percentile"] = "P50-P90"
    else:
        result["percentile"] = "> P90"

    result["trophicite"] = "Hypotrophe" if ds < -1.67 else "Eutrophe"

    if masse_foetale and masse > 0:
        ratio = masse_foetale / masse
        result["ratio_fp"] = round(ratio, 2)
        rr = RATIO_FP.get(int(terme))
        if rr and rr.get("sd"):
            result["ratio_ds"] = round((ratio - rr["moy"]) / rr["sd"], 2)

    return result


def _item_to_tissue(item_id: str) -> str:
    """Détermine le tissu auquel appartient un item par son préfixe."""
    ITEM_TISSUE_MAP = {
        "cordon_": "cordon",
        "memb_": "membranes",
        "pcho_": "plaque_choriale",
        "villo_": "villosites",
        "eiv_": "espace_intervilleux",
        "pbas_": "plaque_basale",
    }
    for prefix, tissue in ITEM_TISSUE_MAP.items():
        if item_id.startswith(prefix):
            return tissue
    return ""


def build_micro_text(micro_lecture: dict) -> str:
    """Génère le texte microscopique à partir des données micro_lecture."""
    if not micro_lecture:
        return ""

    # Aggregate anomalies across all slides by tissue
    tissue_anomalies = {}  # tissue -> { item_id: { checked, severity, value } }
    all_tissues = set()

    for slide_key, slide_data in micro_lecture.items():
        tissues = slide_data.get("tissues", [])
        items = slide_data.get("items", {})
        for t in tissues:
            all_tissues.add(t)
        for item_id, item_data in items.items():
            if item_data.get("checked") or item_data.get("value"):
                # Map item to its correct tissue
                tissue = _item_to_tissue(item_id)
                if tissue and tissue in all_tissues:
                    if tissue not in tissue_anomalies:
                        tissue_anomalies[tissue] = {}
                    # Keep the most severe value across slides
                    existing = tissue_anomalies[tissue].get(item_id)
                    if not existing or (item_data.get("severity", 0) > existing.get("severity", 0)):
                        tissue_anomalies[tissue][item_id] = item_data

    if not all_tissues:
        return ""

    lines = []
    tissue_order = ["cordon", "membranes", "plaque_choriale", "villosites", "espace_intervilleux", "plaque_basale"]

    for tissue in tissue_order:
        if tissue not in all_tissues:
            continue
        anomalies = tissue_anomalies.get(tissue, {})
        # Filter out _normal items and check if "Normal" was explicitly checked
        normal_items = {k: v for k, v in anomalies.items() if k.endswith("_normal")}
        patho_items = {k: v for k, v in anomalies.items() if not k.endswith("_normal")}

        if not patho_items or normal_items:
            # Normal tissue (either no anomalies, or "Normal" explicitly checked)
            normal_text = MICRO_NORMAL.get(tissue)
            if normal_text:
                lines.append(normal_text)
            continue

        for item_id, item_data in patho_items.items():
            desc_entry = MICRO_DESCRIPTIONS.get(item_id)
            if not desc_entry:
                continue
            if isinstance(desc_entry, dict):
                # Radio type
                val = item_data.get("value", "")
                text = desc_entry.get(val, "")
            else:
                # Checkbox type
                text = desc_entry

            if text:
                sev = item_data.get("severity", 0)
                if sev and sev > 0:
                    if sev <= 25:
                        text += " De manière focale et discrète."
                    elif sev <= 50:
                        text += " De manière modérée."
                    elif sev <= 75:
                        text += " De manière marquée et étendue."
                    else:
                        text += " De manière massive et diffuse."
                lines.append(text)

    # Custom tissues
    for tissue in all_tissues:
        if tissue not in tissue_order and tissue in TISSUE_LABELS:
            continue  # already handled
        if tissue not in tissue_order:
            lines.append(f"Tissu personnalisé ({tissue}) : examiné.")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# Construction du contexte
# ══════════════════════════════════════════════════════════════════════════

def build_cr_context(case: dict, modules: dict, viewer_annotations: dict | None = None) -> dict:
    """
    Construit le contexte unifié pour les templates Jinja2 placenta.

    Args:
        case: données admin du cas (table placenta_cases)
        modules: dict {module_name: data} (tous les modules)
        viewer_annotations: données d'annotations du viewer Lumi (optionnel)

    Returns:
        Dict prêt à passer aux templates
    """
    macro_frais = modules.get("macro_frais", {})
    tranches = modules.get("tranches_section", {})

    terme = macro_frais.get("terme", {})
    foetus = macro_frais.get("foetus", {})
    bio = macro_frais.get("biometrie", {})
    cordon = macro_frais.get("cordon", {})
    membranes = macro_frais.get("membranes", {})

    # Fusionner données case + module (priorité module si existant)
    return {
        # Admin
        "numero": case.get("numero_dossier", ""),
        "statut": case.get("statut", "en_cours"),

        # Terme
        "terme_sa": terme.get("sa") or case.get("terme_sa"),
        "terme_j": terme.get("jours", 0) or case.get("terme_jours", 0),
        "terme_source": terme.get("source") or case.get("terme_source"),

        # Contexte fœtal
        "masse_foetale_g": foetus.get("masse_g") or case.get("masse_foetale_g"),
        "sexe": foetus.get("sexe") or case.get("sexe"),
        "indication_terme": foetus.get("indication_autre") or foetus.get("indication_terme") or case.get("indication_terme"),

        # Biométrie galette
        "grand_axe_cm": bio.get("grand_axe_cm") or case.get("grand_axe_cm"),
        "petit_axe_cm": bio.get("petit_axe_cm") or case.get("petit_axe_cm"),
        "epaisseur_cm": bio.get("epaisseur_cm") or case.get("epaisseur_cm"),
        "masse_paree_g": bio.get("masse_paree_g") or case.get("masse_paree_g"),

        # Descriptif
        "forme": macro_frais.get("forme") or case.get("forme"),
        "completude": macro_frais.get("completude") or case.get("completude", []),

        # Plaques
        "plaque_choriale": macro_frais.get("plaque_choriale") or case.get("plaque_choriale", {}),
        "plaque_basale": macro_frais.get("plaque_basale") or case.get("plaque_basale", {}),

        # Cordon
        "cordon": cordon if cordon else case.get("cordon", {}),

        # Membranes
        "membranes": membranes if membranes else case.get("membranes", {}),

        # Tranches de section
        "tranches": tranches,
        "nb_tranches_groups": len(tranches.get("tranche_groups", [])),
        "lesions": tranches.get("lesions", []),
        "tranches_commentaire": (tranches.get("commentaire") or "").strip(),

        # Photos
        "photos_frais": macro_frais.get("photos", []),
        "photos_tranches": tranches.get("photos", []),

        # Microscopie (grille de lecture)
        "micro_lecture": modules.get("micro_lecture", {}),
        "micro_text": build_micro_text(modules.get("micro_lecture", {})),

        # Z-score
        "zscore": compute_zscore(
            terme.get("sa") or case.get("terme_sa"),
            bio.get("masse_paree_g") or case.get("masse_paree_g"),
            foetus.get("masse_g") or case.get("masse_foetale_g"),
        ),

        # Annotations viewer (Lumi)
        "viewer_micro_text": build_viewer_micro_text(viewer_annotations) if viewer_annotations else "",
        "viewer_conclusion_items": build_viewer_conclusion_items(viewer_annotations) if viewer_annotations else "",
        "viewer_annotations": viewer_annotations or {},
    }


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _list_or_empty(val):
    """Retourne une liste à partir d'une valeur qui peut être str JSON, list, ou None."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            import json
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            log.debug("Failed to parse JSON as list", exc_info=True)
            return [val] if val else []
    return []


def _dict_or_empty(val):
    """Retourne un dict à partir d'une valeur qui peut être str JSON, dict, ou None."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            import json
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            log.debug("Failed to parse JSON as dict", exc_info=True)
            return {}
    return {}


def _format_etats(etats):
    """Formate une liste d'états en texte."""
    items = _list_or_empty(etats)
    if not items:
        return "non évaluée"
    if items == ["Normale"] or items == ["Normal"]:
        return "sans particularité"
    return ", ".join(items).lower()


# ══════════════════════════════════════════════════════════════════════════
# Templates (loaded from files)
# ══════════════════════════════════════════════════════════════════════════
# Template strings have been moved to separate .jinja2 files in templates/cr/


# ══════════════════════════════════════════════════════════════════════════
# Registre
# ══════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "standard": {
        "label": "CR Standard (Amsterdam)",
        "description": "Compte-rendu macro placentaire complet",
        "version": "2.0.0",
        "file": "placenta_standard.jinja2",
        "changelog": [
            {
                "version": "2.0.0",
                "date": "2026-03-29",
                "changes": [
                    "Suppression du ratio P/F (pas de tables de référence)",
                    "Ratio F/P conservé avec DS et mention réf. Redline",
                    "Ajout versioning et marqueur de version en pied de CR",
                ],
            },
            {
                "version": "1.0.0",
                "date": "2026-03-01",
                "changes": [
                    "Template standard initial — Amsterdam consensus, biométrie, "
                    "microscopie, tranches de section, conclusion",
                ],
            },
        ],
    },
    "moderne": {
        "label": "CR Moderne (mise en page)",
        "description": "Compte-rendu complet, sections encadrées, micro DB-driven FOETO",
        "version": "1.0.0",
        "file": "placenta_moderne.jinja2",
        "changelog": [
            {
                "version": "1.0.0",
                "date": "2026-07-08",
                "changes": [
                    "Template dérivé du standard + court : en-tête et conclusion "
                    "encadrés, sections en boîtes, source micro fusionnée "
                    "(composite_micro_text) dérivée de foeto_terms.cr_description",
                ],
            },
        ],
    },
    "court": {
        "label": "CR Court",
        "description": "Synthèse courte pour communication rapide",
        "version": "2.0.0",
        "file": "placenta_court.jinja2",
        "changelog": [
            {
                "version": "2.0.0",
                "date": "2026-03-29",
                "changes": [
                    "Remplacement du ratio P/F par F/P (avec DS Redline)",
                    "Ajout versioning",
                ],
            },
            {
                "version": "1.0.0",
                "date": "2026-03-01",
                "changes": ["Template court initial — synthèse rapide"],
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
    def _completude(val):
        items = _list_or_empty(val)
        return ", ".join(items).lower() if items else "non évaluée"

    def _plaque(val):
        d = _dict_or_empty(val)
        etats = _format_etats(d.get("etats", []))
        remarques = d.get("remarques", "")
        result = f"Aspect : {etats}."
        if remarques:
            result += f"\nNote : {remarques}."
        return result

    def _plaque_short(val):
        d = _dict_or_empty(val)
        return _format_etats(d.get("etats", []))

    return {
        "_completude": _completude,
        "_plaque": _plaque,
        "_plaque_short": _plaque_short,
    }


def render_cr(template_id: str, context: dict) -> str:
    return _render(TEMPLATES, template_id, context,
                   custom_helpers=cr_helpers(context), footer_prefix="placenta")
