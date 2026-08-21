#!/usr/bin/env python3
"""
FoetoPath Server — Hub Admin + Appairage

Flask server combining:
  - Case administration & SQLite database
  - Phone sync (ADB) with auto-import
  - Slide/macro photo pairing table

Slide viewer is served by Luminarium (see viewer_port in settings).

Usage:
    python app.py                                    # Start on port 5000
    python app.py --port 8080                        # Custom port
    python app.py --data-dir /path/to/foetopath/data # DB & foetus data dir
"""

import argparse
import logging
import os
import secrets
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, send_from_directory, url_for
from divers_bp import divers_bp


log = logging.getLogger(__name__)

# ── Setup structured logging ───────────────────────────────────────────────
from utils.logging_config import setup_logging
setup_logging()

# ── Admin & BDD ────────────────────────────────────────────────────────────
import db as foetopath_db
from admin_bp import admin_bp

# ── Placenta ──────────────────────────────────────────────────────────────
import placenta_db
from placenta_bp import placenta_bp

# ── Pédiatrique ──────────────────────────────────────────────────────────
import pediatrique_db
from pediatrique_bp import pediatrique_bp

# ── Authentification ─────────────────────────────────────────────────────
import auth_db
from auth_bp import auth_bp, login_required, check_session_2fa

# ── Audit ────────────────────────────────────────────────────────────────
import audit

# ── Feedback / suggestions ──────────────────────────────────────────────
from feedback_bp import feedback_bp

# ── Config persistante (chemin des BDD, hors base) ──────────────────────
import persistent_config
from config import (
    DEFAULT_IDLE_TIMEOUT_MIN, MIN_IDLE_TIMEOUT_MIN, MAX_IDLE_TIMEOUT_MIN,
)

# ── Internationalisation ────────────────────────────────────────────────
import i18n

app = Flask(__name__)
app.json.sort_keys = False  # Préserver l'ordre des OrderedDict dans les réponses JSON

# Désactiver le cache des fichiers statiques pour éviter les problèmes de JS obsolète
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 Mo


# ── Secret Flask sécurisé ────────────────────────────────────────────────
# Priorité : 1) variable d'environnement  2) config persistante  3) génération auto
if os.environ.get("FOETOPATH_SECRET"):
    app.secret_key = os.environ["FOETOPATH_SECRET"]
else:
    _persisted_secret = persistent_config.get("flask_secret")
    if _persisted_secret:
        app.secret_key = _persisted_secret
    else:
        _generated_secret = secrets.token_hex(32)
        persistent_config.set_key("flask_secret", _generated_secret)
        app.secret_key = _generated_secret
        log.warning(
            "FOETOPATH_SECRET non défini — secret généré automatiquement et "
            "sauvegardé dans la config persistante. Définissez la variable "
            "d'environnement FOETOPATH_SECRET pour un contrôle explicite."
        )

# ── Cookies de session sécurisés ─────────────────────────────────────────
# SESSION_COOKIE_SECURE=True exige HTTPS ; désactivé en local (sans tunnel)
_force_https = bool(os.environ.get("FOETOPATH_CORS_ORIGINS"))  # Tunnel actif → HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = _force_https
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"    # Chantier 5 : protection CSRF
app.config["PERMANENT_SESSION_LIFETIME"] = DEFAULT_IDLE_TIMEOUT_MIN * 60

# ── Headers de sécurité HTTP (Chantier 5 — Flask-Talisman) ──────────────
from flask_talisman import Talisman

# CSP adaptée à la PWA : inline scripts/styles nécessaires, CDN pour OpenSeadragon
_CSP = {
    "default-src": "'self'",
    "script-src": "'self' 'unsafe-inline' https://cdnjs.cloudflare.com",
    "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src": "'self' https://fonts.gstatic.com",
    "img-src": "'self' data: blob: https://cdnjs.cloudflare.com",
    "connect-src": "'self'",
    "worker-src": "'self'",
    "manifest-src": "'self'",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}

