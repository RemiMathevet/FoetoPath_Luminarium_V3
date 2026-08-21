"""
Fixtures partagées pour les tests FoetoPath.

Fournit des bases de données temporaires isolées pour chaque test,
un client Flask, et des helpers d'authentification.
"""

import json
import os
import sys
import tempfile

import pytest

# Le code source est au niveau parent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def tmp_data_dir(tmp_path):
    """Répertoire temporaire pour les bases de données d'un test."""
    return str(tmp_path)


# ── Auth DB ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def auth_db_ready(tmp_data_dir):
    """Initialise auth.db dans un répertoire temporaire."""
    import auth_db
    auth_db.init_db(tmp_data_dir)
    yield auth_db
    auth_db._db_path = None


# ── Foetus DB ───────────────────────────────────────────────────────────────

@pytest.fixture()
def foetus_db_ready(tmp_data_dir):
    """Initialise foetopath.db dans un répertoire temporaire."""
    import db
    db.init_db(tmp_data_dir)
    yield db
    db._mgr._db_path = None


# ── Placenta DB ─────────────────────────────────────────────────────────────

@pytest.fixture()
def placenta_db_ready(tmp_data_dir):
    """Initialise placenta.db dans un répertoire temporaire."""
    import placenta_db
    placenta_db.init_db(tmp_data_dir)
    yield placenta_db
    placenta_db._mgr._db_path = None


# ── Divers DB ───────────────────────────────────────────────────────────────

@pytest.fixture()
def divers_db_ready(tmp_data_dir):
    """Initialise la table cas_divers dans un répertoire temporaire."""
    import db
    import divers_db
    db.init_db(tmp_data_dir)
    divers_db.init_table()
    yield divers_db
    db._mgr._db_path = None


# ── Audit DB ────────────────────────────────────────────────────────────────

@pytest.fixture()
def audit_db_ready(tmp_data_dir):
    """Initialise audit.db dans un répertoire temporaire."""
    import audit
    audit.init_db(tmp_data_dir)
    yield audit
    audit._db_path = None


# ── Flask App ───────────────────────────────────────────────────────────────

@pytest.fixture()
def flask_app(tmp_data_dir):
    """Mini-app Flask de test avec blueprints et BDD isolées.
    N'importe PAS app.py (qui dépend d'OpenSlide) — enregistre
    les blueprints directement pour des tests d'intégration légers."""
    from flask import Flask

    import auth_db
    import db as foetopath_db
    import placenta_db
    import audit as audit_mod

    auth_db.init_db(tmp_data_dir)
    foetopath_db.init_db(tmp_data_dir)
    placenta_db.init_db(tmp_data_dir)
    audit_mod.init_db(tmp_data_dir)

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
    )
    app.secret_key = "test-secret-key-for-testing"
    app.config["TESTING"] = True
    app.config["DATA_DIR"] = tmp_data_dir

    foetopath_db.set_setting("totp_required", "0")

    import i18n
    i18n.init_app(app)

    from auth_bp import auth_bp
    from admin_bp import admin_bp
    from placenta_bp import placenta_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(placenta_bp)

    @app.route("/")
    def hub():
        return "hub"

    yield app

    auth_db._db_path = None
    foetopath_db._mgr._db_path = None
    placenta_db._mgr._db_path = None
    audit_mod._db_path = None


@pytest.fixture()
def client(flask_app):
    """Client de test Flask."""
    return flask_app.test_client()


def _make_session(client, auth_db_mod, username, password, role,
                  totp_verified=True):
    """Helper : crée un user et injecte sa session dans le client."""
    uid = auth_db_mod.create_user(
        username=username, password=password, role=role,
        display_name=username.title(), created_by="test",
    )
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["username"] = username
        sess["user_role"] = role
        sess["display_name"] = username.title()
        sess["totp_verified"] = totp_verified
        sess["totp_required"] = False
        sess["totp_setup_done"] = True
        sess["login_time"] = __import__("time").time()
        sess["last_activity"] = __import__("time").time()
    return uid


@pytest.fixture()
def admin_client(client, tmp_data_dir):
    """Client authentifié en tant qu'admin."""
    import auth_db
    _make_session(client, auth_db, "testadmin", "Pass123!", "admin")
    return client


@pytest.fixture()
def user_client(client, tmp_data_dir):
    """Client authentifié en tant qu'user (pas de delete)."""
    import auth_db
    _make_session(client, auth_db, "testuser", "Pass123!", "user")
    return client


@pytest.fixture()
def spectator_client(client, tmp_data_dir):
    """Client authentifié en tant que spectator (lecture seule)."""
    import auth_db
    _make_session(client, auth_db, "testspectator", "Pass123!", "spectator")
    return client


# ── Helpers ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_foetus_case():
    """Données minimales pour créer un cas foetus."""
    return {
        "numero_dossier": "24P0001",
        "sexe": "M",
        "terme_issue": "34",
        "nom_mere": "DUPONT",
        "indication_examen": "IMG pour malformation",
    }


@pytest.fixture()
def sample_placenta_case():
    """Données minimales pour créer un cas placenta."""
    return {
        "numero_dossier": "24PL001",
        "terme_sa": 38,
        "terme_jours": 2,
        "sexe": "F",
        "masse_paree_g": 450,
    }


@pytest.fixture()
def sample_divers_case():
    """Données minimales pour créer un cas divers."""
    return {
        "type_cas": "curetage",
        "dossier": "24D001",
        "ag_sa": 12,
        "indication": "FCS",
        "form_data": {"fragments_g": 15, "aspect": "complet"},
    }
