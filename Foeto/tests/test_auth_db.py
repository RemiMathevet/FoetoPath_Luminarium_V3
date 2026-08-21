"""Tests pour auth_db — hashing, authentification, CRUD utilisateurs, TOTP."""

import pytest


class TestPasswordHashing:

    def test_argon2_hash_and_verify(self, auth_db_ready):
        h, salt = auth_db_ready._hash_password("motdepasse123")
        assert h.startswith("$argon2")
        assert salt == "argon2"
        assert auth_db_ready._verify_password("motdepasse123", h, salt)

    def test_wrong_password_fails(self, auth_db_ready):
        h, salt = auth_db_ready._hash_password("correct")
        assert not auth_db_ready._verify_password("incorrect", h, salt)

    def test_legacy_sha256_verify(self, auth_db_ready):
        import hashlib
        salt = "random_salt"
        password = "legacy_pass"
        legacy_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        assert auth_db_ready._verify_password(password, legacy_hash, salt)
        assert not auth_db_ready._verify_password("wrong", legacy_hash, salt)

    def test_legacy_needs_rehash(self, auth_db_ready):
        import hashlib
        salt = "old_salt"
        legacy_hash = hashlib.sha256((salt + "pass").encode("utf-8")).hexdigest()
        assert auth_db_ready._needs_rehash(legacy_hash, salt)

    def test_argon2_no_rehash_needed(self, auth_db_ready):
        h, salt = auth_db_ready._hash_password("password")
        assert not auth_db_ready._needs_rehash(h, salt)


class TestAuthentication:

    def test_authenticate_success(self, auth_db_ready):
        auth_db_ready.create_user("alice", "pass123", "user")
        user = auth_db_ready.authenticate("alice", "pass123")
        assert user is not None
        assert user["username"] == "alice"
        assert user["role"] == "user"
        assert "password" not in user
        assert "salt" not in user

    def test_authenticate_wrong_password(self, auth_db_ready):
        auth_db_ready.create_user("bob", "correct", "user")
        assert auth_db_ready.authenticate("bob", "wrong") is None

    def test_authenticate_nonexistent_user(self, auth_db_ready):
        assert auth_db_ready.authenticate("ghost", "pass") is None

    def test_authenticate_updates_last_login(self, auth_db_ready):
        auth_db_ready.create_user("charlie", "pass", "user")
        auth_db_ready.authenticate("charlie", "pass")
        user = auth_db_ready.get_user_by_username("charlie")
        assert user is not None

    def test_authenticate_migrates_legacy_hash(self, auth_db_ready):
        import hashlib
        import sqlite3
        salt = "old_salt"
        password = "legacy"
        legacy_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

        conn = sqlite3.connect(auth_db_ready._db_path)
        conn.execute(
            "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)",
            ("legacy_user", legacy_hash, salt, "user"),
        )
        conn.commit()
        conn.close()

        user = auth_db_ready.authenticate("legacy_user", password)
        assert user is not None

        conn = sqlite3.connect(auth_db_ready._db_path)
        row = conn.execute(
            "SELECT password, salt FROM users WHERE username = ?", ("legacy_user",)
        ).fetchone()
        conn.close()
        assert row[0].startswith("$argon2")
        assert row[1] == "argon2"

    def test_inactive_user_cannot_login(self, auth_db_ready):
        uid = auth_db_ready.create_user("inactive", "pass", "user")
        auth_db_ready.update_user(uid, {"active": 0})
        assert auth_db_ready.authenticate("inactive", "pass") is None


class TestCrudUsers:

    def test_create_user(self, auth_db_ready):
        uid = auth_db_ready.create_user("newuser", "pass", "user", display_name="New")
        assert uid is not None
        assert isinstance(uid, int)

    def test_create_duplicate_returns_none(self, auth_db_ready):
        auth_db_ready.create_user("dup", "pass", "user")
        assert auth_db_ready.create_user("dup", "pass2", "admin") is None

    def test_create_invalid_role_returns_none(self, auth_db_ready):
        assert auth_db_ready.create_user("bad", "pass", "superadmin") is None

    def test_get_user(self, auth_db_ready):
        uid = auth_db_ready.create_user("getme", "pass", "spectator")
        user = auth_db_ready.get_user(uid)
        assert user is not None
        assert user["username"] == "getme"
        assert user["role"] == "spectator"
        assert "password" not in user
        assert "salt" not in user

    def test_get_user_nonexistent(self, auth_db_ready):
        assert auth_db_ready.get_user(99999) is None

    def test_get_user_by_username(self, auth_db_ready):
        auth_db_ready.create_user("findme", "pass", "user")
        user = auth_db_ready.get_user_by_username("findme")
        assert user is not None
        assert user["username"] == "findme"

    def test_update_user_role(self, auth_db_ready):
        uid = auth_db_ready.create_user("updater", "pass", "user")
        assert auth_db_ready.update_user(uid, {"role": "admin"})
        user = auth_db_ready.get_user(uid)
        assert user["role"] == "admin"

    def test_update_user_password(self, auth_db_ready):
        uid = auth_db_ready.create_user("pwchange", "old_pass", "user")
        auth_db_ready.update_user(uid, {"password": "new_pass"})
        assert auth_db_ready.authenticate("pwchange", "new_pass") is not None
        assert auth_db_ready.authenticate("pwchange", "old_pass") is None

    def test_update_empty_data(self, auth_db_ready):
        uid = auth_db_ready.create_user("nochange", "pass", "user")
        assert auth_db_ready.update_user(uid, {}) is False

    def test_delete_user(self, auth_db_ready):
        uid = auth_db_ready.create_user("deleteme", "pass", "user")
        assert auth_db_ready.delete_user(uid) is True
        assert auth_db_ready.get_user(uid) is None

    def test_delete_nonexistent(self, auth_db_ready):
        assert auth_db_ready.delete_user(99999) is False

    def test_list_users(self, auth_db_ready):
        auth_db_ready.create_user("u1", "p", "admin")
        auth_db_ready.create_user("u2", "p", "user")
        users = auth_db_ready.list_users()
        usernames = [u["username"] for u in users]
        assert "u1" in usernames
        assert "u2" in usernames
        for u in users:
            assert "password" not in u
            assert "salt" not in u