# Domaines autorisés pour CORS (Cloudflare Tunnel)
_ALLOWED_ORIGINS = os.environ.get(
    "FOETOPATH_CORS_ORIGINS", ""
).split(",") if os.environ.get("FOETOPATH_CORS_ORIGINS") else []

Talisman(
    app,
    force_https=False,                  # Géré par Cloudflare Tunnel en amont
    strict_transport_security=True,     # HSTS
    strict_transport_security_max_age=31536000,  # 1 an
    strict_transport_security_include_subdomains=True,
    content_security_policy=_CSP,
    content_security_policy_nonce_in=None,  # Pas de nonce (inline omniprésent)
    referrer_policy="no-referrer",
    permissions_policy={
        "camera": "()",
        "microphone": "()",
        "geolocation": "()",
    },
    session_cookie_secure=_force_https,
    session_cookie_http_only=True,
    session_cookie_samesite="Lax",
)

# Rafraîchir la session à chaque requête + adapter le timeout dynamique + 2FA
from flask import session as flask_session
from datetime import timedelta
@app.before_request
def _refresh_session():
    flask_session.modified = True
    # Adapter le lifetime au paramètre idle_timeout_min (1-30, défaut 8)
    try:
        settings = foetopath_db.get_all_settings()
        mins = int(settings.get('idle_timeout_min', DEFAULT_IDLE_TIMEOUT_MIN))
        mins = max(MIN_IDLE_TIMEOUT_MIN, min(MAX_IDLE_TIMEOUT_MIN, mins))
        app.permanent_session_lifetime = timedelta(minutes=mins)
    except Exception:
        log.debug("Failed to update session lifetime from settings", exc_info=True)

    # ── Vérification session 2FA (idle 2h / absolue 8h) ──
    # Ne pas vérifier sur les routes d'auth elles-mêmes ni les statiques
    if not request.path.startswith(("/auth/", "/static/")):
        resp = check_session_2fa()
        if resp is not None:
            return resp

# ── Enregistrer les blueprints ────────────────────────────────────────────
app.register_blueprint(auth_bp)           # /auth
app.register_blueprint(admin_bp)          # /admin
app.register_blueprint(placenta_bp)       # /placenta
app.register_blueprint(pediatrique_bp)    # /pediatrique
app.register_blueprint(divers_bp)         # /divers
app.register_blueprint(feedback_bp)       # /api/feedback

from viewer_proxy_bp import viewer_proxy_bp
app.register_blueprint(viewer_proxy_bp)   # /viewer

# ── i18n : injecter t() dans tous les templates Jinja2 ──────────────────
i18n.init_app(app)


# ── Audit after_request : tracer les mutations (POST/PUT/DELETE) ─────────
@app.after_request
def _audit_mutations(response):
    """Loguer automatiquement les requêtes de mutation sur les routes API."""
    try:
        if request.method in ("POST", "PUT", "DELETE") and "user_id" in session:
            path = request.path
            # Ignorer les routes non-API et les routes d'auth (déjà auditées manuellement)
            if "/api/" in path and not path.startswith("/auth/"):
                action_map = {"POST": "create", "PUT": "update", "DELETE": "delete"}
                action = action_map.get(request.method, request.method.lower())

                # Déduire resource_type depuis le chemin
                resource_type = None
                if "/admin/api/" in path:
                    resource_type = "foetus"
                elif "/placenta/api/" in path:
                    resource_type = "placenta"

                audit.log_audit(
                    action=f"api_{action}",
                    resource_type=resource_type,
                    details={"path": path, "method": request.method,
                             "status": response.status_code},
                )
    except Exception:
        log.debug("Audit after_request failed", exc_info=True)
    return response

# ── Injection widget feedback (ampoule) dans les pages HTML ──────────────
_WIDGET_SCRIPT = '<script src="/static/widget-feedback.js"></script>'

