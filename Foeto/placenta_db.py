#!/usr/bin/env python3
"""
FoetoPath — Module BDD SQLite pour les placentas.

Schéma simplifié par rapport au fœtus :
  - placenta_cases     : données admin (numéro, terme, contexte)
  - placenta_modules   : JSON par module (macro_frais, tranches_section)
  - placenta_photos    : photos indexées par clé

Utilise db_core.DatabaseManager pour les opérations communes.
"""

import json
import logging
import os
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Optional

from config import KNOWN_MODULES_PLACENTA
from db_core import DatabaseManager, _now, _row_to_dict

log = logging.getLogger(__name__)

# ── Instance partagée ────────────────────────────────────────────────────

_mgr = DatabaseManager(
    db_name="placenta.db",
    cases_table="placenta_cases",
    modules_table="placenta_modules",
)

# Alias de compatibilité
KNOWN_MODULES = KNOWN_MODULES_PLACENTA


# ── Schéma SQL ───────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS placenta_cases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_dossier      TEXT UNIQUE NOT NULL,

    -- Contexte
    terme_sa            INTEGER,
    terme_jours         INTEGER DEFAULT 0,
    terme_source        TEXT,
    masse_foetale_g     INTEGER,
    sexe                TEXT,
    indication_terme    TEXT,

    -- Biométrie galette
    grand_axe_cm        REAL,
    petit_axe_cm        REAL,
    epaisseur_cm        REAL,
    masse_paree_g       INTEGER,

    -- Descriptif macro
    forme               TEXT,
    completude          TEXT,
    plaque_choriale     TEXT,
    plaque_basale       TEXT,
    cordon              TEXT,
    membranes           TEXT,

    -- Workflow
    statut              TEXT DEFAULT 'en_cours',
    dossier_photos_path TEXT,
    dossier_lames_path  TEXT,

    -- Attribution & traçabilité
    assigned_to         TEXT DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    created_by          TEXT DEFAULT '',
    modified_by         TEXT DEFAULT '',
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS placenta_modules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES placenta_cases(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    data_json   TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL,
    modified_by TEXT DEFAULT '',
    UNIQUE(case_id, module_name)
);

CREATE TABLE IF NOT EXISTS placenta_photos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES placenta_cases(id) ON DELETE CASCADE,
    photo_key   TEXT NOT NULL,
    filename    TEXT NOT NULL,
    label       TEXT,
    module      TEXT,
    file_path   TEXT,
    size_bytes  INTEGER DEFAULT 0,
    uploaded_at TEXT NOT NULL,
    uploaded_by TEXT DEFAULT '',
    UNIQUE(case_id, photo_key)
);

CREATE TABLE IF NOT EXISTS templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    type            TEXT NOT NULL,
    content_jinja2  TEXT NOT NULL,
    is_default      INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_docs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL,
    template_id     TEXT,
    content_html    TEXT,
    content_text    TEXT,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plac_numero ON placenta_cases(numero_dossier);
CREATE INDEX IF NOT EXISTS idx_plac_mod    ON placenta_modules(case_id, module_name);
CREATE INDEX IF NOT EXISTS idx_plac_photo  ON placenta_photos(case_id);
CREATE INDEX IF NOT EXISTS idx_plac_docs   ON generated_docs(case_id);
"""


# ── Init & Connexion ─────────────────────────────────────────────────────

def init_db(base_dir: str | Path) -> Path:
    """Initialise la BDD placenta dans le répertoire donné."""
    db_path = _mgr.set_path(base_dir)
    with _mgr.connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
    return db_path


def _migrate(conn):
    """Ajoute les colonnes manquantes aux tables existantes (migrations)."""
    _migrations = [
        ("placenta_cases", "modified_by", "TEXT DEFAULT ''"),
        ("placenta_cases", "created_by", "TEXT DEFAULT ''"),
        ("placenta_cases", "notes", "TEXT"),
        ("placenta_cases", "dossier_lames_path", "TEXT"),
        ("placenta_cases", "assigned_to", "TEXT DEFAULT ''"),
        ("placenta_cases", "indication_terme", "TEXT"),
        ("placenta_modules", "modified_by", "TEXT DEFAULT ''"),
        ("placenta_photos", "uploaded_by", "TEXT DEFAULT ''"),
    ]
    for table, col, col_type in _migrations:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            print(f"[placenta_db] Migration: ajout colonne {table}.{col}")


def get_db_path() -> Path:
    return _mgr.get_db_path()


# Exposer connect pour le code legacy
_connect = _mgr.connect


# ── Helpers spécifiques placenta ─────────────────────────────────────────

def _get_data_root() -> str:
    try:
        import db as foetopath_db
        return foetopath_db.get_setting("data_root", "")
    except Exception:
        return ""


def _resolve_path(rel_path: str | None) -> str | None:
    if not rel_path:
        return rel_path
    if os.path.isabs(rel_path):
        return rel_path
    root = _get_data_root()
    if root:
        return str(Path(root) / rel_path)
    return rel_path


def _to_relative_path(abs_path: str | None) -> str | None:
    if not abs_path:
        return abs_path
    root = _get_data_root()
    if root and abs_path.startswith(root):
        rel = abs_path[len(root):].lstrip("/")
        return rel if rel else abs_path
    return abs_path


def _enrich_case(row) -> dict:
    """Parse les champs JSON d'un cas placenta."""
    d = dict(row)
    for k in ["completude", "plaque_choriale", "plaque_basale", "cordon", "membranes"]:
        if d.get(k) and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError):
                log.debug("Failed to parse JSON field %s", k, exc_info=True)
    d["dossier_photos_path"] = _resolve_path(d.get("dossier_photos_path"))
    d["dossier_lames_path"] = _resolve_path(d.get("dossier_lames_path"))
    return d


