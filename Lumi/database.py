"""
Viewer — Base SQLite pour annotations, diagnostics, embeddings et pipeline.
Un fichier viewer.db par dossier racine de lames.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

# Source unique de vérité : lames.db (Lumi). viewer.db a été fusionnée dedans.
LAMES_DB = os.environ.get("LAMES_DB_PATH", "/media/SSDsamsung/db/lames.db")

_connections: dict[str, sqlite3.Connection] = {}

SCHEMA = """
-- ── Lames ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slides (
    slide_id        TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    folder          TEXT NOT NULL,
    tissue_type     TEXT,
    width_px        INTEGER,
    height_px       INTEGER,
    mpp_x           REAL,
    mpp_y           REAL,
    objective_power TEXT,
    vendor          TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- ── Diagnostics lame (N par lame) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS diagnoses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id    TEXT NOT NULL REFERENCES slides(slide_id) ON DELETE CASCADE,
    diagnosis   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(slide_id, diagnosis)
);

-- ── Annotations GeoJSON ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS annotations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ann_id              TEXT NOT NULL,
    slide_id            TEXT NOT NULL REFERENCES slides(slide_id) ON DELETE CASCADE,
    tissue_type         TEXT,
    ann_class           TEXT,
    label               TEXT,
    color               TEXT,
    geometry_json       TEXT,
    coordinates_um_json TEXT,
    num_points          INTEGER,
    sp_key              TEXT,          -- superpixel peint ; NULL = détourée à la main
    created_at          TEXT NOT NULL,
    UNIQUE(slide_id, ann_id)
);

-- ── Embeddings (par magnification) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS embeddings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id         TEXT NOT NULL REFERENCES slides(slide_id) ON DELETE CASCADE,
    magnification    TEXT NOT NULL,
    encoder          TEXT NOT NULL,
    embedding_path   TEXT,
    num_patches      INTEGER,
    feature_dim      INTEGER,
    tissue_type      TEXT,
    pipeline_version TEXT,
    mpp_target       REAL,
    created_at       TEXT NOT NULL,
    UNIQUE(slide_id, magnification, encoder)
);

-- ── Log pipeline ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id        TEXT REFERENCES slides(slide_id) ON DELETE SET NULL,
    step            TEXT NOT NULL,
    tool            TEXT,
    tool_version    TEXT,
    parameters_json TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    error_message   TEXT
);

-- ── Clustering ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clustering (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id        TEXT NOT NULL REFERENCES slides(slide_id) ON DELETE CASCADE,
    method          TEXT NOT NULL,
    n_clusters      INTEGER,
    parameters_json TEXT,
    labels_json     TEXT,
    created_at      TEXT NOT NULL
);