@app.after_request
def _inject_feedback_widget(response):
    if (response.content_type and "text/html" in response.content_type
            and not response.direct_passthrough
            and "user_id" in session):
        data = response.get_data(as_text=True)
        if "</body>" in data:
            data = data.replace("</body>", _WIDGET_SCRIPT + "\n</body>")
            response.set_data(data)
    return response


# ── Configuration (centralisée dans config.py) ────────────────────────────


# ── Routes PWA (servies à la racine pour accès direct) ────────────────────

def _check_pwa_access():
    """Refuse l'accès aux PWA pour les spectateurs (lecture seule).
    Pose un cookie pwa_username pour identifier l'utilisateur dans les soumissions PWA."""
    role = session.get("user_role", "")
    if role == "spectator":
        return redirect(url_for("hub"))
    # Mémoriser le username dans un cookie accessible JS (survit à la session Flask)
    username = session.get("username", "")
    if username:
        from flask import g
        g._pwa_username = username  # sera posé sur la réponse via after_request
    return None


@app.after_request
def _set_pwa_username_cookie(response):
    """Pose le cookie pwa_username sur les réponses PWA si l'utilisateur est identifié."""
    from flask import g
    username = getattr(g, "_pwa_username", None)
    if username and request.path.startswith("/pwa/"):
        response.set_cookie(
            "pwa_username",
            username,
            max_age=90 * 24 * 3600,  # 90 jours
            httponly=False,           # accessible en JS
            samesite="Lax",
            secure=request.is_secure,
        )
    return response


PWA_PLACENTAS_DIR = Path(__file__).parent / "pwa" / "placentas"


@app.route("/pwa/placentas/")
def pwa_placentas_index():
    """Sert la page d'accueil de la PWA Placenta."""
    block = _check_pwa_access()
    if block:
        return block
    return send_from_directory(str(PWA_PLACENTAS_DIR), "index.html")


@app.route("/pwa/placentas/<path:filename>")
def pwa_placentas_static(filename):
    """Sert les fichiers statiques de la PWA Placenta."""
    block = _check_pwa_access()
    if block:
        return block
    resp = send_from_directory(str(PWA_PLACENTAS_DIR), filename)
    if filename == "sw.js":
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ── PWA Fœtus ─────────────────────────────────────────────────────────────

PWA_FOET_DIR = Path(__file__).parent / "pwa" / "foet"


@app.route("/pwa/foet/")
def pwa_foet_index():
    """Sert la page d'accueil de la PWA Fœtus."""
    block = _check_pwa_access()
    if block:
        return block
    return send_from_directory(str(PWA_FOET_DIR), "index.html")


@app.route("/pwa/foet/<path:filename>")
def pwa_foet_static(filename):
    """Sert les fichiers statiques de la PWA Fœtus."""
    block = _check_pwa_access()
    if block:
        return block
    resp = send_from_directory(str(PWA_FOET_DIR), filename)
    if filename == "sw.js":
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ── PWA Néonat ────────────────────────────────────────────────────────────

PWA_NEONAT_DIR = Path(__file__).parent / "pwa" / "neonat"


@app.route("/pwa/neonat/")
def pwa_neonat_index():
    block = _check_pwa_access()
    if block:
        return block
    return send_from_directory(str(PWA_NEONAT_DIR), "index.html")


@app.route("/pwa/neonat/<path:filename>")
def pwa_neonat_static(filename):
    block = _check_pwa_access()
    if block:
        return block
    resp = send_from_directory(str(PWA_NEONAT_DIR), filename)
    if filename == "sw.js":
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def hub():
    """Page hub — point d'entrée principal avec navigation."""
    return render_template("hub.html")


# ── Endpoint pour le formulaire pré-examen ─────────────────────────────────