# ── CRUD Cases ───────────────────────────────────────────────────────────

def create_case(data: dict, user: str = "") -> int:
    """Crée un nouveau cas placenta. Retourne l'ID."""
    now = _now()
    numero = data.get("numero_dossier")
    if not numero:
        raise ValueError("numero_dossier requis")

    with _mgr.connect() as conn:
        cur = conn.execute(
            """INSERT INTO placenta_cases
               (numero_dossier, terme_sa, terme_jours, terme_source,
                masse_foetale_g, sexe,
                grand_axe_cm, petit_axe_cm, epaisseur_cm, masse_paree_g,
                forme, completude, plaque_choriale, plaque_basale,
                cordon, membranes, statut, notes, assigned_to,
                created_at, updated_at, created_by, modified_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                numero,
                data.get("terme_sa"),
                data.get("terme_jours", 0),
                data.get("terme_source"),
                data.get("masse_foetale_g"),
                data.get("sexe"),
                data.get("grand_axe_cm"),
                data.get("petit_axe_cm"),
                data.get("epaisseur_cm"),
                data.get("masse_paree_g"),
                data.get("forme"),
                json.dumps(data.get("completude", []), ensure_ascii=False),
                json.dumps(data.get("plaque_choriale", {}), ensure_ascii=False),
                json.dumps(data.get("plaque_basale", {}), ensure_ascii=False),
                json.dumps(data.get("cordon", {}), ensure_ascii=False),
                json.dumps(data.get("membranes", {}), ensure_ascii=False),
                data.get("statut", "en_cours"),
                data.get("notes"),
                data.get("assigned_to", ""),
                now, now, user, user,
            ),
        )
        return cur.lastrowid


def update_case(case_id: int, data: dict, user: str = "") -> bool:
    """Met à jour un cas placenta existant."""
    now = _now()
    sets = []
    vals = []

    scalars = [
        "numero_dossier", "terme_sa", "terme_jours", "terme_source",
        "masse_foetale_g", "sexe",
        "grand_axe_cm", "petit_axe_cm", "epaisseur_cm", "masse_paree_g",
        "forme", "indication_terme", "statut", "notes", "dossier_photos_path", "dossier_lames_path",
        "assigned_to",
    ]
    for k in scalars:
        if k in data:
            sets.append(f"{k} = ?")
            val = data[k]
            if k in ("dossier_photos_path", "dossier_lames_path"):
                val = _to_relative_path(val)
            vals.append(val)

    json_fields = ["completude", "plaque_choriale", "plaque_basale", "cordon", "membranes"]
    for k in json_fields:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(json.dumps(data[k], ensure_ascii=False) if not isinstance(data[k], str) else data[k])

    if not sets:
        return False

    sets.append("updated_at = ?")
    vals.append(now)
    if user:
        sets.append("modified_by = ?")
        vals.append(user)
    vals.append(case_id)

    with _mgr.connect() as conn:
        conn.execute(f"UPDATE placenta_cases SET {', '.join(sets)} WHERE id = ?", vals)
        return True


def get_case(case_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM placenta_cases WHERE id = ? AND statut != 'supprime'",
            (case_id,),
        ).fetchone()
        return _enrich_case(row) if row else None


def get_case_by_numero(numero: str) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM placenta_cases WHERE numero_dossier = ?", (numero,)
        ).fetchone()
        return _enrich_case(row) if row else None


# ── Recherche par labels/annotations pathologiques (Lumi lames.db) ────────
# Le viewer Lumi stocke les labels slide-level (diagnoses/annotation_diagnosis)
# et les annotations (annotations) dans lames.db, avec des codes FOETO résolus
# en français via foeto_terms. On indexe uniquement le pathologique : on exclut
# les axes développementaux normaux (architecture/maturation) et les mentions
# « normal / RAS ».
LAMES_DB_PATH = os.environ.get("LAMES_DB_PATH", "/media/SSDsamsung/db/lames.db")
FOETO_DB_PATH = os.environ.get(
    "FOETO_DB_PATH", "/home/mathevet/Bureau/foeto_base/syndromes_foetaux.db"
)
_NORMAL_AXES = {"architecture", "maturation"}
_NORMAL_KW = ("normal", "sans particularit", " ras")


def _is_normal(text: str) -> bool:
    """Vrai si le libellé décrit du normal (structure saine, RAS…). Garde
    « anormal » du bon côté (pathologique)."""
    t = text.lower()
    if "anormal" in t:
        return False
    return any(kw in t for kw in _NORMAL_KW)


@lru_cache(maxsize=1)
def _foeto_patho_labels() -> dict:
    """code FOETO → label_fr, pour les termes non-normaux uniquement.

    ponytail: caché process-life ; foeto_terms bouge rarement — relancer le
    serveur pour rafraîchir.
    """
    if not os.path.exists(FOETO_DB_PATH):
        return {}
    try:
        conn = sqlite3.connect(f"file:{FOETO_DB_PATH}?mode=ro", uri=True)
        try:
            return {
                cid: (lab or "")
                for cid, lab, axis in conn.execute(
                    "SELECT id, label_fr, axis FROM foeto_terms"
                )
                if axis not in _NORMAL_AXES
            }
        finally:
            conn.close()
    except sqlite3.Error:
        return {}


def _pathology_dossiers(search: str) -> set[str]:
    """Dossiers dont une lame porte un label slide-level ou une annotation
    pathologique correspondant à `search`. Set vide si lames.db injoignable."""
    q = search.strip().lower()
    if not q or not os.path.exists(LAMES_DB_PATH):
        return set()
    codes = _foeto_patho_labels()
    try:
        conn = sqlite3.connect(f"file:{LAMES_DB_PATH}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """SELECT slide_id, diagnosis FROM diagnoses
                   UNION ALL SELECT slide_id, diagnosis FROM annotation_diagnosis
                   UNION ALL SELECT slide_id, label FROM annotations
                   UNION ALL SELECT slide_id, ann_class FROM annotations"""
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return set()

    hits = set()
    for slide_id, txt in rows:
        if not txt:
            continue
        # Code FOETO normal (axe dev) → absent du dict patho, on l'ignore.
        if txt.startswith("FOETO:") and txt not in codes:
            continue
        hay = f"{txt} {codes.get(txt, '')}".lower()
        if _is_normal(hay):
            continue
        if q in hay:
            hits.add(slide_id.split("_")[0])  # slide_id = {dossier}_{bloc}_{n}
    return hits


def list_cases(statut: str = None, search: str = None, assigned_to: str = None) -> list[dict]:
    query = "SELECT * FROM placenta_cases"
    params = []
    conditions = []

    if statut:
        conditions.append("statut = ?")
        params.append(statut)
    else:
        conditions.append("statut != 'supprime'")
    if search:
        patho = _pathology_dossiers(search)
        if patho:
            placeholders = ",".join("?" * len(patho))
            conditions.append(
                f"(numero_dossier LIKE ? OR numero_dossier IN ({placeholders}))"
            )
            params.append(f"%{search}%")
            params.extend(sorted(patho))
        else:
            conditions.append("numero_dossier LIKE ?")
            params.append(f"%{search}%")
    if assigned_to:
        conditions.append("assigned_to = ?")
        params.append(assigned_to)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC"

    with _mgr.connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_enrich_case(r) for r in rows]


def delete_case(case_id: int) -> bool:
    with _mgr.connect() as conn:
        cur = conn.execute(
            f"UPDATE {_mgr.cases_table} SET statut = 'supprime', updated_at = datetime('now') WHERE id = ?",
            (case_id,),
        )
        return cur.rowcount > 0


# ── Module Data (délégué à db_core) ─────────────────────────────────────

def save_module_data(case_id: int, module_name: str, data: dict, user: str = "") -> bool:
    return _mgr.save_module_data(case_id, module_name, data, user=user)


def get_module_data(case_id: int, module_name: str) -> Optional[dict]:
    return _mgr.get_module_data(case_id, module_name)


def get_all_modules(case_id: int) -> dict[str, dict]:
    return _mgr.get_all_modules(case_id)


# ── Photos (spécifique placenta) ─────────────────────────────────────────

def save_photo(case_id: int, photo_key: str, filename: str,
               label: str = "", module: str = "", file_path: str = "",
               size_bytes: int = 0, user: str = "") -> int:
    now = _now()
    with _mgr.connect() as conn:
        cur = conn.execute(
            """INSERT INTO placenta_photos
               (case_id, photo_key, filename, label, module, file_path, size_bytes, uploaded_at, uploaded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(case_id, photo_key)
               DO UPDATE SET filename = excluded.filename,
                             label = excluded.label,
                             module = excluded.module,
                             file_path = excluded.file_path,
                             size_bytes = excluded.size_bytes,
                             uploaded_at = excluded.uploaded_at,
                             uploaded_by = excluded.uploaded_by""",
            (case_id, photo_key, filename, label, module, file_path, size_bytes, now, user),
        )
        return cur.lastrowid


def get_photos(case_id: int, module: str = None) -> list[dict]:
    query = "SELECT * FROM placenta_photos WHERE case_id = ?"
    params = [case_id]
    if module:
        query += " AND module = ?"
        params.append(module)
    query += " ORDER BY photo_key"
    with _mgr.connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]


# ── Import depuis JSON ──────────────────────────────────────────────────

def import_from_macro_frais_json(data: dict, user: str = "") -> Optional[int]:
    """Importe un cas depuis le JSON généré par la PWA macro_frais."""
    numero = data.get("dossier")
    if not numero:
        return None

    terme = data.get("terme", {})
    foetus = data.get("foetus", {})
    bio = data.get("biometrie", {})

    case_data = {
        "numero_dossier": numero,
        "terme_sa": terme.get("sa"),
        "terme_jours": terme.get("jours", 0),
        "terme_source": terme.get("source"),
        "masse_foetale_g": foetus.get("masse_g"),
        "sexe": foetus.get("sexe"),
        "indication_terme": foetus.get("indication_autre") or foetus.get("indication_terme"),
        "grand_axe_cm": bio.get("grand_axe_cm"),
        "petit_axe_cm": bio.get("petit_axe_cm"),
        "epaisseur_cm": bio.get("epaisseur_cm"),
        "masse_paree_g": bio.get("masse_paree_g"),
        "forme": data.get("forme"),
        "completude": data.get("completude", []),
        "plaque_choriale": data.get("plaque_choriale", {}),
        "plaque_basale": data.get("plaque_basale", {}),
        "cordon": data.get("cordon", {}),
        "membranes": data.get("membranes", {}),
    }

    existing = get_case_by_numero(numero)
    if existing:
        case_id = existing["id"]
        update_case(case_id, case_data, user=user)
    else:
        case_id = create_case(case_data, user=user)

    save_module_data(case_id, "macro_frais", data, user=user)
    return case_id


# ── CR Templates CRUD ──────────────────────────────────────────────────

def list_cr_templates() -> list[dict]:
    with _mgr.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM templates ORDER BY is_default DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_cr_template(template_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        return dict(row) if row else None


def create_cr_template(name: str, ttype: str, content: str,
                       is_default: int = 0) -> int:
    with _mgr.connect() as conn:
        cur = conn.execute(
            "INSERT INTO templates (name, type, content_jinja2, is_default) "
            "VALUES (?, ?, ?, ?)",
            (name, ttype, content, is_default),
        )
        return cur.lastrowid


def update_cr_template(template_id: int, name: str, ttype: str,
                       content: str):
    with _mgr.connect() as conn:
        conn.execute(
            "UPDATE templates SET name=?, type=?, content_jinja2=?, "
            "updated_at=? WHERE id=?",
            (name, ttype, content, _now(), template_id),
        )


def delete_cr_template(template_id: int):
    with _mgr.connect() as conn:
        conn.execute(
            "DELETE FROM generated_docs WHERE template_id = ?",
            (template_id,),
        )
        conn.execute(
            "DELETE FROM templates WHERE id = ? AND is_default = 0",
            (template_id,),
        )


def duplicate_cr_template(template_id: int) -> int | None:
    tpl = get_cr_template(template_id)
    if not tpl:
        return None
    return create_cr_template(
        tpl["name"] + " (copie)", tpl["type"], tpl["content_jinja2"]
    )


# ── Generated Docs CRUD ───────────────────────────────────────────────

def save_generated_doc(case_id: int, template_id,
                       html: str, text: str) -> int:
    with _mgr.connect() as conn:
        cur = conn.execute(
            "INSERT INTO generated_docs "
            "(case_id, template_id, content_html, content_text) "
            "VALUES (?, ?, ?, ?)",
            (case_id, template_id, html, text),
        )
        return cur.lastrowid


def list_generated_docs(case_id: int) -> list[dict]:
    with _mgr.connect() as conn:
        rows = conn.execute("""
            SELECT id, template_id, content_html, content_text, generated_at
            FROM generated_docs
            WHERE case_id = ?
            ORDER BY generated_at DESC
        """, (case_id,)).fetchall()
        return [dict(r) for r in rows]


def get_generated_doc(doc_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute(
            "SELECT * FROM generated_docs WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_generated_doc(doc_id: int):
    with _mgr.connect() as conn:
        conn.execute(
            "DELETE FROM generated_docs WHERE id = ?", (doc_id,)
        )
