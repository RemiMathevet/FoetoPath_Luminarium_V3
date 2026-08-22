"""
Read-only queries against Lumi's single database (lames.db).
Never writes — the Lumi DB is owned by the pipeline. lames.db is the source of
truth for slide paths (hot/cold roots in the config table), annotations,
diagnoses and embeddings (ex-viewer.db tables, now fused in).
"""

import logging
import re
import sqlite3
from pathlib import Path

import db

log = logging.getLogger(__name__)

LUMI_DB_PATH_SETTING = "lumi_db_path"
DEFAULT_LUMI_DB = "/media/SSDsamsung/db/lames.db"

DEFAULT_HOT_ROOT = "/media/toshiba1/hot"
DEFAULT_COLD_ROOT = "/media/toshiba2/cold_storage"


def _lames_db_path() -> str:
    return db.get_setting(LUMI_DB_PATH_SETTING, DEFAULT_LUMI_DB)


def _like_prefix(numero_dossier: str) -> str:
    """Motif LIKE des lames d'un cas, à utiliser avec ESCAPE '\\'.

    Le `_` qui sépare le dossier du bloc est un joker SQL : sans échappement,
    `25P123_%` remonte aussi les lames de 25P1234 — les deux longueurs de
    numéro coexistent en base.
    """
    esc = (numero_dossier.replace("\\", "\\\\")
           .replace("_", "\\_").replace("%", "\\%"))
    return esc + "\\_%"


def _connect_readonly(path: str) -> sqlite3.Connection | None:
    if not path or not Path(path).is_file():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _config(conn, key: str, default: str) -> str:
    try:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return default
    return row["value"] if row and row["value"] else default


def _resolve_path(conn, chemin, storage, cold_root_per_lame=None) -> str | None:
    """Absolute slide path from `lames`: the storage-tier root + relative
    `chemin`. This is the authoritative record and stays correct across
    archiving; the viewer's slides.folder/filename is a stale hot-time snapshot
    and is deliberately ignored."""
    if not chemin:
        return None
    if chemin.startswith("/"):
        return chemin
    if storage == "cold" and cold_root_per_lame:
        root = cold_root_per_lame
    else:
        key = "cold_root" if storage == "cold" else "hot_root"
        root = _config(conn, key, DEFAULT_COLD_ROOT if storage == "cold" else DEFAULT_HOT_ROOT)
    return root.rstrip("/") + "/" + chemin.lstrip("/")


def get_case_slides_dir(numero_dossier: str) -> str | None:
    """Local directory holding a case's slides, derived from Lumi's absolute
    slide paths. Returns None if no on-disk slide is found. Replaces the old
    slides_root + numero_dossier reconstruction."""
    data = get_slides_for_case(numero_dossier)
    for slide in data.get("slides", []):
        full_path = slide.get("full_path")
        if full_path:
            parent = Path(full_path).parent
            if parent.is_dir():
                return str(parent)
    return None