@app.route("/api/dossiers/pre-examen", methods=["POST"])
@login_required
def receive_pre_exam():
    """
    Endpoint appelé par le formulaire pré-examen (sendToServer).
    Importe les données directement dans la BDD SQLite.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Données requises"}), 400

    admin_data = data.get("case_admin", data)
    numero = admin_data.get("numero_dossier")
    if not numero:
        return jsonify({"error": "Numéro de dossier requis"}), 400

    # Tracking utilisateur (session si connecté, sinon champ 'user' du payload)
    submit_user = session.get("username", "") or data.get("user", "pwa")
    admin_data["modified_by"] = submit_user

    existing = foetopath_db.get_case_by_numero(numero)
    if existing:
        case_id = existing["id"]
        foetopath_db.update_case(case_id, admin_data)
    else:
        admin_data.setdefault("created_by", submit_user)
        case_id = foetopath_db.create_case(admin_data)

    # Sauvegarder les sous-tables comme données de modules
    for key in ["atcd_maternels", "grossesse_en_cours", "examens_prenataux", "atcd_obstetricaux"]:
        if key in data:
            foetopath_db.save_module_data(case_id, key, data[key])

    return jsonify({"id": case_id, "message": "Dossier enregistré"})


# ── FOETO DB version check ────────────────────────────────────────────────

from config import FOETO_DB_PATH as FOETO_DB
FOETO_VERSION_URL = "https://data.pazuzu.uk/api/foeto/version"


def _check_foeto_db_version():
    """Compare local foeto_meta version vs remote. Warn if outdated."""
    import sqlite3
    local_version = None
    if os.path.exists(FOETO_DB):
        try:
            conn = sqlite3.connect(FOETO_DB)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT value FROM foeto_meta WHERE key='version'").fetchone()
            if row:
                local_version = row["value"]
            conn.close()
        except Exception:
            pass
    if not local_version:
        print(f"  ⚠ FOETO DB introuvable ou sans version ({FOETO_DB})")
        return
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(FOETO_VERSION_URL, timeout=5) as resp:
            remote = _json.loads(resp.read())
        remote_version = remote.get("version", "")
        if remote_version and remote_version != local_version:
            dl = remote.get("download_url", FOETO_VERSION_URL)
            print(f"  ⚠ FOETO DB obsolète : locale={local_version}, distante={remote_version}")
            print(f"    → Télécharger : {dl}")
        else:
            print(f"  FOETO DB v{local_version} ✓")
    except Exception:
        print(f"  FOETO DB v{local_version} (check distant indisponible)")


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FoetoPath Server (Hub Admin)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--data-dir", default="", help="Directory for FoetoPath data (DB, foetus folders)")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    # ── Déterminer le répertoire de données (config persistante > CLI > défaut) ──
    data_dir = persistent_config.get_db_directory(cli_arg=args.data_dir)
    app.config["DATA_DIR"] = data_dir
    db_path = foetopath_db.init_db(data_dir)
    plac_db_path = placenta_db.init_db(data_dir)
    ped_db_path = pediatrique_db.init_db(data_dir)
    auth_db_path = auth_db.init_db(data_dir)
    audit_db_path = audit.init_db(data_dir)

    _check_foeto_db_version()

    print(f"\n{'='*60}")
    print(f"  FoetoPath Server")
    print(f"  Hub         : http://{args.host}:{args.port}/")
    print(f"  Admin Fœtus : http://{args.host}:{args.port}/admin")
    print(f"  Admin Plac. : http://{args.host}:{args.port}/admin/placenta")
    print(f"  PWA Fœtus   : http://{args.host}:{args.port}/pwa/foet/")
    print(f"  PWA Placenta: http://{args.host}:{args.port}/pwa/placentas/")
    print(f"  DB Fœtus    : {db_path}")
    print(f"  DB Placenta : {plac_db_path}")
    print(f"  DB Pédiatr. : {ped_db_path}")
    print(f"  DB Auth     : {auth_db_path}")
    print(f"  DB Audit    : {audit_db_path}")
    viewer_port = foetopath_db.get_setting("viewer_port", "5080")
    print(f"  Viewer      : http://10.0.0.1:{viewer_port}/ (Luminarium)")
    print(f"  Login       : http://{args.host}:{args.port}/auth/login")
    print(f"{'='*60}\n")

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
