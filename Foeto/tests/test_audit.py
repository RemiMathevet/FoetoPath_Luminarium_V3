"""Tests pour audit.py — logging append-only."""

import pytest
from flask import Flask


class TestAuditLog:

    def test_log_and_retrieve(self, audit_db_ready):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/", method="POST"):
            audit_db_ready.log_audit(
                action="test_action",
                resource_type="test",
                resource_id="42",
                details={"key": "value"},
                user_id=1,
                username="tester",
            )
        logs = audit_db_ready.get_recent_logs(limit=10)
        assert len(logs) >= 1
        entry = logs[0]
        assert entry["action"] == "test_action"
        assert entry["resource_type"] == "test"
        assert entry["resource_id"] == "42"
        assert entry["user_id"] == 1
        assert entry["username"] == "tester"

    def test_log_without_flask_context(self, audit_db_ready):
        audit_db_ready.log_audit(
            action="cli_action",
            user_id=0,
            username="system",
        )
        logs = audit_db_ready.get_recent_logs(limit=1)
        assert len(logs) == 1
        assert logs[0]["action"] == "cli_action"
        assert logs[0]["ip_address"] is None

    def test_log_with_session_context(self, audit_db_ready):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/api/cases", method="POST",
                                       headers={"User-Agent": "TestBot/1.0"}):
            from flask import session
            session["user_id"] = 5
            session["username"] = "dr_martin"
            audit_db_ready.log_audit(action="create_case", resource_type="case")

        logs = audit_db_ready.get_recent_logs(limit=1)
        assert logs[0]["user_id"] == 5
        assert logs[0]["username"] == "dr_martin"

    def test_filter_by_action(self, audit_db_ready):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/"):
            audit_db_ready.log_audit(action="login", user_id=1, username="a")
            audit_db_ready.log_audit(action="edit_case", user_id=1, username="a")
            audit_db_ready.log_audit(action="login", user_id=2, username="b")

        logins = audit_db_ready.get_recent_logs(action="login")
        assert all(l["action"] == "login" for l in logins)
        assert len(logins) == 2

    def test_log_never_raises(self, audit_db_ready):
        import audit
        old_path = audit._db_path
        audit._db_path = "/nonexistent/path/audit.db"
        audit.log_audit(action="should_not_crash", user_id=0, username="test")
        audit._db_path = old_path

    def test_details_json_stored(self, audit_db_ready):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/"):
            audit_db_ready.log_audit(
                action="export",
                details={"format": "pdf", "pages": 12},
                user_id=1,
                username="u",
            )
        logs = audit_db_ready.get_recent_logs(limit=1)
        import json
        details = json.loads(logs[0]["details"])
        assert details["format"] == "pdf"
        assert details["pages"] == 12

    def test_limit_respected(self, audit_db_ready):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/"):
            for i in range(20):
                audit_db_ready.log_audit(action=f"action_{i}", user_id=1, username="u")
        logs = audit_db_ready.get_recent_logs(limit=5)
        assert len(logs) == 5

    def test_ordering_most_recent_first(self, audit_db_ready):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/"):
            audit_db_ready.log_audit(action="first", user_id=1, username="u")
            audit_db_ready.log_audit(action="second", user_id=1, username="u")
        logs = audit_db_ready.get_recent_logs(limit=2)
        assert logs[0]["action"] == "second"
        assert logs[1]["action"] == "first"
