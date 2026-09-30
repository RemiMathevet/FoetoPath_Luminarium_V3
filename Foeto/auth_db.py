#!/usr/bin/env python3
"""
FoetoPath — Module d'authentification & gestion des utilisateurs.

Rôles :
  admin         Tous les droits. Crée / supprime tous les profils.
  admin_centre  Crée admin_centre et user. Accès complet aux cas.
  user          Crée et consulte les cas.
  spectator     Consulte les cas (lecture seule).

L'administrateur principal (Remi_Mathevet) est créé automatiquement
au premier lancement avec un mot de passe en dur.
"""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import pyotp

from db_core import open_db

log = logging.getLogger(__name__)

# ── Hachage Argon2id (conforme HDS) ─────────────────────────────────────
# Remplace SHA-256+sel. Les anciens hashes sont migrés au prochain login.

_ph = PasswordHasher()  # Argon2id par défaut, paramètres sûrs


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash un mot de passe avec Argon2id.
    Le champ salt est conservé pour compatibilité de schéma (vide pour Argon2).
    Retourne (argon2_hash, salt_marker).
    """
    h = _ph.hash(password)
    return h, "argon2"  # Marqueur pour identifier le format


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Vérifie un mot de passe contre le hash stocké.
    Supporte à la fois l'ancien format SHA-256+sel et le nouveau Argon2id.
    """
    if salt == "argon2" or stored_hash.startswith("$argon2"):
        try:
            return _ph.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    else:
        h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return h == stored_hash


def _needs_rehash(stored_hash: str, salt: str) -> bool:
    """Retourne True si le hash doit être mis à jour (legacy ou paramètres Argon2 obsolètes)."""
    if salt != "argon2" or not stored_hash.startswith("$argon2"):
        return True  # Legacy SHA-256 → migrer
    try:
        return _ph.check_needs_rehash(stored_hash)
    except Exception:
        return False


# ── Rôles & permissions ──────────────────────────────────────────────────

ROLES = ("admin", "admin_centre", "user", "spectator")

PERMISSIONS = {
    "admin": {
        "can_manage_users": True,
        "can_create_roles": ["admin_centre", "user", "spectator"],
        "can_delete_users": True,
        "can_write_cases": True,
        "can_delete_cases": True,
        "can_read_cases": True,
    },
    "admin_centre": {
        "can_manage_users": True,
        "can_create_roles": ["admin_centre", "user", "spectator"],
        "can_delete_users": False,
        "can_write_cases": True,
        "can_delete_cases": True,
        "can_read_cases": True,
    },
    "user": {
        "can_manage_users": False,
        "can_create_roles": [],
        "can_delete_users": False,
        "can_write_cases": True,
        "can_delete_cases": False,
        "can_read_cases": True,
    },
    "spectator": {
        "can_manage_users": False,
        "can_create_roles": [],
        "can_delete_users": False,
        "can_write_cases": False,
        "can_delete_cases": False,
        "can_read_cases": True,
    },
}


def get_permissions(role: str) -> dict:
    return PERMISSIONS.get(role, PERMISSIONS["spectator"])


# ── Base de données ──────────────────────────────────────────────────────

_db_path: str | None = None