-- ── Configuration ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS viewer_config (
    key         TEXT PRIMARY KEY,
    value_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ── Organ status (labellisation lame) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS organ_status (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id    TEXT NOT NULL REFERENCES slides(slide_id) ON DELETE CASCADE,
    organ       TEXT NOT NULL,
    status      TEXT NOT NULL CHECK(status IN ('normal', 'patho')),
    created_at  TEXT NOT NULL,
    UNIQUE(slide_id, organ)
);
CREATE INDEX IF NOT EXISTS idx_organ_status_slide ON organ_status(slide_id);

-- ── Notes lame ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slide_notes (
    slide_id    TEXT PRIMARY KEY REFERENCES slides(slide_id) ON DELETE CASCADE,
    note        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ── Diagnostic d'annotation (contexte LDA/embedding, distinct de labellisation) ─
CREATE TABLE IF NOT EXISTS annotation_diagnosis (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id    TEXT NOT NULL REFERENCES slides(slide_id) ON DELETE CASCADE,
    diagnosis   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(slide_id, diagnosis)
);
CREATE INDEX IF NOT EXISTS idx_ann_diag_slide ON annotation_diagnosis(slide_id);

CREATE INDEX IF NOT EXISTS idx_diagnoses_slide   ON diagnoses(slide_id);
CREATE INDEX IF NOT EXISTS idx_annotations_slide ON annotations(slide_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_slide  ON embeddings(slide_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_slide    ON pipeline_log(slide_id);
CREATE INDEX IF NOT EXISTS idx_clustering_slide  ON clustering(slide_id);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


_MIGRATIONS = [
    ("embeddings", "tissue_type", "TEXT"),
    ("embeddings", "pipeline_version", "TEXT"),
    ("embeddings", "mpp_target", "REAL"),
    ("annotations", "sp_key", "TEXT"),
]


def _migrate(conn):
    for table, col, col_type in _MIGRATIONS:
        try:
            conn.execute(f"SELECT {col} FROM {table} LIMIT 0")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
    conn.commit()


def get_db(root: str | None = None) -> sqlite3.Connection:
    db_path = LAMES_DB
    if db_path not in _connections:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        _migrate(conn)
        _connections[db_path] = conn
    return _connections[db_path]


def upsert_slide(conn, slide_id, filename, folder, tissue_type, calibration=None):
    cal = calibration or {}
    dims = cal.get("dimensions_px", [None, None])
    now = _now()
    conn.execute("""
        INSERT INTO slides (slide_id, filename, folder, tissue_type,
                           width_px, height_px, mpp_x, mpp_y,
                           objective_power, vendor, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slide_id) DO UPDATE SET
            tissue_type=excluded.tissue_type,
            width_px=COALESCE(excluded.width_px, slides.width_px),
            height_px=COALESCE(excluded.height_px, slides.height_px),
            mpp_x=COALESCE(excluded.mpp_x, slides.mpp_x),
            mpp_y=COALESCE(excluded.mpp_y, slides.mpp_y),
            objective_power=COALESCE(excluded.objective_power, slides.objective_power),
            vendor=COALESCE(excluded.vendor, slides.vendor),
            updated_at=excluded.updated_at
    """, (slide_id, filename, folder, tissue_type,
          dims[0], dims[1],
          cal.get("mpp_x"), cal.get("mpp_y"),
          cal.get("objective_power"), cal.get("vendor"),
          now, now))
    conn.commit()


def set_diagnoses(conn, slide_id, diagnosis_list):
    now = _now()
    conn.execute("DELETE FROM diagnoses WHERE slide_id = ?", (slide_id,))
    for diag in diagnosis_list:
        conn.execute(
            "INSERT INTO diagnoses (slide_id, diagnosis, created_at) VALUES (?, ?, ?)",
            (slide_id, diag, now))
    conn.commit()


def set_annotation_diagnoses(conn, slide_id, diagnosis_list):
    now = _now()
    conn.execute("DELETE FROM annotation_diagnosis WHERE slide_id = ?", (slide_id,))
    for diag in diagnosis_list:
        conn.execute(
            "INSERT INTO annotation_diagnosis (slide_id, diagnosis, created_at) VALUES (?, ?, ?)",
            (slide_id, diag, now))
    conn.commit()


def get_annotation_diagnoses(conn, slide_id):
    rows = conn.execute(
        "SELECT diagnosis FROM annotation_diagnosis WHERE slide_id = ? ORDER BY diagnosis",
        (slide_id,)).fetchall()
    return [r["diagnosis"] for r in rows]


def get_diagnoses(conn, slide_id):
    rows = conn.execute(
        "SELECT diagnosis FROM diagnoses WHERE slide_id = ? ORDER BY diagnosis",
        (slide_id,)).fetchall()
    return [r["diagnosis"] for r in rows]


def save_annotations(conn, slide_id, tissue_type, features, mpp_x=0, mpp_y=0):
    now = _now()
    conn.execute("DELETE FROM annotations WHERE slide_id = ?", (slide_id,))
    for feat in features:
        coords_px = feat.get("coordinates", [[]])[0] if feat.get("coordinates") else []
        props = feat.get("properties", {})
        coords_um = None
        if mpp_x > 0 and mpp_y > 0 and coords_px:
            coords_um = [[pt[0] * mpp_x, pt[1] * mpp_y] for pt in coords_px]
        conn.execute("""
            INSERT INTO annotations
                (ann_id, slide_id, tissue_type, ann_class, label, color,
                 geometry_json, coordinates_um_json, num_points, sp_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            props.get("id", ""),
            slide_id,
            tissue_type,
            props.get("ann_class", ""),
            props.get("label", ""),
            props.get("color", ""),
            json.dumps(coords_px),
            json.dumps(coords_um) if coords_um else None,
            len(coords_px),
            props.get("sp_key") or None,
            props.get("created", now),
        ))
    conn.commit()


def load_slide_annotations(conn, slide_id):
    rows = conn.execute(
        "SELECT * FROM annotations WHERE slide_id = ? ORDER BY ann_id",
        (slide_id,)).fetchall()
    return [dict(r) for r in rows]


def get_slide(conn, slide_id):
    row = conn.execute("SELECT * FROM slides WHERE slide_id = ?", (slide_id,)).fetchone()
    return dict(row) if row else None


def get_all_slides(conn):
    rows = conn.execute("SELECT * FROM slides ORDER BY slide_id").fetchall()
    return [dict(r) for r in rows]


def upsert_embedding(conn, slide_id, magnification, encoder, embedding_path,
                     num_patches, feature_dim, tissue_type="",
                     pipeline_version="", mpp_target=0.0):
    now = _now()
    conn.execute("""
        INSERT INTO embeddings
            (slide_id, magnification, encoder, embedding_path,
             num_patches, feature_dim, tissue_type, pipeline_version,
             mpp_target, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slide_id, magnification, encoder) DO UPDATE SET
            embedding_path=excluded.embedding_path,
            num_patches=excluded.num_patches,
            feature_dim=excluded.feature_dim,
            tissue_type=excluded.tissue_type,
            pipeline_version=excluded.pipeline_version,
            mpp_target=excluded.mpp_target,
            created_at=excluded.created_at
    """, (slide_id, magnification, encoder, embedding_path,
          num_patches, feature_dim, tissue_type, pipeline_version,
          mpp_target, now))
    conn.commit()


def get_embeddings(conn, slide_id=None):
    if slide_id:
        rows = conn.execute(
            "SELECT * FROM embeddings WHERE slide_id = ? ORDER BY magnification",
            (slide_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM embeddings ORDER BY slide_id, magnification").fetchall()
    return [dict(r) for r in rows]


def stats(conn):
    s = conn.execute("SELECT COUNT(*) AS n FROM slides").fetchone()["n"]
    d = conn.execute("SELECT COUNT(DISTINCT slide_id) AS n FROM diagnoses").fetchone()["n"]
    a = conn.execute("SELECT COUNT(*) AS n FROM annotations").fetchone()["n"]
    e = conn.execute("SELECT COUNT(*) AS n FROM embeddings").fetchone()["n"]
    return {"slides": s, "diagnosed": d, "annotations": a, "embeddings": e}


# ── Config (viewer_config) ───────────────────────────────────────────────

def get_config(conn, key):
    row = conn.execute("SELECT value_json FROM viewer_config WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row else None


def set_config(conn, key, value):
    now = _now()
    conn.execute(
        """INSERT INTO viewer_config (key, value_json, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
        (key, json.dumps(value, ensure_ascii=False), now))
    conn.commit()


# ponytail: lda_classes now come from foeto_terms, seed only slide_tags
def seed_default_config(conn):
    if get_config(conn, "slide_tags") is not None:
        return
    set_config(conn, "slide_tags", {
        "cordon": ["Normal", "FIR S1", "FIR S2", "FIR G1", "FIR G2", "MAVM",
                    "Nécrose myocytes (rétention >6j)", "AOU"],
        "membranes": ["Normales", "MIR S1", "MIR S2", "MIR S3", "MIR G1", "MIR G2",
                       "Nécrose laminaire déciduale", "Chorioamniotite chronique"],
        "parenchyme": ["Normal", "MVM Art. déc.", "MVM Hypopl. VD", "MVM Mat. acc.", "MVM Infarctus",
                       "FVM Low", "FVM High", "DVM", "VUE Low", "VUE High", "CHI", "NIDF",
                       "Chorangiose", "Chorangiomatose", "Dysplasie mésenchy.",
                       "Érythroblastose", "Accreta spectrum", "Drépano"],
    })


# ── Organ status / Slide notes (labellisation) ─────────────────────────

def upsert_organ_status(conn, slide_id, organ, status):
    now = _now()
    conn.execute("""
        INSERT INTO organ_status (slide_id, organ, status, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(slide_id, organ) DO UPDATE SET status=excluded.status, created_at=excluded.created_at
    """, (slide_id, organ, status, now))
    conn.commit()


def delete_organ_status(conn, slide_id, organ):
    conn.execute("DELETE FROM organ_status WHERE slide_id = ? AND organ = ?", (slide_id, organ))
    conn.commit()


def get_organ_statuses(conn, slide_id):
    rows = conn.execute("SELECT organ, status FROM organ_status WHERE slide_id = ? ORDER BY organ", (slide_id,)).fetchall()
    return [{"organ": r["organ"], "status": r["status"]} for r in rows]


def upsert_slide_note(conn, slide_id, note):
    now = _now()
    conn.execute("""
        INSERT INTO slide_notes (slide_id, note, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(slide_id) DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at
    """, (slide_id, note, now))
    conn.commit()


def delete_slide_note(conn, slide_id):
    conn.execute("DELETE FROM slide_notes WHERE slide_id = ?", (slide_id,))
    conn.commit()


def get_slide_note(conn, slide_id):
    row = conn.execute("SELECT note FROM slide_notes WHERE slide_id = ?", (slide_id,)).fetchone()
    return row["note"] if row else ""


def get_label_summary(conn, folder):
    rows = conn.execute("""
        SELECT s.slide_id, CASE WHEN os.slide_id IS NOT NULL THEN 'labeled' ELSE 'unlabeled' END AS status
        FROM slides s LEFT JOIN (SELECT DISTINCT slide_id FROM organ_status) os ON s.slide_id = os.slide_id
        WHERE s.folder = ?
    """, (folder,)).fetchall()
    return {r["slide_id"]: r["status"] for r in rows}
