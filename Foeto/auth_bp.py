#!/usr/bin/env python3
"""
FoetoPath — Blueprint Authentification & Gestion Utilisateurs.

Routes :
  GET  /auth/login              Page de connexion
  POST /auth/login              Soumettre identifiants
  GET  /auth/totp               Page de saisie code TOTP
  POST /auth/totp               Valider code TOTP
  GET  /auth/totp/setup         Page d'enrollment TOTP (QR code)
  POST /auth/totp/setup         Confirmer enrollment TOTP
  GET  /auth/logout             Déconnexion
  GET  /auth/api/me             Info utilisateur connecté
  GET  /auth/api/users          Liste des utilisateurs (admin/admin_centre)
  POST /auth/api/users          Créer un utilisateur
  PUT  /auth/api/users/<id>     Modifier un utilisateur
  DELETE /auth/api/users/<id>   Supprimer un utilisateur
  POST /auth/api/users/<id>/totp-reset  Reset TOTP (admin)
"""

import io
import math
import time
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Blueprint,
    Response,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import auth_db
from config import (
    DEFAULT_TOTP_COOKIE_HOURS, MIN_TOTP_COOKIE_HOURS, MAX_TOTP_COOKIE_HOURS,
    MAX_ABSOLUTE_SESSION_HOURS,
)
from i18n import t
import audit
import db as settings_db
from rate_limiter import login_limiter

auth_bp = Blueprint("auth", __name__, template_folder="templates")


# ══════════════════════════════════════════════════════════════════════════
#  Constantes session & 2FA
# ══════════════════════════════════════════════════════════════════════════

TOTP_COOKIE_MAX_AGE_DEFAULT = DEFAULT_TOTP_COOKIE_HOURS * 3600
TOTP_COOKIE_NAME = "foetopath_2fa"
SESSION_ABSOLUTE_MAX_SECONDS = MAX_ABSOLUTE_SESSION_HOURS * 3600


def _get_totp_cookie_max_age() -> int:
    """Lit la durée du cookie 2FA depuis les settings (en secondes).
    Configurable de 1h à 12h, défaut 4h."""
    try:
        hours = int(settings_db.get_setting("totp_cookie_hours", str(DEFAULT_TOTP_COOKIE_HOURS)))
        hours = max(MIN_TOTP_COOKIE_HOURS, min(MAX_TOTP_COOKIE_HOURS, hours))
        return hours * 3600
    except Exception:
        return TOTP_COOKIE_MAX_AGE_DEFAULT


def _is_totp_globally_required() -> bool:
    """Vérifie si la 2FA est globalement activée dans les paramètres."""
    return settings_db.get_setting("totp_required", "1") != "0"


# ── Cookie 2FA signé (survit aux expirations de session Flask) ──────────

def _get_2fa_serializer():
    """Retourne un serializer signé pour le cookie 2FA."""
    from flask import current_app
    return URLSafeTimedSerializer(current_app.secret_key, salt="foetopath-2fa")


def _set_2fa_cookie(response, user_id: int):
    """Pose un cookie signé attestant que le 2FA a été validé.
    Durée configurable via le setting totp_cookie_hours (1-12h, défaut 4h)."""
    max_age = _get_totp_cookie_max_age()
    s = _get_2fa_serializer()
    token = s.dumps({"uid": user_id, "t": int(time.time())})
    response.set_cookie(
        TOTP_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
    )
    return response


def _check_2fa_cookie(user_id: int) -> bool:
    """Vérifie si le cookie 2FA est valide pour cet utilisateur.
    Utilise la durée configurée via totp_cookie_hours."""
    token = request.cookies.get(TOTP_COOKIE_NAME)
    if not token:
        return False
    try:
        max_age = _get_totp_cookie_max_age()
        s = _get_2fa_serializer()
        data = s.loads(token, max_age=max_age)
        return data.get("uid") == user_id
    except (BadSignature, SignatureExpired):
        return False


def _clear_2fa_cookie(response):
    """Supprime le cookie 2FA."""
    response.delete_cookie(TOTP_COOKIE_NAME)
    return response


# ══════════════════════════════════════════════════════════════════════════
#  Décorateurs d'accès — importables depuis les autres blueprints
# ══════════════════════════════════════════════════════════════════════════