class TestPermissions:

    def test_admin_permissions(self, auth_db_ready):
        p = auth_db_ready.get_permissions("admin")
        assert p["can_manage_users"] is True
        assert p["can_write_cases"] is True
        assert p["can_delete_cases"] is True
        assert p["can_delete_users"] is True

    def test_spectator_permissions(self, auth_db_ready):
        p = auth_db_ready.get_permissions("spectator")
        assert p["can_manage_users"] is False
        assert p["can_write_cases"] is False
        assert p["can_delete_cases"] is False
        assert p["can_read_cases"] is True

    def test_unknown_role_defaults_to_spectator(self, auth_db_ready):
        p = auth_db_ready.get_permissions("unknown_role")
        assert p == auth_db_ready.PERMISSIONS["spectator"]

    def test_user_permissions(self, auth_db_ready):
        p = auth_db_ready.get_permissions("user")
        assert p["can_write_cases"] is True
        assert p["can_delete_cases"] is False
        assert p["can_manage_users"] is False

    def test_admin_centre_permissions(self, auth_db_ready):
        p = auth_db_ready.get_permissions("admin_centre")
        assert p["can_manage_users"] is True
        assert p["can_delete_users"] is False
        assert p["can_delete_cases"] is True


class TestTotp:

    def test_generate_secret(self, auth_db_ready):
        secret = auth_db_ready.totp_generate_secret()
        assert isinstance(secret, str)
        assert len(secret) >= 16

    def test_provisioning_uri(self, auth_db_ready):
        secret = auth_db_ready.totp_generate_secret()
        uri = auth_db_ready.totp_get_provisioning_uri(secret, "testuser")
        assert uri.startswith("otpauth://totp/")
        assert "FoetoPath" in uri
        assert "testuser" in uri

    def test_totp_verify_valid_code(self, auth_db_ready):
        import pyotp
        secret = auth_db_ready.totp_generate_secret()
        code = pyotp.TOTP(secret).now()
        assert auth_db_ready.totp_verify(secret, code) is True

    def test_totp_verify_invalid_code(self, auth_db_ready):
        secret = auth_db_ready.totp_generate_secret()
        assert auth_db_ready.totp_verify(secret, "000000") is False

    def test_totp_verify_empty_inputs(self, auth_db_ready):
        assert auth_db_ready.totp_verify("", "123456") is False
        assert auth_db_ready.totp_verify("secret", "") is False

    def test_totp_enroll(self, auth_db_ready):
        uid = auth_db_ready.create_user("totp_user", "pass", "user")
        secret = auth_db_ready.totp_generate_secret()
        backup_codes = auth_db_ready.totp_enroll(uid, secret)
        assert len(backup_codes) == auth_db_ready.TOTP_BACKUP_COUNT
        assert auth_db_ready.totp_is_enabled(uid) is True

    def test_totp_not_enabled_by_default(self, auth_db_ready):
        uid = auth_db_ready.create_user("no_totp", "pass", "user")
        assert auth_db_ready.totp_is_enabled(uid) is False

    def test_totp_get_secret(self, auth_db_ready):
        uid = auth_db_ready.create_user("sec_user", "pass", "user")
        secret = auth_db_ready.totp_generate_secret()
        auth_db_ready.totp_enroll(uid, secret)
        assert auth_db_ready.totp_get_secret(uid) == secret

    def test_totp_backup_code_verify_and_consume(self, auth_db_ready):
        uid = auth_db_ready.create_user("backup_user", "pass", "user")
        secret = auth_db_ready.totp_generate_secret()
        backup_codes = auth_db_ready.totp_enroll(uid, secret)

        first_code = backup_codes[0]
        assert auth_db_ready.totp_verify_backup_code(uid, first_code) is True
        assert auth_db_ready.totp_verify_backup_code(uid, first_code) is False

    def test_totp_reset(self, auth_db_ready):
        uid = auth_db_ready.create_user("reset_user", "pass", "user")
        secret = auth_db_ready.totp_generate_secret()
        auth_db_ready.totp_enroll(uid, secret)
        assert auth_db_ready.totp_is_enabled(uid) is True
        auth_db_ready.totp_reset(uid)
        assert auth_db_ready.totp_is_enabled(uid) is False