def get_slide_counts(numeros: list[str]) -> dict[str, int]:
    """Return {numero_dossier: slide_count} for a batch of case numbers."""
    conn = _connect_readonly(_lames_db_path())
    if not conn:
        return {}
    try:
        rows = conn.execute(
            "SELECT nom_lame FROM lames WHERE storage != 'deleted'"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return {}
    conn.close()

    counts: dict[str, int] = {}
    lookup = set(numeros)
    for r in rows:
        prefix = r["nom_lame"].split("_")[0]
        if prefix in lookup:
            counts[prefix] = counts.get(prefix, 0) + 1
    return counts


def get_slides_for_case(numero_dossier: str) -> dict:
    """Query Lumi DBs for all slides matching a case number.

    Returns dict with slides list and summary stats.
    """
    result = {
        "available": False,
        "slides": [],
        "stats": {"total": 0, "in_viewer": 0, "annotated": 0, "embedded": 0, "diagnosed": 0},
    }

    conn = _connect_readonly(_lames_db_path())
    if not conn:
        return result

    try:
        rows = conn.execute(
            "SELECT id, nom_lame, taille_mo, chemin, storage, cold_root FROM lames "
            "WHERE nom_lame LIKE ? ESCAPE '\\' ORDER BY nom_lame",
            (_like_prefix(numero_dossier),),
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return result

    if not rows:
        conn.close()
        return result

    result["available"] = True
    result["stats"]["total"] = len(rows)

    slides_by_name = {}
    for r in rows:
        slides_by_name[r["nom_lame"]] = {
            "nom_lame": r["nom_lame"],
            "taille_mo": r["taille_mo"],
            "chemin": r["chemin"],
            "storage": r["storage"] or "hot",
            "cold_root": r["cold_root"],
            "tissue_type": None,
            "diagnoses": [],
            "annotation_count": 0,
            "embedding_mags": [],
            "full_path": None,
            "in_viewer": False,
            "label_status": "unlabeled",
            "organ_statuses": [],
            "slide_note": None,
        }

    try:
        nom_lames = list(slides_by_name.keys())
        placeholders = ",".join("?" * len(nom_lames))

        # Viewer presence + tissue type (path comes from lames, not here)
        vrows = conn.execute(
            f"SELECT slide_id, tissue_type FROM slides WHERE slide_id IN ({placeholders})",
            nom_lames,
        ).fetchall()
        viewer_meta = {vr["slide_id"]: vr for vr in vrows}
        for sid, slide in slides_by_name.items():
            vr = viewer_meta.get(sid)
            if vr:
                slide["in_viewer"] = True
                slide["tissue_type"] = vr["tissue_type"]
                result["stats"]["in_viewer"] += 1
            slide["full_path"] = _resolve_path(
                conn, slide["chemin"], slide["storage"],
                cold_root_per_lame=slide["cold_root"],
            )

        # Diagnoses
        drows = conn.execute(
            f"SELECT slide_id, diagnosis FROM diagnoses WHERE slide_id IN ({placeholders})",
            nom_lames,
        ).fetchall()
        diagnosed_set = set()
        for dr in drows:
            sid = dr["slide_id"]
            if sid in slides_by_name:
                slides_by_name[sid]["diagnoses"].append(dr["diagnosis"])
                diagnosed_set.add(sid)
        result["stats"]["diagnosed"] = len(diagnosed_set)

        # Annotations count
        arows = conn.execute(
            f"SELECT slide_id, COUNT(*) as cnt FROM annotations "
            f"WHERE slide_id IN ({placeholders}) GROUP BY slide_id",
            nom_lames,
        ).fetchall()
        for ar in arows:
            sid = ar["slide_id"]
            if sid in slides_by_name:
                slides_by_name[sid]["annotation_count"] = ar["cnt"]
        result["stats"]["annotated"] = sum(1 for s in slides_by_name.values() if s["annotation_count"] > 0)

        # Organ status (labellisation)
        try:
            orows = conn.execute(
                f"SELECT slide_id, organ, status FROM organ_status "
                f"WHERE slide_id IN ({placeholders})",
                nom_lames,
            ).fetchall()
            for orw in orows:
                sid = orw["slide_id"]
                if sid in slides_by_name:
                    slides_by_name[sid]["organ_statuses"].append(
                        {"organ": orw["organ"], "status": orw["status"]})
            for slide in slides_by_name.values():
                if slide["organ_statuses"]:
                    has_patho = any(o["status"] == "patho" for o in slide["organ_statuses"])
                    slide["label_status"] = "labeled_patho" if has_patho else "labeled_normal"
        except sqlite3.OperationalError:
            pass

        # Slide notes
        try:
            nrows = conn.execute(
                f"SELECT slide_id, note FROM slide_notes "
                f"WHERE slide_id IN ({placeholders})",
                nom_lames,
            ).fetchall()
            for nr in nrows:
                sid = nr["slide_id"]
                if sid in slides_by_name:
                    slides_by_name[sid]["slide_note"] = nr["note"]
        except sqlite3.OperationalError:
            pass

        # Embeddings
        erows = conn.execute(
            f"SELECT slide_id, magnification FROM embeddings WHERE slide_id IN ({placeholders})",
            nom_lames,
        ).fetchall()
        embedded_set = set()
        for er in erows:
            sid = er["slide_id"]
            if sid in slides_by_name:
                slides_by_name[sid]["embedding_mags"].append(er["magnification"])
                embedded_set.add(sid)
        result["stats"]["embedded"] = len(embedded_set)

    except sqlite3.OperationalError as e:
        log.debug("lames.db slide query failed: %s", e)
    finally:
        conn.close()

    # Resolve FOETO IDs → French labels
    all_diag_ids = set()
    for slide in slides_by_name.values():
        for d in slide["diagnoses"]:
            all_diag_ids.add(d.split(".G")[0])
    if all_diag_ids:
        foeto_labels = _resolve_foeto_labels(all_diag_ids)
        for slide in slides_by_name.values():
            slide["diagnoses_resolved"] = [
                {"id": d, "label_fr": foeto_labels.get(d.split(".G")[0], d)}
                for d in slide["diagnoses"]
            ]
    else:
        for slide in slides_by_name.values():
            slide["diagnoses_resolved"] = []

    result["slides"] = list(slides_by_name.values())
    return result


def _foeto_db_path() -> str:
    from config import FOETO_DB_PATH
    return FOETO_DB_PATH


def _resolve_foeto_labels(ids: set) -> dict:
    """Read-only lookup of FOETO term IDs → label_fr from foeto_base."""
    foeto_path = _foeto_db_path()
    if not Path(foeto_path).is_file():
        return {}
    try:
        fconn = sqlite3.connect(f"file:{foeto_path}?mode=ro", uri=True)
        ph = ",".join("?" * len(ids))
        rows = fconn.execute(
            f"SELECT id, label_fr FROM foeto_terms WHERE id IN ({ph})",
            list(ids),
        ).fetchall()
        fconn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


# ponytail: static map organ → generic "normal" FOETO term ID
_NORMAL_TERM = {
    "cerveau": "FOETO:PF.CER-NOR-007",
    "coeur": "FOETO:PF.COE-NOR-016",
    "poumon": "FOETO:PF.POU-NOR-023",
    "rein": "FOETO:PF.REN-NOR-026",
    "foie": "FOETO:PF.FOI-NOR-002",
    "digestif": "FOETO:PF.DIG-NOR-065",
    "endocrine": "FOETO:PF.END-NOR-045",
    "hematolymphoide": "FOETO:PF.HEM-NOR-068",
    "muscle": "FOETO:PF.MUS-NOR-008",
    "peau": "FOETO:PF.PEA-NOR-021",
    "genital": "FOETO:PF.GEN-NOR-012",
    "squelette": "FOETO:PF.SQU-NOR-019",
    "oeil_oreille": "FOETO:PF.ORL-NOR-034",
    "cordon": "FOETO:PP.COR-NOR-000",
    "membranes": "FOETO:PP.MEM-NOR-001",
    "parenchyme": "FOETO:PP.PAR-NOR-000",
}

_ORGAN_ORDER = [
    "cordon", "membranes", "parenchyme",
    "cerveau", "coeur", "poumon", "rein", "foie", "digestif",
    "endocrine", "hematolymphoide", "muscle", "peau", "genital",
    "squelette", "oeil_oreille",
]

_ORGAN_LABEL = {
    "cerveau": "Cerveau", "coeur": "Cœur", "poumon": "Poumons",
    "rein": "Reins", "foie": "Foie", "digestif": "Tractus digestif",
    "endocrine": "Système endocrine", "hematolymphoide": "Système hématolymphoïde",
    "muscle": "Muscle", "peau": "Peau", "genital": "Appareil génital",
    "squelette": "Squelette", "oeil_oreille": "Œil et oreille",
    "cordon": "Cordon", "membranes": "Membranes", "parenchyme": "Parenchyme",
}


def _resolve_foeto_for_cr(ids: set) -> dict:
    """Resolve FOETO IDs → {id: {organe, cr_description, cr_section, label_fr}}."""
    foeto_path = _foeto_db_path()
    if not Path(foeto_path).is_file() or not ids:
        return {}
    try:
        fconn = sqlite3.connect(f"file:{foeto_path}?mode=ro", uri=True)
        ph = ",".join("?" * len(ids))
        rows = fconn.execute(
            f"SELECT id, organe, cr_description, cr_section, label_fr FROM foeto_terms WHERE id IN ({ph})",
            list(ids),
        ).fetchall()
        fconn.close()
        return {r[0]: {"organe": r[1], "cr_description": r[2] or "",
                       "cr_section": r[3], "label_fr": r[4] or ""} for r in rows}
    except Exception:
        return {}


def _load_cr_sections() -> list:
    """CR sections (order + normal text) from foeto_structures, DB-driven."""
    foeto_path = _foeto_db_path()
    if not Path(foeto_path).is_file():
        return []
    try:
        fconn = sqlite3.connect(f"file:{foeto_path}?mode=ro", uri=True)
        rows = fconn.execute(
            "SELECT name, label_fr, texte_normal FROM foeto_structures "
            "WHERE type='cr_section' AND domain='placenta' ORDER BY sort_order"
        ).fetchall()
        fconn.close()
        return rows
    except Exception:
        return []


# Section → tissu qui doit être examiné pour l'émettre.
# ponytail: 2 cas particuliers, tout le reste = parenchyme.
_CR_SECTION_ORGAN = {"cr_cordon": "cordon", "cr_membranes": "membranes"}


def build_labellisation_micro_text(numero_dossier: str) -> str:
    """Build microscopy CR text from slide labellisation (organ_status + diagnoses → cr_description)."""
    slides_data = get_slides_for_case(numero_dossier)
    if not slides_data["available"]:
        return ""

    organ_status = {}
    organ_diags = {}
    notes = []

    for sl in slides_data["slides"]:
        for os_entry in sl["organ_statuses"]:
            organ = os_entry["organ"]
            if organ not in organ_status or os_entry["status"] == "patho":
                organ_status[organ] = os_entry["status"]
        if sl["slide_note"]:
            lame_num = sl["nom_lame"].rsplit("_", 1)[-1]
            notes.append(f"Lame {lame_num} : {sl['slide_note']}")

    if not organ_status:
        return ""

    # Collect all FOETO IDs to resolve in one query
    all_ids = set()
    for organ, status in organ_status.items():
        if status == "normal" and organ in _NORMAL_TERM:
            all_ids.add(_NORMAL_TERM[organ])
    for sl in slides_data["slides"]:
        for d in sl["diagnoses"]:
            all_ids.add(d.split(".G")[0])

    foeto_data = _resolve_foeto_for_cr(all_ids)

    # Assign diagnoses to organs via foeto_terms.organe
    for sl in slides_data["slides"]:
        for d in sl["diagnoses"]:
            base_id = d.split(".G")[0]
            info = foeto_data.get(base_id)
            if not info or not info["cr_description"]:
                continue
            organ = info["organe"]
            organ_diags.setdefault(organ, [])
            if info["cr_description"] not in organ_diags[organ]:
                organ_diags[organ].append(info["cr_description"])

    # Build text in standard organ order
    lines = []
    seen = set()
    for organ in _ORGAN_ORDER:
        if organ not in organ_status or organ in seen:
            continue
        seen.add(organ)
        label = _ORGAN_LABEL.get(organ, organ.capitalize())

        if organ in organ_diags:
            lines.append(f"{label} : {' '.join(organ_diags[organ])}")
        elif organ_status[organ] == "normal":
            normal_id = _NORMAL_TERM.get(organ)
            desc = foeto_data.get(normal_id, {}).get("cr_description", "sans particularité.")
            lines.append(f"{label} : {desc}")
        else:
            lines.append(f"{label} : anomalies notées.")

    for organ in sorted(organ_status.keys()):
        if organ not in seen:
            lines.append(f"{organ.capitalize()} : examiné.")

    if notes:
        lines.append("")
        lines.extend(notes)

    return "\n".join(lines)


def build_labellisation_table(numero_dossier: str) -> list[dict]:
    """Build structured labellisation data for CR templates.

    Returns list of dicts sorted by organ order:
      [{organe, statut, findings: [{text, nb_lames}], notes: [str]}]
    Each finding has nb_lames so templates can do:
      {% if f.nb_lames > 2 %}{{ f.text }}, diffus{% endif %}
    """
    slides_data = get_slides_for_case(numero_dossier)
    if not slides_data["available"]:
        return []

    organ_status = {}
    # {organ: {cr_description: set(slide_names)}}
    organ_diag_slides: dict[str, dict[str, set]] = {}
    organ_notes: dict[str, list[str]] = {}

    for sl in slides_data["slides"]:
        for os_entry in sl["organ_statuses"]:
            organ = os_entry["organ"]
            if organ not in organ_status or os_entry["status"] == "patho":
                organ_status[organ] = os_entry["status"]
        if sl["slide_note"]:
            for os_entry in sl["organ_statuses"]:
                organ_notes.setdefault(os_entry["organ"], [])
                if sl["slide_note"] not in organ_notes[os_entry["organ"]]:
                    organ_notes[os_entry["organ"]].append(sl["slide_note"])

    if not organ_status:
        return []

    all_ids = set()
    for organ, status in organ_status.items():
        if status == "normal" and organ in _NORMAL_TERM:
            all_ids.add(_NORMAL_TERM[organ])
    for sl in slides_data["slides"]:
        for d in sl["diagnoses"]:
            all_ids.add(d.split(".G")[0])

    foeto_data = _resolve_foeto_for_cr(all_ids)

    for sl in slides_data["slides"]:
        for d in sl["diagnoses"]:
            base_id = d.split(".G")[0]
            info = foeto_data.get(base_id)
            if not info or not info["cr_description"]:
                continue
            organ = info["organe"]
            organ_diag_slides.setdefault(organ, {})
            organ_diag_slides[organ].setdefault(info["cr_description"], set())
            organ_diag_slides[organ][info["cr_description"]].add(sl["nom_lame"])

    # Count total slides per organ for context
    organ_slide_count: dict[str, int] = {}
    for sl in slides_data["slides"]:
        for os_entry in sl["organ_statuses"]:
            organ_slide_count[os_entry["organ"]] = organ_slide_count.get(os_entry["organ"], 0) + 1

    table = []
    seen = set()
    for organ in list(_ORGAN_ORDER) + sorted(organ_status.keys()):
        if organ not in organ_status or organ in seen:
            continue
        seen.add(organ)
        label = _ORGAN_LABEL.get(organ, organ.capitalize())
        status = organ_status[organ]

        findings = []
        if organ in organ_diag_slides:
            for desc, slide_set in organ_diag_slides[organ].items():
                findings.append({"text": desc, "nb_lames": len(slide_set)})
        elif status == "normal":
            normal_id = _NORMAL_TERM.get(organ)
            desc = foeto_data.get(normal_id, {}).get("cr_description", "sans particularité.")
            findings.append({"text": desc, "nb_lames": organ_slide_count.get(organ, 1)})
        else:
            findings.append({"text": "anomalies notées.", "nb_lames": 1})

        table.append({
            "organe": label,
            "organe_key": organ,
            "statut": status,
            "findings": findings,
            "nb_lames": organ_slide_count.get(organ, 0),
            "notes": organ_notes.get(organ, []),
        })

    return table


_GRADE_SUFFIX = re.compile(r"\.G\d+$")


def _load_case_annotations(numero_dossier: str) -> list:
    """[(slide_id, ann_class)] pour un cas, marqueurs STRUCT: exclus (hors CR)."""
    conn = _connect_readonly(_lames_db_path())
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT slide_id, ann_class FROM annotations "
            "WHERE slide_id LIKE ? ESCAPE '\\' GROUP BY slide_id, ann_class",
            (_like_prefix(numero_dossier),),
        ).fetchall()
        return [(r["slide_id"], r["ann_class"]) for r in rows
                if r["ann_class"] and not r["ann_class"].startswith("STRUCT:")]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _resolve_ann_for_cr(tokens: set) -> dict:
    """{token: (cr_description, cr_section, label_fr)} pour les classes d'annotation.

    Résolution par id FOETO (suffixe .G\\d+ toléré) puis viewer_id. Les signes
    de structure/normaux (sans cr_section) ne résolvent pas → exclus du CR.
    """
    foeto_path = _foeto_db_path()
    if not Path(foeto_path).is_file() or not tokens:
        return {}
    try:
        fconn = sqlite3.connect(f"file:{foeto_path}?mode=ro", uri=True)
        rows = fconn.execute(
            "SELECT id, viewer_id, cr_description, cr_section, label_fr FROM foeto_terms "
            "WHERE cr_section IS NOT NULL AND cr_description IS NOT NULL "
            "AND cr_description != ''"
        ).fetchall()
        fconn.close()
    except Exception:
        return {}
    by_id, by_vid = {}, {}
    for tid, vid, desc, sec, label in rows:
        val = (desc, sec, label or "")
        if tid:
            by_id[tid] = val
        if vid:
            by_vid[vid] = val
    out = {}
    for tok in tokens:
        base = _GRADE_SUFFIX.sub("", tok)
        hit = by_id.get(base) or by_vid.get(tok) or by_vid.get(base)
        if hit:
            out[tok] = hit
    return out


# ponytail: tag diagnostic en fin de cr_description, ex. "…amnios (MIR stage 1)."
# Convention FOETO ; si un jour la parenthèse porte autre chose, retoucher ici.
_DIAG_PAREN = re.compile(r"\s*\([^()]+\)(\s*\.?\s*)$")


def _morpho(desc: str) -> str:
    """Description morphologique : retire le tag diagnostic parenthésé final."""
    m = _DIAG_PAREN.search(desc)
    if not m:
        return desc
    return (desc[:m.start()].rstrip() + (m.group(1).strip() or "")).strip()


def build_composite_micro_cr(numero_dossier: str) -> tuple[str, list[str]]:
    """CR micro DB-driven → (description morphologique, diagnostics conclusion).

    Part d'une description placentaire normale (8 sections foeto_structures).
    Deux sources fusionnées, dédup par texte :
      - labellisation (organ_status + diagnostics FOETO id) → normal par défaut,
        les pathologies labellisées remplacent le normal de leur section ;
      - annotations de pathologie (table annotations) → surchargent le normal
        même si la lame est labellisée normale (ex. « déciduite chronique »).
    Les annotations de structure (STRUCT: / signes sans cr_section) sont exclues.
    La description reste morphologique (tag diagnostic retiré) ; les diagnostics
    (label_fr) partent en conclusion, à charge du LLM de les expliciter.
    """
    slides_data = get_slides_for_case(numero_dossier)
    if not slides_data["available"]:
        return "", []

    # Collect organ statuses and notes per slide
    organ_status = {}
    notes = []
    for sl in slides_data["slides"]:
        for os_entry in sl["organ_statuses"]:
            organ = os_entry["organ"]
            if organ not in organ_status or os_entry["status"] == "patho":
                organ_status[organ] = os_entry["status"]
        if sl["slide_note"]:
            lame_num = sl["nom_lame"].rsplit("_", 1)[-1]
            notes.append(f"Lame {lame_num} : {sl['slide_note']}")

    if not organ_status:
        return "", []

    sec_findings: dict[str, list[dict]] = {}
    concl: list[dict] = []

    def _push(sec, desc, label, slide_id):
        mdesc = _morpho(desc)
        bucket = sec_findings.setdefault(sec, [])
        for f in bucket:
            if f["text"] == mdesc:
                f["slides"].add(slide_id)
                break
        else:
            bucket.append({"text": mdesc, "slides": {slide_id}})
        if label:
            for c in concl:
                if c["label"] == label:
                    c["slides"].add(slide_id)
                    return
            concl.append({"label": label, "slides": {slide_id}})

    # 1) Findings labellisation : diagnostics FOETO id par lame.
    all_ids = set()
    for sl in slides_data["slides"]:
        for d in sl["diagnoses"]:
            all_ids.add(d.split(".G")[0])
    foeto_data = _resolve_foeto_for_cr(all_ids)
    for sl in slides_data["slides"]:
        for d in sl["diagnoses"]:
            info = foeto_data.get(d.split(".G")[0])
            if info and info["cr_description"] and info["cr_section"]:
                _push(info["cr_section"], info["cr_description"],
                      info["label_fr"], sl["nom_lame"])

    # 2) Fusion : annotations de pathologie surchargent le normal.
    ann_rows = _load_case_annotations(numero_dossier)
    ann_resolved = _resolve_ann_for_cr({a[1] for a in ann_rows})
    for slide_id, ann_class in ann_rows:
        hit = ann_resolved.get(ann_class)
        if hit:
            _push(hit[1], hit[0], hit[2], slide_id)

    lines = []
    for name, label, texte_normal in _load_cr_sections():
        req_organ = _CR_SECTION_ORGAN.get(name, "parenchyme")
        if req_organ not in organ_status:
            continue
        findings = sec_findings.get(name, [])
        if findings:
            parts = []
            for f in findings:
                n = len(f["slides"])
                parts.append(f"{f['text'].rstrip('.')} (diffus, {n} lames)."
                             if n > 2 else f["text"])
            lines.append(f"{label} : {' '.join(parts)}")
        else:
            lines.append(f"{label} : {texte_normal}")

    if notes:
        lines.append("")
        lines.extend(notes)

    concl_items = []
    for c in concl:
        n = len(c["slides"])
        concl_items.append(f"{c['label']} (diffus)" if n > 2 else c["label"])

    return "\n".join(lines), concl_items


def get_annotations_for_case(numero_dossier: str) -> dict:
    """Return structured annotations and diagnoses for a case.

    Groups annotations by tissue_type and ann_class, with counts.
    Returns diagnoses per slide.
    """
    result = {"annotations_by_tissue": {}, "diagnoses_by_slide": {}, "slide_count": 0}

    conn = _connect_readonly(_lames_db_path())
    if not conn:
        return result

    try:
        slides = conn.execute(
            "SELECT slide_id FROM slides WHERE slide_id LIKE ? ESCAPE '\\'",
            (_like_prefix(numero_dossier),),
        ).fetchall()
        slide_ids = [s["slide_id"] for s in slides]
        if not slide_ids:
            conn.close()
            return result

        result["slide_count"] = len(slide_ids)
        ph = ",".join("?" * len(slide_ids))

        rows = conn.execute(
            f"SELECT slide_id, tissue_type, ann_class, label, COUNT(*) as cnt "
            f"FROM annotations WHERE slide_id IN ({ph}) "
            f"GROUP BY slide_id, tissue_type, ann_class",
            slide_ids,
        ).fetchall()
        for r in rows:
            tissue = r["tissue_type"] or "autre"
            if tissue not in result["annotations_by_tissue"]:
                result["annotations_by_tissue"][tissue] = {}
            cls = r["ann_class"] or "unknown"
            if cls not in result["annotations_by_tissue"][tissue]:
                result["annotations_by_tissue"][tissue][cls] = {
                    "label": r["label"], "count": 0, "slides": [],
                }
            entry = result["annotations_by_tissue"][tissue][cls]
            entry["count"] += r["cnt"]
            entry["slides"].append(r["slide_id"])

        trows = conn.execute(
            f"SELECT slide_id, tissue_type FROM slides WHERE slide_id IN ({ph})",
            slide_ids,
        ).fetchall()
        for tr in trows:
            tt = tr["tissue_type"]
            if tt:
                result.setdefault("tissues_examined", set()).add(tt)
        if "tissues_examined" in result:
            result["tissues_examined"] = list(result["tissues_examined"])

        drows = conn.execute(
            f"SELECT slide_id, diagnosis FROM diagnoses WHERE slide_id IN ({ph})",
            slide_ids,
        ).fetchall()
        for dr in drows:
            sid = dr["slide_id"]
            if sid not in result["diagnoses_by_slide"]:
                result["diagnoses_by_slide"][sid] = []
            result["diagnoses_by_slide"][sid].append(dr["diagnosis"])

        result["diagnoses_by_tissue"] = {}
        for tr in trows:
            sid, tt = tr["slide_id"], tr["tissue_type"]
            if tt and sid in result["diagnoses_by_slide"]:
                if tt not in result["diagnoses_by_tissue"]:
                    result["diagnoses_by_tissue"][tt] = []
                result["diagnoses_by_tissue"][tt].extend(result["diagnoses_by_slide"][sid])

    except sqlite3.OperationalError as e:
        log.debug("lames.db annotation query failed: %s", e)
    finally:
        conn.close()

    return result
