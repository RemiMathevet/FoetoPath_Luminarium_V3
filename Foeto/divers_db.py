"""Modèle de données pour les cas divers (curetage, placenta gémellaire).

Utilise la même base foetopath.db que le module principal, via db._mgr.connect()
pour bénéficier du context manager partagé (WAL, foreign keys, auto-commit/rollback).
"""

import json
import logging

from db_core import _now

log = logging.getLogger(__name__)

TABLE_NAME = "cas_divers"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cas_divers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Type de cas (clé de routage vers le bon template)
    type_cas      TEXT NOT NULL CHECK(type_cas IN ('curetage', 'gemellaire')),

    -- Champs communs (identiques à tous les templates)
    dossier       TEXT,
    date_prel     TEXT,
    operateur     TEXT,
    ag_sa         INTEGER,
    ag_j          INTEGER DEFAULT 0,
    indication    TEXT,
    etat          TEXT DEFAULT 'frais',

    -- Données spécifiques au type (tout le formulaire sérialisé)
    form_data     TEXT NOT NULL DEFAULT '{}',

    -- Compte-rendu généré
    cr_text       TEXT,

    -- Métadonnées
    user_id       INTEGER,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),

    -- Soft delete
    deleted       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cas_divers_type ON cas_divers(type_cas);
CREATE INDEX IF NOT EXISTS idx_cas_divers_dossier ON cas_divers(dossier);
CREATE INDEX IF NOT EXISTS idx_cas_divers_date ON cas_divers(created_at);
"""


def _connect():
    """Réutilise le context manager de db._mgr (même DB foetopath.db)."""
    import db
    return db._connect()


def init_table():
    with _connect() as conn:
        conn.executescript(SCHEMA)


def save_cas(data):
    type_cas = data.get('type_cas', '')
    if type_cas not in ('curetage', 'gemellaire'):
        raise ValueError(f"type_cas invalide : {type_cas}")

    form_data = data.get('form_data', {})
    if isinstance(form_data, dict):
        form_data_json = json.dumps(form_data, ensure_ascii=False)
    else:
        form_data_json = str(form_data)

    now = _now()
    cas_id = data.get('id')

    with _connect() as conn:
        if cas_id:
            conn.execute("""
                UPDATE cas_divers SET
                    type_cas = ?, dossier = ?, date_prel = ?, operateur = ?,
                    ag_sa = ?, ag_j = ?, indication = ?, etat = ?,
                    form_data = ?, cr_text = ?, updated_at = ?
                WHERE id = ? AND deleted = 0
            """, (
                type_cas, data.get('dossier'), data.get('date_prel'), data.get('operateur'),
                data.get('ag_sa'), data.get('ag_j', 0), data.get('indication'), data.get('etat', 'frais'),
                form_data_json, data.get('cr_text'), now,
                cas_id
            ))
            return cas_id
        else:
            cursor = conn.execute("""
                INSERT INTO cas_divers
                    (type_cas, dossier, date_prel, operateur, ag_sa, ag_j,
                     indication, etat, form_data, cr_text, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                type_cas, data.get('dossier'), data.get('date_prel'), data.get('operateur'),
                data.get('ag_sa'), data.get('ag_j', 0), data.get('indication'), data.get('etat', 'frais'),
                form_data_json, data.get('cr_text'), data.get('user_id'),
                now, now
            ))
            return cursor.lastrowid


def load_cas(cas_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cas_divers WHERE id = ? AND deleted = 0", (cas_id,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        if d.get('form_data'):
            try:
                d['form_data'] = json.loads(d['form_data'])
            except (json.JSONDecodeError, TypeError):
                d['form_data'] = {}
        return d


def list_cas(type_cas=None, limit=50, offset=0):
    with _connect() as conn:
        if type_cas and type_cas in ('curetage', 'gemellaire'):
            rows = conn.execute(
                """SELECT id, type_cas, dossier, date_prel, operateur, ag_sa, ag_j,
                          indication, etat, created_at, updated_at
                   FROM cas_divers WHERE deleted = 0 AND type_cas = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (type_cas, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, type_cas, dossier, date_prel, operateur, ag_sa, ag_j,
                          indication, etat, created_at, updated_at
                   FROM cas_divers WHERE deleted = 0
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()
        return [dict(r) for r in rows]


def soft_delete_cas(cas_id):
    with _connect() as conn:
        conn.execute(
            "UPDATE cas_divers SET deleted = 1, updated_at = ? WHERE id = ?",
            (_now(), cas_id)
        )
    return True