def init_db(data_dir: str) -> str:
    """Initialise la table users dans auth.db et crée l'admin par défaut."""
    global _db_path
    p = Path(data_dir)
    p.mkdir(parents=True, exist_ok=True)
    _db_path = str(p / "auth.db")

    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                salt        TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'spectator',
                display_name TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                created_by  TEXT DEFAULT '',
                last_login  TEXT DEFAULT '',
                active      INTEGER DEFAULT 1
            )
        """)

    with _connect() as con:
        existing_cols = {row[1] for row in con.execute("PRAGMA table_info(users)").fetchall()}
        if "totp_secret" not in existing_cols:
            con.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT DEFAULT ''")
            log.info("Migration: ajout colonne totp_secret")
        if "totp_backup_codes" not in existing_cols:
            con.execute("ALTER TABLE users ADD COLUMN totp_backup_codes TEXT DEFAULT ''")
            log.info("Migration: ajout colonne totp_backup_codes")

    with _connect() as con:
        row = con.execute(
            "SELECT id FROM users WHERE username = ?", ("Remi_Mathevet",)
        ).fetchone()
        if not row:
            initial_password = secrets.token_urlsafe(12)
            pw_hash, salt = _hash_password(initial_password)
            con.execute(
                "INSERT INTO users (username, password, salt, role, display_name, created_by) "
                "VALUES (?, ?, ?, 'admin', 'Rémi Mathevet', 'system')",
                ("Remi_Mathevet", pw_hash, salt),
            )
            print(f"\n{'='*60}")
            print(f"  ⚠️  Mot de passe admin initial : {initial_password}")
            print(f"  Utilisateur : Remi_Mathevet")
            print(f"  ⚠️  Changez-le immédiatement après la première connexion !")
            print(f"{'='*60}\n")

    return _db_path


@contextmanager
def _connect():
    if _db_path is None:
        raise RuntimeError("auth_db.init_db() n'a pas été appelé")
    conn = open_db(_db_path, foreign_keys=False, row_factory=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row, cursor) -> dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


# ── Authentification ─────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> dict | None:
    """Vérifie les identifiants. Retourne le user dict ou None.
    Migre automatiquement les hashes legacy vers Argon2id au login réussi.
    """
    with _connect() as con:
        cur = con.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        )
        row = cur.fetchone()
        if not row:
            return None
        user = _row_to_dict(row, cur)

    if not _verify_password(password, user["password"], user["salt"]):
        return None

    if _needs_rehash(user["password"], user["salt"]):
        new_hash, new_salt = _hash_password(password)
        with _connect() as con:
            con.execute(
                "UPDATE users SET password = ?, salt = ? WHERE id = ?",
                (new_hash, new_salt, user["id"]),
            )
        log.info("Migrated password hash to Argon2id for user %s", username)

    with _connect() as con:
        con.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user["id"]),
        )

    user.pop("password", None)
    user.pop("salt", None)
    return user


# ── CRUD Utilisateurs ────────────────────────────────────────────────────

def create_user(username: str, password: str, role: str,
                display_name: str = "", created_by: str = "") -> int | None:
    """Crée un utilisateur. Retourne l'id ou None si le username existe déjà."""
    if role not in ROLES:
        return None
    pw_hash, salt = _hash_password(password)
    try:
        with _connect() as con:
            cur = con.execute(
                "INSERT INTO users (username, password, salt, role, display_name, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, pw_hash, salt, role, display_name, created_by),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def update_user(user_id: int, data: dict) -> bool:
    """Met à jour un utilisateur (display_name, role, active).
    Si 'password' est dans data, le re-hashe."""
    allowed = {"display_name", "role", "active"}
    fields = {k: v for k, v in data.items() if k in allowed}

    if "password" in data and data["password"]:
        pw_hash, salt = _hash_password(data["password"])
        fields["password"] = pw_hash
        fields["salt"] = salt

    if not fields:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    with _connect() as con:
        con.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    return True


def delete_user(user_id: int) -> bool:
    with _connect() as con:
        cur = con.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cur.rowcount > 0


def _sanitize_user(user: dict) -> dict:
    """Retire les champs sensibles d'un dict utilisateur."""
    user.pop("password", None)
    user.pop("salt", None)
    user.pop("totp_backup_codes", None)
    user["totp_enabled"] = bool(user.pop("totp_secret", ""))
    return user


def get_user(user_id: int) -> dict | None:
    with _connect() as con:
        cur = con.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return _sanitize_user(_row_to_dict(row, cur))


def get_user_by_username(username: str) -> dict | None:
    with _connect() as con:
        cur = con.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            return None
        return _sanitize_user(_row_to_dict(row, cur))


def list_users() -> list[dict]:
    with _connect() as con:
        cur = con.execute("SELECT * FROM users ORDER BY role, username")
        rows = cur.fetchall()
        users = [_row_to_dict(r, cur) for r in rows]
    for u in users:
        _sanitize_user(u)
    return users


# ── 2FA TOTP ────────────────────────────────────────────────────────────

TOTP_ISSUER = "FoetoPath"
TOTP_BACKUP_COUNT = 8


def totp_generate_secret() -> str:
    """Génère un secret TOTP base32 aléatoire."""
    return pyotp.random_base32()


def totp_get_provisioning_uri(secret: str, username: str) -> str:
    """Retourne l'URI otpauth:// pour le QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=TOTP_ISSUER)


def totp_verify(secret: str, code: str) -> bool:
    """Vérifie un code TOTP (window +/-1 = 90 secondes de tolérance)."""
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=1)


def _generate_backup_codes() -> list[str]:
    """Génère TOTP_BACKUP_COUNT codes de récupération à usage unique."""
    return [secrets.token_hex(4).upper() for _ in range(TOTP_BACKUP_COUNT)]


def _hash_backup_codes(codes: list[str]) -> str:
    """Stocke les codes hashés en JSON (Argon2id chacun)."""
    hashed = [_ph.hash(c) for c in codes]
    return json.dumps(hashed)


def totp_enroll(user_id: int, secret: str) -> list[str]:
    """Active le TOTP pour un utilisateur. Retourne les backup codes en clair
    (à afficher une seule fois)."""
    backup_codes = _generate_backup_codes()
    hashed_json = _hash_backup_codes(backup_codes)
    with _connect() as con:
        con.execute(
            "UPDATE users SET totp_secret = ?, totp_backup_codes = ? WHERE id = ?",
            (secret, hashed_json, user_id),
        )
    log.info("TOTP enrolled for user_id=%s", user_id)
    return backup_codes


def totp_is_enabled(user_id: int) -> bool:
    """Retourne True si le TOTP est activé pour cet utilisateur."""
    with _connect() as con:
        row = con.execute(
            "SELECT totp_secret FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return bool(row and row[0])


def totp_get_secret(user_id: int) -> str:
    """Retourne le secret TOTP d'un utilisateur (usage interne uniquement)."""
    with _connect() as con:
        row = con.execute(
            "SELECT totp_secret FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else ""


def totp_verify_backup_code(user_id: int, code: str) -> bool:
    """Vérifie et consomme un code de récupération (usage unique).
    Retourne True si le code est valide."""
    code = code.strip().upper()
    with _connect() as con:
        row = con.execute(
            "SELECT totp_backup_codes FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row or not row[0]:
            return False

        try:
            hashed_codes = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return False

        for i, h in enumerate(hashed_codes):
            try:
                if _ph.verify(h, code):
                    hashed_codes.pop(i)
                    con.execute(
                        "UPDATE users SET totp_backup_codes = ? WHERE id = ?",
                        (json.dumps(hashed_codes), user_id),
                    )
                    log.info("Backup code used for user_id=%s (%d remaining)",
                             user_id, len(hashed_codes))
                    return True
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                continue

        return False


def totp_reset(user_id: int):
    """Désactive le TOTP et supprime les backup codes (reset admin)."""
    with _connect() as con:
        con.execute(
            "UPDATE users SET totp_secret = '', totp_backup_codes = '' WHERE id = ?",
            (user_id,),
        )
    log.info("TOTP reset for user_id=%s", user_id)
