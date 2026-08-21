#!/usr/bin/env python3
"""
FoetoPath — Module d'audit (append-only).

Table audit_log dans audit.db (base dédiée, jamais modifiée/supprimée).
Helper log_audit() appelable depuis n'importe quel module.

Actions typiques :
  login, login_failed, logout, view_case, edit_case, create_case,
  delete_case, export, create_user, update_user, delete_user,
  view_settings, update_settings
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import request, session

log = logging.getLogger(__name__)

_db_path: Optional[str] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
    user_id         INTEGER,
    username        TEXT,
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    ip_address      TEXT,
    user_agent      TEXT,
    details         TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action    ON audit_log(action);
"""


def init_db(data_dir: str) -> str:
    """Initialise audit.db dans le répertoire de données."""
    global _db_path
    p = Path(data_dir)
    p.mkdir(parents=True, exist_ok=True)
    _db_path = str(p / "audit.db")

    with _connect() as con:
        con.executescript(_SCHEMA)
    return _db_path


@contextmanager
def _connect():
    if _db_path is None:
        raise RuntimeError("audit.init_db() n'a pas été appelé")
    conn = sqlite3.connect(_db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_audit(
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    details: dict = None,
    user_id: int = None,
    username: str = None,
):
    """Enregistre une entrée d'audit (append-only).

    Si user_id/username ne sont pas fournis, les récupère depuis la session Flask.
    L'IP et le User-Agent sont extraits automatiquement depuis la requête courante.
    """
    try:
        _user_id = user_id
        _username = username
        _ip = None
        _ua = None

        try:
            if _user_id is None:
                _user_id = session.get("user_id")
            if _username is None:
                _username = session.get("username")
            _ip = request.remote_addr
            _ua = request.headers.get("User-Agent", "")[:500]
        except RuntimeError:
            pass

        details_json = json.dumps(details, ensure_ascii=False) if details else None

        with _connect() as con:
            con.execute(
                """INSERT INTO audit_log
                   (timestamp, user_id, username, action, resource_type,
                    resource_id, ip_address, user_agent, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    _user_id,
                    _username,
                    action,
                    resource_type,
                    str(resource_id) if resource_id is not None else None,
                    _ip,
                    _ua,
                    details_json,
                ),
            )
    except Exception:
        log.warning("Failed to write audit log entry", exc_info=True)


def get_recent_logs(limit: int = 100, action: str = None) -> list[dict]:
    """Récupère les dernières entrées d'audit (lecture seule, pour l'admin)."""
    with _connect() as con:
        con.row_factory = sqlite3.Row
        query = "SELECT * FROM audit_log"
        params = []
        if action:
            query += " WHERE action = ?"
            params.append(action)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = con.execute(query, params).fetchall()
        return [dict(r) for r in rows]
