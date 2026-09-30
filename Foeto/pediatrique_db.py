"""
FoetoPath — Module BDD SQLite pour les cas pédiatriques.

DB indépendante (pediatrique.db), même pattern que placenta_db.py.
Tables : ped_cases, ped_modules, ped_details.
Utilise db_core.DatabaseManager pour les opérations communes.
"""

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

from config import KNOWN_MODULES_PEDIATRIQUE
from db_core import DatabaseManager, _now, _row_to_dict

log = logging.getLogger(__name__)

_mgr = DatabaseManager(
    db_name="pediatrique.db",
    cases_table="ped_cases",
    modules_table="ped_modules",
)

KNOWN_MODULES = KNOWN_MODULES_PEDIATRIQUE

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ped_cases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_dossier      TEXT UNIQUE NOT NULL,
    sexe                TEXT,
    nom_mere            TEXT,
    prenom_mere         TEXT,
    ddn_mere            TEXT,
    dossier_macro_path  TEXT,
    dossier_lames_path  TEXT,
    statut              TEXT DEFAULT 'en_cours',
    assigned_to         TEXT DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    created_by          TEXT DEFAULT '',
    modified_by         TEXT DEFAULT '',
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS ped_modules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES ped_cases(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    data_json   TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL,
    modified_by TEXT DEFAULT '',
    UNIQUE(case_id, module_name)
);