def _is_api_request() -> bool:
    """Détecte si la requête courante est une requête API."""
    return request.path.startswith(("/admin/api/", "/placenta/api/",
                                    "/divers/api/", "/auth/api/", "/api/"))


def make_before_request(
    *,
    api_prefix: str,
    exempt_paths: set[str] | None = None,
    exempt_prefixes: tuple[str, ...] = (),
    exempt_delete_paths: set[str] | None = None,
    check_mutations: bool = True,
    spectator_blocked_pages: set[str] | None = None,
    redirect_on_unauth: bool = True,
):
    """Génère un before_request pour un blueprint avec auth + permissions.

    Parameters:
        api_prefix: préfixe des routes API (ex: "/admin/api/")
        exempt_paths: chemins exacts exemptés d'auth
        exempt_prefixes: préfixes exemptés d'auth
        exempt_delete_paths: préfixes de routes DELETE exemptées du check can_delete_cases
        check_mutations: vérifier can_write/can_delete sur POST/PUT/DELETE
        spectator_blocked_pages: pages interdites aux spectateurs (redirect hub)
        redirect_on_unauth: True = redirect login, False = return None
    """
    _exempt = exempt_paths or set()
    _blocked = spectator_blocked_pages or set()
    _exempt_del = exempt_delete_paths or set()

    def _before_request():
        if request.path in _exempt:
            return None
        for pfx in exempt_prefixes:
            if request.path.startswith(pfx):
                return None

        if "user_id" not in session:
            if request.path.startswith(api_prefix):
                return jsonify({"error": t('errors.unauthorized')}), 401
            if redirect_on_unauth:
                return redirect(url_for("auth.login_page", next=request.path))
            return None

        role = session.get("user_role", "spectator")

        if role == "spectator" and _blocked:
            if request.path in _blocked:
                return redirect(url_for("hub"))
            if request.path == f"{api_prefix.rstrip('/')}/../settings" or \
               (request.path.startswith(api_prefix) and
                request.path.endswith("/settings") and request.method == "PUT"):
                return jsonify({"error": t('errors.forbidden')}), 403

        if check_mutations and request.method in ("POST", "PUT", "DELETE") \
                and request.path.startswith(api_prefix):
            if request.method == "DELETE" and any(request.path.startswith(p) for p in _exempt_del):
                pass
            else:
                perms = auth_db.get_permissions(role)
                if request.method == "DELETE" and not perms.get("can_delete_cases"):
                    return jsonify({"error": t('users.delete_forbidden')}), 403
                if request.method in ("POST", "PUT") and not perms.get("can_write_cases"):
                    return jsonify({"error": t('errors.readonly')}), 403

    return _before_request


def login_required(f):
    """Redirige vers /auth/login si l'utilisateur n'est pas connecté.
    Vérifie aussi que le 2FA est complété si activé."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if _is_api_request():
                return jsonify({"error": t('errors.unauthorized')}), 401
            return redirect(url_for("auth.login_page", next=request.path))

        # ── Si la 2FA est activée globalement ──
        if _is_totp_globally_required():
            # Vérifier que le TOTP a été validé (si activé pour cet utilisateur)
            if session.get("totp_required") and not session.get("totp_verified"):
                if _is_api_request():
                    return jsonify({"error": t('auth.totp_required')}), 401
                return redirect(url_for("auth.totp_page"))

            # Vérifier que le TOTP est configuré (obligatoire pour tous)
            if not session.get("totp_required") and not session.get("totp_setup_done"):
                if auth_db.totp_is_enabled(session["user_id"]):
                    pass
                else:
                    if _is_api_request():
                        return jsonify({"error": t('auth.totp_setup_required')}), 401
                    if request.path != url_for("auth.totp_setup_page"):
                        return redirect(url_for("auth.totp_setup_page"))

        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Vérifie que l'utilisateur connecté a l'un des rôles spécifiés."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                if _is_api_request():
                    return jsonify({"error": t('errors.unauthorized')}), 401
                return redirect(url_for("auth.login_page", next=request.path))

            # Vérifier 2FA (seulement si activée globalement)
            if _is_totp_globally_required():
                if session.get("totp_required") and not session.get("totp_verified"):
                    if _is_api_request():
                        return jsonify({"error": t('auth.totp_required')}), 401
                    return redirect(url_for("auth.totp_page"))

            user_role = session.get("user_role", "")
            if user_role not in roles:
                if _is_api_request():
                    return jsonify({"error": t('errors.forbidden'), "role": user_role}), 403
                return redirect(url_for("hub"))
            return f(*args, **kwargs)
        return decorated
    return decorator


def can_write(f):
    """Autorise admin, admin_centre, user. Refuse spectator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": t('errors.unauthorized')}), 401
        role = session.get("user_role", "spectator")
        perms = auth_db.get_permissions(role)
        if not perms.get("can_write_cases"):
            return jsonify({"error": t('errors.readonly')}), 403
        return f(*args, **kwargs)
    return decorated


