"""Tests d'intégration pour auth_bp — login, logout, TOTP, API users."""

import json
import time

import pytest


class TestLoginLogout:

    def test_login_page_accessible(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_json_success(self, client, tmp_data_dir):
        import auth_db
        import db as foetopath_db
        foetopath_db.set_setting("totp_required", "0")
        auth_db.create_user("alice", "pass123", "user")
        resp = client.post("/auth/login", json={
            "username": "alice",
            "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_login_json_wrong_password(self, client, tmp_data_dir):
        import auth_db
        auth_db.create_user("bob", "correct", "user")
        resp = client.post("/auth/login", json={
            "username": "bob",
            "password": "wrong",
        })
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={
            "username": "ghost",
            "password": "anything",
        })
        assert resp.status_code == 401

    def test_login_form_success(self, client, tmp_data_dir):
        import auth_db
        import db as foetopath_db
        foetopath_db.set_setting("totp_required", "0")
        auth_db.create_user("charlie", "pass", "user")
        resp = client.post("/auth/login", data={
            "username": "charlie",
            "password": "pass",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_logout_clears_session(self, admin_client):
        resp = admin_client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code == 302
        with admin_client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_login_sets_session_fields(self, client, tmp_data_dir):
        import auth_db
        import db as foetopath_db
        foetopath_db.set_setting("totp_required", "0")
        auth_db.create_user("dave", "pass", "admin")
        client.post("/auth/login", json={
            "username": "dave",
            "password": "pass",
        })
        with client.session_transaction() as sess:
            assert sess["username"] == "dave"
            assert sess["user_role"] == "admin"
            assert "login_time" in sess


class TestRateLimiting:

    def test_rate_limit_after_failures(self, client, tmp_data_dir):
        import auth_db
        auth_db.create_user("target", "real_pass", "user")
        for _ in range(3):
            client.post("/auth/login", json={
                "username": "target",
                "password": "wrong",
            })
        resp = client.post("/auth/login", json={
            "username": "target",
            "password": "wrong",
        })
        assert resp.status_code == 429
        data = resp.get_json()
        assert "retry_after" in data

    def test_rate_limit_resets_on_success(self, client, tmp_data_dir):
        import auth_db
        import db as foetopath_db
        foetopath_db.set_setting("totp_required", "0")
        auth_db.create_user("resetme", "pass", "user")
        for _ in range(3):
            client.post("/auth/login", json={
                "username": "resetme", "password": "wrong",
            })
        time.sleep(5.1)
        resp = client.post("/auth/login", json={
            "username": "resetme", "password": "pass",
        })
        assert resp.status_code == 200


class TestApiMe:

    def test_me_authenticated(self, admin_client):
        resp = admin_client.get("/auth/api/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"
        assert "permissions" in data

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/api/me")
        assert resp.status_code == 401


class TestApiUsers:

    def test_list_users_as_admin(self, admin_client):
        resp = admin_client.get("/auth/api/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "users" in data
        assert len(data["users"]) >= 1

    def test_list_users_as_user_forbidden(self, user_client):
        resp = user_client.get("/auth/api/users")
        assert resp.status_code in (401, 403)

    def test_create_user(self, admin_client):
        resp = admin_client.post("/auth/api/users", json={
            "username": "newbie",
            "password": "securepass",
            "role": "user",
            "display_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert "id" in data

    def test_create_user_duplicate(self, admin_client):
        admin_client.post("/auth/api/users", json={
            "username": "dup_user", "password": "pass", "role": "user",
        })
        resp = admin_client.post("/auth/api/users", json={
            "username": "dup_user", "password": "pass2", "role": "user",
        })
        assert resp.status_code == 409

    def test_create_user_missing_fields(self, admin_client):
        resp = admin_client.post("/auth/api/users", json={
            "username": "", "password": "", "role": "user",
        })
        assert resp.status_code == 400

    def test_create_user_invalid_role(self, admin_client):
        resp = admin_client.post("/auth/api/users", json={
            "username": "bad_role", "password": "pass", "role": "superadmin",
        })
        assert resp.status_code == 400

    def test_update_user(self, admin_client):
        resp = admin_client.post("/auth/api/users", json={
            "username": "upd_target", "password": "pass", "role": "user",
        })
        uid = resp.get_json()["id"]
        resp = admin_client.put(f"/auth/api/users/{uid}", json={
            "display_name": "Updated Name",
        })
        assert resp.status_code == 200

    def test_update_nonexistent_user(self, admin_client):
        resp = admin_client.put("/auth/api/users/99999", json={
            "display_name": "Ghost",
        })
        assert resp.status_code == 404

    def test_delete_user(self, admin_client):
        resp = admin_client.post("/auth/api/users", json={
            "username": "del_target", "password": "pass", "role": "user",
        })
        uid = resp.get_json()["id"]
        resp = admin_client.delete(f"/auth/api/users/{uid}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_delete_user_as_non_admin(self, user_client):
        resp = user_client.delete("/auth/api/users/1")
        assert resp.status_code in (401, 403)

    def test_delete_nonexistent_user(self, admin_client):
        resp = admin_client.delete("/auth/api/users/99999")
        assert resp.status_code == 404


class TestTotpReset:

    def test_totp_reset_as_admin(self, admin_client, tmp_data_dir):
        import auth_db
        uid = auth_db.create_user("totp_target", "pass", "user")
        secret = auth_db.totp_generate_secret()
        auth_db.totp_enroll(uid, secret)
        assert auth_db.totp_is_enabled(uid)
        resp = admin_client.post(f"/auth/api/users/{uid}/totp-reset")
        assert resp.status_code == 200
        assert not auth_db.totp_is_enabled(uid)

    def test_totp_reset_nonexistent_user(self, admin_client):
        resp = admin_client.post("/auth/api/users/99999/totp-reset")
        assert resp.status_code == 404