CREATE TABLE IF NOT EXISTS ped_details (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id                 INTEGER NOT NULL UNIQUE REFERENCES ped_cases(id) ON DELETE CASCADE,
    date_naissance          TEXT,
    heure_naissance         TEXT,
    terme_naissance_sa      INTEGER,
    terme_naissance_jours   INTEGER,
    mode_accouchement       TEXT,
    poids_naissance_g       REAL,
    taille_naissance_cm     REAL,
    pc_naissance_mm         REAL,
    apgar_1                 INTEGER,
    apgar_5                 INTEGER,
    apgar_10                INTEGER,
    date_deces              TEXT,
    heure_deces             TEXT,
    age_deces_jours         INTEGER,
    lieu_deces              TEXT,
    cause_deces_principale  TEXT,
    contexte_deces          TEXT,
    reanimation             BOOLEAN,
    poids_deces_g           REAL,
    taille_deces_cm         REAL,
    pc_deces_mm             REAL,
    autopsie_consentement   BOOLEAN,
    autopsie_type           TEXT,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (autopsie_type IN ('complete', 'limitee', 'refusee') OR autopsie_type IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_ped_numero ON ped_cases(numero_dossier);
CREATE INDEX IF NOT EXISTS idx_ped_mod    ON ped_modules(case_id, module_name);
"""

DETAIL_FIELDS = [
    "date_naissance", "heure_naissance", "terme_naissance_sa", "terme_naissance_jours",
    "mode_accouchement", "poids_naissance_g", "taille_naissance_cm", "pc_naissance_mm",
    "apgar_1", "apgar_5", "apgar_10",
    "date_deces", "heure_deces", "age_deces_jours", "lieu_deces",
    "cause_deces_principale", "contexte_deces", "reanimation",
    "poids_deces_g", "taille_deces_cm", "pc_deces_mm",
    "autopsie_consentement", "autopsie_type",
]


# ── Init ─────────────────────────────────────────────────────────────────

def init_db(base_dir: str | Path) -> Path:
    db_path = _mgr.set_path(base_dir)
    with _mgr.connect() as conn:
        conn.executescript(_SCHEMA)
    return db_path


def get_db_path() -> Path:
    return _mgr.get_db_path()


# ── Helpers ──────────────────────────────────────────────────────────────

def _get_data_root() -> str:
    try:
        import db as foetopath_db
        return foetopath_db.get_setting("data_root", "")
    except Exception:
        return ""


def _resolve_path(rel_path: str | None) -> str | None:
    if not rel_path or os.path.isabs(rel_path):
        return rel_path
    root = _get_data_root()
    return str(Path(root) / rel_path) if root else rel_path


def _to_relative_path(abs_path: str | None) -> str | None:
    if not abs_path:
        return abs_path
    root = _get_data_root()
    if root and abs_path.startswith(root):
        rel = abs_path[len(root):].lstrip("/")
        return rel if rel else abs_path
    return abs_path


# ── CRUD Cases ───────────────────────────────────────────────────────────

def create_case(data: dict, user: str = "") -> int:
    now = _now()
    numero = data.get("numero_dossier")
    if not numero:
        raise ValueError("numero_dossier requis")
    with _mgr.connect() as conn:
        cur = conn.execute(
            """INSERT INTO ped_cases
               (numero_dossier, sexe, nom_mere, prenom_mere, ddn_mere,
                dossier_macro_path, statut, notes, assigned_to,
                created_at, updated_at, created_by, modified_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, data.get("sexe"), data.get("nom_mere"), data.get("prenom_mere"),
             data.get("ddn_mere"), data.get("dossier_macro_path"),
             data.get("statut", "en_cours"), data.get("notes"),
             data.get("assigned_to", ""), now, now, user, user),
        )
        return cur.lastrowid


def update_case(case_id: int, data: dict, user: str = "") -> bool:
    now = _now()
    scalars = [
        "numero_dossier", "sexe", "nom_mere", "prenom_mere", "ddn_mere",
        "dossier_macro_path", "dossier_lames_path", "statut", "notes", "assigned_to",
    ]
    sets, vals = [], []
    for k in scalars:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(now)
    if user:
        sets.append("modified_by = ?")
        vals.append(user)
    vals.append(case_id)
    with _mgr.connect() as conn:
        conn.execute(f"UPDATE ped_cases SET {', '.join(sets)} WHERE id = ?", vals)
    return True


def get_case(case_id: int) -> Optional[dict]:
    return _mgr.get_case(case_id)


def get_case_by_numero(numero: str) -> Optional[dict]:
    return _mgr.get_case_by_numero(numero)


def list_cases(statut: str = None, search: str = None) -> list[dict]:
    with _mgr.connect() as conn:
        query = "SELECT * FROM ped_cases"
        clauses, params = [], []
        if statut:
            clauses.append("statut = ?")
            params.append(statut)
        if search:
            clauses.append("(numero_dossier LIKE ? OR nom_mere LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        return [_row_to_dict(r) for r in conn.execute(query, params).fetchall()]


def delete_case(case_id: int) -> bool:
    with _mgr.connect() as conn:
        conn.execute("DELETE FROM ped_cases WHERE id = ?", (case_id,))
    return True


# ── Module data (delegates to DatabaseManager) ──────────────────────────

def save_module_data(case_id: int, module_name: str, data: dict, user: str = "") -> bool:
    return _mgr.save_module_data(case_id, module_name, data, user)


def get_module_data(case_id: int, module_name: str) -> Optional[dict]:
    return _mgr.get_module_data(case_id, module_name)


def get_all_modules(case_id: int) -> dict:
    return _mgr.get_all_modules(case_id)


# ── Pediatric details ───────────────────────────────────────────────────

def get_pediatric_details(case_id: int) -> Optional[dict]:
    with _mgr.connect() as conn:
        row = conn.execute("SELECT * FROM ped_details WHERE case_id = ?", (case_id,)).fetchone()
        return _row_to_dict(row) if row else None


def save_pediatric_details(case_id: int, data: dict):
    now = _now()
    fields = {k: data[k] for k in DETAIL_FIELDS if k in data}
    fields["updated_at"] = now
    with _mgr.connect() as conn:
        existing = conn.execute("SELECT id FROM ped_details WHERE case_id = ?", (case_id,)).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE ped_details SET {sets} WHERE case_id = ?",
                         [*fields.values(), case_id])
        else:
            fields["case_id"] = case_id
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" * len(fields))
            conn.execute(f"INSERT INTO ped_details ({cols}) VALUES ({placeholders})",
                         list(fields.values()))