def can_delete(f):
    """Autorise admin, admin_centre. Refuse user et spectator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": t('errors.unauthorized')}), 401
        role = session.get("user_role", "spectator")
        perms = auth_db.get_permissions(role)
        if not perms.get("can_delete_cases"):
            return jsonify({"error": t('users.delete_forbidden')}), 403
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════════
#  Gestion session 2FA à deux paliers
# ══════════════════════════════════════════════════════════════════════════

def check_session_2fa():
    """Appelé dans before_request de l'app.
    Vérifie la session absolue (12h max → déconnexion totale).
    La validité 2FA est gérée par un cookie signé séparé (4h), pas par la session.
    Retourne None si OK, ou une Response de redirection."""
    if "user_id" not in session:
        return None

    now = time.time()

    # ── Session absolue : 12h max (sécurité maximale) ──
    login_time = session.get("login_time", 0)
    if login_time and (now - login_time) >= SESSION_ABSOLUTE_MAX_SECONDS:
        audit.log_audit(action="session_expired_absolute")
        session.clear()
        if _is_api_request():
            return jsonify({"error": t('auth.session_expired')}), 401
        return redirect(url_for("auth.login_page"))

    # Mettre à jour last_activity (utilisé pour l'audit)
    session["last_activity"] = now
    return None


# ══════════════════════════════════════════════════════════════════════════
#  Pages
# ══════════════════════════════════════════════════════════════════════════

@auth_bp.route("/auth/login")
def login_page():
    if "user_id" in session and session.get("totp_verified", False):
        return redirect(url_for("hub"))
    return render_template("login.html")


@auth_bp.route("/auth/login", methods=["POST"])
def login_submit():
    """Connexion par formulaire ou JSON, avec rate-limiting progressif.
    Étape 1 du 2FA : validation mot de passe uniquement."""
    if request.is_json:
        data = request.get_json()
        username = data.get("username", "")
        password = data.get("password", "")
    else:
        username = request.form.get("username", "")
        password = request.form.get("password", "")

    client_ip = request.remote_addr or "unknown"

    # ── Rate-limiting : vérifier le délai avant d'autoriser la tentative ──
    delay = login_limiter.get_delay(username, client_ip)
    if delay > 0:
        wait_msg = t('auth.rate_limited', seconds=math.ceil(delay))
        if request.is_json:
            return jsonify({"error": wait_msg, "retry_after": math.ceil(delay)}), 429
        return render_template("login.html", error=wait_msg), 429

    user = auth_db.authenticate(username, password)
    if not user:
        login_limiter.record_failure(username, client_ip)
        audit.log_audit(
            action="login_failed",
            details={"username_attempt": username, "ip": client_ip},
        )
        err_msg = t('auth.invalid_credentials')
        if request.is_json:
            return jsonify({"error": err_msg}), 401
        return render_template("login.html", error=err_msg)

    # Mot de passe OK → réinitialiser le rate-limiter
    login_limiter.record_success(username, client_ip)

    # Stocker en session (palier 1 : mot de passe validé)
    now = time.time()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["user_role"] = user["role"]
    session["display_name"] = user.get("display_name", user["username"])
    session["login_time"] = now
    session["last_activity"] = now
    session.permanent = True

    # Conserver le next_url pour après le TOTP
    next_url = request.form.get("next") or request.args.get("next") or "/"
    parsed = urlparse(next_url)
    if parsed.netloc or parsed.scheme:
        next_url = "/"
    session["login_next_url"] = next_url

    # ── Vérifier si TOTP est activé ──
    totp_global = _is_totp_globally_required()
    has_totp = auth_db.totp_is_enabled(user["id"])

    if not totp_global:
        # 2FA désactivée globalement → connexion directe
        session["totp_required"] = False
        session["totp_verified"] = True
        session["totp_setup_done"] = True
        audit.log_audit(
            action="login",
            user_id=user["id"],
            username=user["username"],
            details={"role": user["role"], "totp": "disabled_globally"},
        )
        if request.is_json:
            return jsonify({"ok": True, "redirect": next_url})
        return redirect(next_url)
    elif has_totp:
        # ── Cookie 2FA encore valide ? → skip TOTP ──
        if _check_2fa_cookie(user["id"]):
            session["totp_required"] = True
            session["totp_verified"] = True
            session["totp_setup_done"] = True
            audit.log_audit(
                action="login",
                user_id=user["id"],
                username=user["username"],
                details={"role": user["role"], "totp": "cookie_valid"},
            )
            if request.is_json:
                return jsonify({"ok": True, "redirect": next_url})
            return redirect(next_url)

        # Cookie 2FA expiré ou absent → demander le code TOTP
        session["totp_required"] = True
        session["totp_verified"] = False
        audit.log_audit(
            action="login_password_ok",
            user_id=user["id"],
            username=user["username"],
            details={"role": user["role"], "totp": "pending"},
        )
        if request.is_json:
            return jsonify({"ok": True, "totp_required": True})
        return redirect(url_for("auth.totp_page"))
    else:
        # TOTP pas encore configuré → rediriger vers setup
        session["totp_required"] = False
        session["totp_verified"] = False
        session["totp_setup_done"] = False
        audit.log_audit(
            action="login_password_ok",
            user_id=user["id"],
            username=user["username"],
            details={"role": user["role"], "totp": "setup_required"},
        )
        if request.is_json:
            return jsonify({"ok": True, "totp_setup_required": True})
        return redirect(url_for("auth.totp_setup_page"))


# ── TOTP : Page de saisie du code ────────────────────────────────────────

@auth_bp.route("/auth/totp")
def totp_page():
    """Affiche la page de saisie du code TOTP."""
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    if session.get("totp_verified"):
        return redirect(url_for("hub"))
    return render_template("totp_verify.html")


@auth_bp.route("/auth/totp", methods=["POST"])
def totp_verify():
    """Valide le code TOTP (étape 2 du login).
    Pose un cookie 2FA signé valide 4h pour éviter de redemander le TOTP
    lors des reconnexions suivantes (après timeout d'inactivité)."""
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    if request.is_json:
        data = request.get_json()
        code = data.get("code", "")
    else:
        code = request.form.get("code", "")

    user_id = session["user_id"]
    secret = auth_db.totp_get_secret(user_id)

    # Essayer d'abord le code TOTP normal
    if auth_db.totp_verify(secret, code):
        _complete_totp_login()
        if request.is_json:
            resp = make_response(jsonify({"ok": True}))
        else:
            next_url = session.pop("login_next_url", "/")
            resp = make_response(redirect(next_url))
        return _set_2fa_cookie(resp, user_id)

    # Essayer comme backup code
    if auth_db.totp_verify_backup_code(user_id, code):
        _complete_totp_login()
        audit.log_audit(
            action="totp_backup_used",
            user_id=user_id,
            username=session.get("username"),
        )
        if request.is_json:
            resp = make_response(jsonify({"ok": True, "backup_used": True}))
        else:
            next_url = session.pop("login_next_url", "/")
            resp = make_response(redirect(next_url))
        return _set_2fa_cookie(resp, user_id)

    # Code invalide
    audit.log_audit(
        action="totp_failed",
        user_id=user_id,
        username=session.get("username"),
    )
    err_msg = t('auth.invalid_code')
    if request.is_json:
        return jsonify({"error": err_msg}), 401
    return render_template("totp_verify.html", error=err_msg)


def _complete_totp_login():
    """Finalise le login 2FA : marquer la session comme totalement authentifiée."""
    now = time.time()
    session["totp_verified"] = True
    session["last_totp_auth"] = now
    session["last_activity"] = now
    session["totp_setup_done"] = True
    audit.log_audit(
        action="login",
        user_id=session["user_id"],
        username=session.get("username"),
        details={"role": session.get("user_role"), "totp": "verified"},
    )


# ── TOTP : Enrollment (première configuration) ──────────────────────────

@auth_bp.route("/auth/totp/setup")
def totp_setup_page():
    """Page d'enrollment TOTP : affiche le QR code."""
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    # Si déjà configuré, pas besoin de re-setup
    if auth_db.totp_is_enabled(session["user_id"]):
        if session.get("totp_verified"):
            return redirect(url_for("hub"))
        return redirect(url_for("auth.totp_page"))

    # Générer un secret temporaire (stocké en session, pas en BDD tant que non confirmé)
    if "totp_setup_secret" not in session:
        session["totp_setup_secret"] = auth_db.totp_generate_secret()

    secret = session["totp_setup_secret"]
    uri = auth_db.totp_get_provisioning_uri(secret, session["username"])

    return render_template("totp_setup.html", totp_uri=uri, totp_secret=secret)


@auth_bp.route("/auth/totp/setup", methods=["POST"])
def totp_setup_confirm():
    """Confirme l'enrollment en validant un premier code TOTP."""
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    secret = session.get("totp_setup_secret", "")
    if not secret:
        return redirect(url_for("auth.totp_setup_page"))

    if request.is_json:
        data = request.get_json()
        code = data.get("code", "")
    else:
        code = request.form.get("code", "")

    # Vérifier le code contre le secret temporaire
    if not auth_db.totp_verify(secret, code):
        uri = auth_db.totp_get_provisioning_uri(secret, session["username"])
        err_msg = t('auth.totp_setup_error')
        if request.is_json:
            return jsonify({"error": err_msg}), 400
        return render_template("totp_setup.html",
                               totp_uri=uri, totp_secret=secret, error=err_msg)

    # Code valide → persister le TOTP en BDD
    user_id = session["user_id"]
    backup_codes = auth_db.totp_enroll(user_id, secret)

    # Nettoyer la session temporaire
    session.pop("totp_setup_secret", None)

    # Marquer la session comme complètement authentifiée
    session["totp_required"] = True
    session["totp_setup_done"] = True
    _complete_totp_login()

    audit.log_audit(
        action="totp_enrolled",
        user_id=user_id,
        username=session.get("username"),
    )

    if request.is_json:
        resp = make_response(jsonify({"ok": True, "backup_codes": backup_codes}))
        return _set_2fa_cookie(resp, user_id)

    # Afficher les backup codes une seule fois
    resp = make_response(render_template("totp_backup_codes.html", backup_codes=backup_codes))
    return _set_2fa_cookie(resp, user_id)


# ── TOTP : QR code image endpoint ───────────────────────────────────────

@auth_bp.route("/auth/totp/qr")
def totp_qr_image():
    """Génère l'image QR code pour l'enrollment TOTP."""
    if "user_id" not in session:
        return "", 401

    secret = session.get("totp_setup_secret", "")
    if not secret:
        return "", 404

    uri = auth_db.totp_get_provisioning_uri(secret, session["username"])

    import qrcode
    qr = qrcode.QRCode(version=1, box_size=6, border=4,
                        error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(uri)
    qr.make(fit=True)
    # QR standard : modules noirs sur fond blanc (requis pour la lecture par les apps)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.read(), mimetype="image/png")


# ══════════════════════════════════════════════════════════════════════════
#  Pages classiques
# ══════════════════════════════════════════════════════════════════════════

@auth_bp.route("/auth/logout")
def logout():
    audit.log_audit(action="logout")
    session.clear()
    # NB : on ne supprime PAS le cookie 2FA signé.
    # Il reste valide (4h par défaut) pour éviter de redemander
    # le code TOTP à chaque reconnexion sur le même navigateur.
    return redirect(url_for("auth.login_page"))


# ══════════════════════════════════════════════════════════════════════════
#  API : Utilisateur connecté
# ══════════════════════════════════════════════════════════════════════════

@auth_bp.route("/auth/api/me")
def api_me():
    if "user_id" not in session:
        return jsonify({"error": t('errors.unauthorized')}), 401
    perms = auth_db.get_permissions(session.get("user_role", "spectator"))
    return jsonify({
        "id": session["user_id"],
        "username": session["username"],
        "role": session["user_role"],
        "display_name": session.get("display_name", ""),
        "permissions": perms,
        "totp_enabled": auth_db.totp_is_enabled(session["user_id"]),
        "totp_verified": session.get("totp_verified", False),
    })


# ══════════════════════════════════════════════════════════════════════════
#  API : Gestion des utilisateurs
# ══════════════════════════════════════════════════════════════════════════

@auth_bp.route("/auth/api/users", methods=["GET"])
@role_required("admin", "admin_centre")
def api_list_users():
    users = auth_db.list_users()
    return jsonify({"users": users})


@auth_bp.route("/auth/api/users", methods=["POST"])
@role_required("admin", "admin_centre")
def api_create_user():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "user")
    display_name = data.get("display_name", "")

    if not username or not password:
        return jsonify({"error": t('users.required_fields')}), 400

    if role not in auth_db.ROLES:
        return jsonify({"error": t('users.invalid_role')}), 400

    # Vérifier que le créateur a le droit de créer ce rôle
    creator_role = session.get("user_role", "")
    creator_perms = auth_db.get_permissions(creator_role)
    if role not in creator_perms.get("can_create_roles", []):
        return jsonify({"error": t('users.cannot_create_role', role=role)}), 403

    uid = auth_db.create_user(
        username=username,
        password=password,
        role=role,
        display_name=display_name,
        created_by=session.get("username", ""),
    )
    if uid is None:
        return jsonify({"error": t('auth.username_exists')}), 409

    audit.log_audit(
        action="create_user",
        resource_type="user",
        resource_id=str(uid),
        details={"created_username": username, "role": role},
    )
    return jsonify({"ok": True, "id": uid}), 201


@auth_bp.route("/auth/api/users/<int:user_id>", methods=["PUT"])
@role_required("admin", "admin_centre")
def api_update_user(user_id):
    data = request.get_json() or {}
    target = auth_db.get_user(user_id)
    if not target:
        return jsonify({"error": t('users.not_found')}), 404

    creator_role = session.get("user_role", "")

    # admin_centre ne peut pas modifier un admin
    if creator_role == "admin_centre" and target["role"] == "admin":
        return jsonify({"error": t('users.cannot_edit_admin')}), 403

    # Vérifier changement de rôle
    new_role = data.get("role")
    if new_role and new_role != target["role"]:
        creator_perms = auth_db.get_permissions(creator_role)
        if new_role not in creator_perms.get("can_create_roles", []):
            return jsonify({"error": t('users.cannot_create_role', role=new_role)}), 403

    auth_db.update_user(user_id, data)
    audit.log_audit(
        action="update_user",
        resource_type="user",
        resource_id=str(user_id),
        details={"target": target.get("username"), "changes": list(data.keys())},
    )
    return jsonify({"ok": True})


@auth_bp.route("/auth/api/users/<int:user_id>", methods=["DELETE"])
@role_required("admin")
def api_delete_user(user_id):
    target = auth_db.get_user(user_id)
    if not target:
        return jsonify({"error": t('users.not_found')}), 404

    auth_db.delete_user(user_id)
    audit.log_audit(
        action="delete_user",
        resource_type="user",
        resource_id=str(user_id),
        details={"deleted_username": target.get("username")},
    )
    return jsonify({"ok": True})


# ── API : Reset TOTP (admin uniquement) ──────────────────────────────────

@auth_bp.route("/auth/api/users/<int:user_id>/totp-reset", methods=["POST"])
@role_required("admin")
def api_totp_reset(user_id):
    """Réinitialise le TOTP d'un utilisateur (admin uniquement)."""
    target = auth_db.get_user(user_id)
    if not target:
        return jsonify({"error": t('users.not_found')}), 404

    auth_db.totp_reset(user_id)
    audit.log_audit(
        action="totp_reset",
        resource_type="user",
        resource_id=str(user_id),
        details={"target_username": target.get("username"),
                 "reset_by": session.get("username")},
    )
    return jsonify({"ok": True, "message": t('users.totp_reset_done')})
