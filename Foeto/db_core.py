#!/usr/bin/env python3
"""
FoetoPath — Infrastructure BDD partagée.

Fournit DatabaseManager, une classe réutilisable pour les opérations
SQLite communes entre foetopath.db et placenta.db :
  - Gestion connexion (WAL, foreign keys, context manager)
  - Helpers (timestamps, row→dict)
  - Module data CRUD (JSON blobs)
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional



log = logging.getLogger(__name__)


def _now() -> str:
    """Timestamp ISO UTC."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convertit un sqlite3.Row en dict."""
    return dict(row) if row else {}


class DatabaseManager:
    """Gestionnaire SQLite partagé pour foetus et placenta.

    Paramètres :
        db_name      : nom du fichier (ex: "foetopath.db")
        cases_table  : nom de la table cases (ex: "cases" ou "placenta_cases")
        modules_table: nom de la table modules (ex: "module_data" ou "placenta_modules")
    """

    def __init__(self, db_name: str, cases_table: str, modules_table: str):
        self.db_name = db_name
        self.cases_table = cases_table
        self.modules_table = modules_table
        self._db_path: Optional[Path] = None

    # ── Connexion ─────────────────────────────────────────────────────────

    def set_path(self, base_dir: str | Path) -> Path:
        """Configure et retourne le chemin de la BDD."""
        base = Path(base_dir)
        base.mkdir(parents=True, exist_ok=True)
        self._db_path = base / self.db_name
        return self._db_path

    def get_db_path(self) -> Path:
        if self._db_path is None:
            raise RuntimeError(f"DB {self.db_name} non initialisée — appeler init_db() d'abord")
        return self._db_path

    @contextmanager
    def connect(self):
        """Context manager pour connexion SQLite avec WAL + foreign keys."""
        conn = sqlite3.connect(str(self.get_db_path()), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            log.error("Database transaction failed, rolling back", exc_info=True)
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Module Data (JSON blobs) ──────────────────────────────────────────

    def save_module_data(self, case_id: int, module_name: str, data: dict,
                         user: str = "") -> bool:
        """Upsert les données JSON d'un module pour un cas."""
        now = _now()
        json_str = json.dumps(data, ensure_ascii=False)
        with self.connect() as conn:
            # Colonnes de la table modules (avec ou sans modified_by)
            if user:
                conn.execute(
                    f"""INSERT INTO {self.modules_table}
                        (case_id, module_name, data_json, updated_at, modified_by)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(case_id, module_name)
                        DO UPDATE SET data_json = excluded.data_json,
                                      updated_at = excluded.updated_at,
                                      modified_by = excluded.modified_by""",
                    (case_id, module_name, json_str, now, user),
                )
            else:
                conn.execute(
                    f"""INSERT INTO {self.modules_table}
                        (case_id, module_name, data_json, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(case_id, module_name)
                        DO UPDATE SET data_json = excluded.data_json,
                                      updated_at = excluded.updated_at""",
                    (case_id, module_name, json_str, now),
                )
            # Mettre à jour le timestamp du cas
            update_sql = f"UPDATE {self.cases_table} SET updated_at = ?"
            params = [now]
            if user:
                update_sql += ", modified_by = ?"
                params.append(user)
            update_sql += " WHERE id = ?"
            params.append(case_id)
            conn.execute(update_sql, params)
            return True

    def get_module_data(self, case_id: int, module_name: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT data_json FROM {self.modules_table} WHERE case_id = ? AND module_name = ?",
                (case_id, module_name),
            ).fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def get_all_modules(self, case_id: int) -> dict[str, dict]:
        """Récupère tous les modules d'un cas."""
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT module_name, data_json, updated_at FROM {self.modules_table} WHERE case_id = ?",
                (case_id,),
            ).fetchall()
            return {
                r["module_name"]: {
                    "data": json.loads(r["data_json"]),
                    "updated_at": r["updated_at"],
                }
                for r in rows
            }

    # ── Cases — Lecture / Suppression ─────────────────────────────────────

    def get_case(self, case_id: int) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.cases_table} WHERE id = ?", (case_id,)
            ).fetchone()
            return _row_to_dict(row) if row else None

    def get_case_by_numero(self, numero: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.cases_table} WHERE numero_dossier = ?", (numero,)
            ).fetchone()
            return _row_to_dict(row) if row else None

    def delete_case(self, case_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                f"DELETE FROM {self.cases_table} WHERE id = ?", (case_id,)
            )
            return cur.rowcount > 0

    def list_cases(self, statut: str = None, search: str = None,
                   search_fields: list[str] = None) -> list[dict]:
        """Liste les cas avec filtre optionnel.

        search_fields : colonnes sur lesquelles chercher (défaut: ["numero_dossier"])
        """
        if search_fields is None:
            search_fields = ["numero_dossier"]

        query = f"SELECT * FROM {self.cases_table}"
        params = []
        conditions = []

        if statut:
            conditions.append("statut = ?")
            params.append(statut)
        if search:
            like_clauses = [f"{f} LIKE ?" for f in search_fields]
            conditions.append(f"({' OR '.join(like_clauses)})")
            s = f"%{search}%"
            params.extend([s] * len(search_fields))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC"

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [_row_to_dict(r) for r in rows]
