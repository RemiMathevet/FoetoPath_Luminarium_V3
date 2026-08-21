#!/usr/bin/env python3
"""
FoetoPath — Blueprint Admin.

Routes pour :
  - Gestion des cas (CRUD)
  - Sync téléphone → PC
  - Scan des dossiers macro
  - Appairage lames / macro
  - Paramètres
  - Import JSON

Sous-blueprints (montés automatiquement) :
  - admin_photos_bp  → photos viewer, list, serve, thumbnail
  - admin_llm_bp     → compute, LLM (Magos), foekinator, micro, concat, pipeline LLM
  - admin_cr_bp      → CR templates, generate, LLM CR
  - admin_pwa_bp     → PWA submit, load, photo
"""

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

import requests as http_requests

from flask import Blueprint, Response, abort, jsonify, render_template, request, session

log = logging.getLogger(__name__)

import db
from auth_bp import login_required, role_required, can_write, can_delete
import config
from config import KNOWN_MODULES_FOETUS
from i18n import t

admin_bp = Blueprint(
    "admin",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/admin",
)


# ── Auth : protéger toutes les routes du blueprint ──────────────────────
from auth_bp import make_before_request

admin_bp.before_request(make_before_request(
    api_prefix="/admin/api/",
    exempt_paths={"/admin/api/pwa/submit", "/admin/api/pwa/load", "/admin/api/pwa/photo"},
    exempt_delete_paths={"/admin/api/cr/user-templates/"},
    spectator_blocked_pages={"/admin/settings"},
    check_mutations=True,
))


# ── Page principale ────────────────────────────────────────────────────────

@admin_bp.route("/")
def admin_index():
    """Page d'administration principale (fœtus)."""
    return render_template("admin.html")


@admin_bp.route("/placenta")
def admin_placenta():
    """Page d'administration placentas."""
    return render_template("admin_placenta.html")


@admin_bp.route("/users")
def admin_users():
    """Page de gestion des utilisateurs (protégée par before_request + JS côté client)."""
    return render_template("users.html")


@admin_bp.route("/settings")
def admin_settings():
    """Page de paramètres globaux."""
    return render_template("settings.html")


# ── API Cases CRUD + Modules (via factory) ────────────────────────────────

from crud_factory import register_crud_routes
from services.embed_queue import enqueue_for_embedding


def _enrich_list_item(case):
    case["macro_folders"] = db.get_macro_folders(case["id"])


def _enrich_detail(case, case_id):
    case["macro_folders"] = db.get_macro_folders(case_id)
    macro_path = case.get("dossier_macro_path")
    dossier = case.get("numero_dossier")
    if macro_path and dossier:
        from utils.file_ops import find_photo_avant_ouverture, extract_exif_datetime
        photo = find_photo_avant_ouverture(macro_path, dossier)
        if photo:
            case["date_autopsie_exif"] = extract_exif_datetime(photo)


def _track_username(data):
    username = session.get("username", "")
    if username:
        data.setdefault("created_by", username)
        data["modified_by"] = username


def _track_username_update(data):
    username = session.get("username", "")
    if username:
        data["modified_by"] = username


def _on_update(case_id, data):
    if data.get("statut") == "archive":
        case = db.get_case(case_id)
        if case:
            enqueue_for_embedding(case["numero_dossier"])


register_crud_routes(admin_bp, db, KNOWN_MODULES_FOETUS, hooks={
    "enrich_list_item": _enrich_list_item,
    "enrich_detail": _enrich_detail,
    "prepare_create": _track_username,
    "prepare_update": _track_username_update,
    "on_update": _on_update,
})


# ── Genes (bam_gene) ─────────────────────────────────────────────────────

@admin_bp.route("/api/cases/<int:case_id>/genes", methods=["GET"])
def api_get_genes(case_id):
    return jsonify(db.get_genes(case_id))


@admin_bp.route("/api/cases/<int:case_id>/genes", methods=["POST"])
def api_add_gene(case_id):
    data = request.get_json()
    if not data or not data.get("code"):
        return jsonify({"error": "code requis"}), 400
    db.add_gene(case_id, data["code"], data.get("label", ""))
    return jsonify({"message": "gene added"}), 201


@admin_bp.route("/api/cases/<int:case_id>/genes", methods=["DELETE"])
def api_remove_gene(case_id):
    data = request.get_json()
    if not data or not data.get("code"):
        return jsonify({"error": "code requis"}), 400
    db.remove_gene(case_id, data["code"])
    return jsonify({"message": "gene removed"})


# ── Biologic Methods (bam_biologic_method) ────────────────────────────────

@admin_bp.route("/api/cases/<int:case_id>/biologic-methods", methods=["GET"])
def api_get_biologic_methods(case_id):
    return jsonify(db.get_biologic_methods(case_id))


@admin_bp.route("/api/cases/<int:case_id>/biologic-methods", methods=["POST"])
def api_add_biologic_method(case_id):
    data = request.get_json()
    if not data or not data.get("code"):
        return jsonify({"error": "code requis"}), 400
    db.add_biologic_method(case_id, data["code"], data.get("label", ""))
    return jsonify({"message": "biologic method added"}), 201


@admin_bp.route("/api/cases/<int:case_id>/biologic-methods", methods=["DELETE"])
def api_remove_biologic_method(case_id):
    data = request.get_json()
    if not data or not data.get("code"):
        return jsonify({"error": "code requis"}), 400
    db.remove_biologic_method(case_id, data["code"])
    return jsonify({"message": "biologic method removed"})


# ── Scan dossiers macro ───────────────────────────────────────────────────

@admin_bp.route("/api/cases/<int:case_id>/scan-macro", methods=["POST"])
def api_scan_macro(case_id):
    """Scanne les sous-dossiers macro d'un cas."""
    from services.sync import scan_macro_for_case
    try:
        result = scan_macro_for_case(case_id)
        return jsonify(result)
    except ValueError as e:
        log.warning("Scan macro — cas non trouvé: %s", e)
        return jsonify({"error": t('errors.case_inaccessible')}), 404


# ── Appairage lames / macro ───────────────────────────────────────────────

@admin_bp.route("/api/cases/<int:case_id>/pairing", methods=["GET"])
def api_pairing(case_id):
    """
    Construit le tableau d'appairage pour un cas :
    - Photos macro frais
    - Photos macro fixé (= cassettes)
    - Lames correspondantes
    - Contrôle cassettes vs lames
    """
    from services.pairing import build_pairing_table
    try:
        result = build_pairing_table(case_id)
        return jsonify(result)
    except ValueError as e:
        log.warning("Appairage — erreur: %s", e)
        return jsonify({"error": t('errors.insufficient_data')}), 404


_sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sync")
_sync_jobs: dict[str, dict] = {}
_sync_lock = Lock()


def _run_sync_job(job_id: str, scan_path: str):
    from services.sync import run_sync
    try:
        result = run_sync(scan_path)
        with _sync_lock:
            _sync_jobs[job_id].update(status="done", result=result)
    except Exception as e:
        log.warning("Sync job %s — erreur: %s", job_id, e)
        with _sync_lock:
            _sync_jobs[job_id].update(status="error", error=str(e))


@admin_bp.route("/api/sync", methods=["POST"])
def api_sync():
    """Lance un scan async du dossier local, retourne un job_id pour polling."""
    data = request.get_json() or {}
    scan_path = data.get("source_dir") or db.get_setting("data_root")

    if not scan_path:
        return jsonify({"error": t('errors.no_data_root')}), 400

    with _sync_lock:
        running = any(j["status"] == "running" for j in _sync_jobs.values())
    if running:
        return jsonify({"error": "Un sync est déjà en cours"}), 409

    job_id = uuid.uuid4().hex[:12]
    with _sync_lock:
        _sync_jobs[job_id] = {"status": "running", "source": scan_path}

    _sync_executor.submit(_run_sync_job, job_id, scan_path)
    return jsonify({"job_id": job_id, "status": "running"})


@admin_bp.route("/api/sync/<job_id>", methods=["GET"])
def api_sync_status(job_id):
    """Polling endpoint : retourne le statut du job sync."""
    with _sync_lock:
        job = _sync_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job introuvable"}), 404
    return jsonify(job)


# ── Settings ──────────────────────────────────────────────────────────────

@admin_bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(db.get_all_settings())


@admin_bp.route("/api/settings", methods=["PUT"])
def api_save_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": t('errors.data_required')}), 400

    # Settings 2FA : réservés aux admin / admin_centre
    SECURITY_SETTINGS = {"totp_required", "totp_cookie_hours"}
    role = session.get("user_role", "spectator")
    has_security_keys = SECURITY_SETTINGS & set(data.keys())
    if has_security_keys and role not in ("admin", "admin_centre"):
        return jsonify({"error": t('errors.security_admin_only')}), 403

    for k, v in data.items():
        db.set_setting(k, str(v))
    return jsonify({"message": t('settings.saved')})


@admin_bp.route("/api/settings/test-path", methods=["POST"])
def api_test_path():
    """Vérifie si un chemin existe et est accessible en écriture."""
    data = request.get_json() or {}
    raw = data.get("path", "").strip()
    if not raw:
        return jsonify({"exists": False, "writable": False, "error": t('settings.path_required')})
    p = Path(os.path.expanduser(raw))
    exists = p.is_dir()
    writable = exists and os.access(str(p), os.W_OK)
    return jsonify({
        "exists": exists,
        "writable": writable,
        "resolved": str(p),
    })


# ── Répertoire des bases de données (config persistante) ─────────────────

@admin_bp.route("/api/settings/db-directory", methods=["GET"])
@role_required("admin", "admin_centre")
def api_get_db_directory():
    """Retourne le répertoire actuel des fichiers .db et les chemins de chaque base."""
    from flask import current_app
    import persistent_config

    data_dir = current_app.config.get("DATA_DIR", "")
    config = persistent_config.load()

    # Chemins réels des fichiers .db
    db_files = {}
    for name in ["foetopath.db", "placenta.db", "auth.db", "audit.db"]:
        p = Path(data_dir) / name
        db_files[name] = {
            "path": str(p),
            "exists": p.is_file(),
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2) if p.is_file() else 0,
        }

    return jsonify({
        "current_directory": data_dir,
        "config_file": persistent_config.get_config_file_path(),
        "persisted_directory": config.get("db_directory", ""),
        "db_files": db_files,
    })


@admin_bp.route("/api/settings/db-directory", methods=["PUT"])
@role_required("admin", "admin_centre")
def api_set_db_directory():
    """Met à jour le répertoire des fichiers .db (prise en compte au prochain redémarrage)."""
    import persistent_config
    import audit

    data = request.get_json() or {}
    new_dir = data.get("db_directory", "").strip()

    if not new_dir:
        return jsonify({"error": t('settings.path_required')}), 400

    # Résoudre ~ et vérifier
    resolved = str(Path(os.path.expanduser(new_dir)))

    # Vérifier que le dossier existe ou peut être créé
    p = Path(resolved)
    if p.is_file():
        return jsonify({"error": t('settings.path_is_file')}), 400

    if not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return jsonify({"error": t('settings.path_create_error', error=str(e))}), 400

    if not os.access(resolved, os.W_OK):
        return jsonify({"error": t('settings.path_not_writable')}), 400

    # Sauvegarder dans la config persistante
    persistent_config.set_key("db_directory", resolved)

    audit.log_audit(
        action="update_db_directory",
        resource_type="settings",
        details={"new_directory": resolved},
    )

    return jsonify({
        "message": "Répertoire des bases mis à jour. Redémarrez le service pour appliquer.",
        "resolved": resolved,
        "restart_required": True,
    })


# ── Import JSON files ─────────────────────────────────────────────────────

@admin_bp.route("/api/import-json", methods=["POST"])
def api_import_json():
    """Import un fichier JSON pré-examen directement (upload ou path)."""
    data = request.get_json()
    json_path = data.get("path")

    if json_path and os.path.isfile(json_path):
        data_root = db.get_setting("data_root")
        if data_root and not Path(json_path).resolve().is_relative_to(Path(data_root).resolve()):
            return jsonify({"error": "Chemin non autorisé"}), 403
        case_id = db.import_case_from_json(json_path)
        if case_id:
            return jsonify({"message": "Importé", "case_id": case_id})
        return jsonify({"error": t('errors.dossier_required')}), 400

    # Import depuis le body directement
    json_data = data.get("data")
    if json_data:
        admin = json_data.get("case_admin", json_data)
        numero = admin.get("numero_dossier")
        if not numero:
            return jsonify({"error": t('errors.dossier_required')}), 400

        existing = db.get_case_by_numero(numero)
        if existing:
            case_id = existing["id"]
            db.update_case(case_id, admin)
        else:
            case_id = db.create_case(admin)

        # Sauvegarder les modules
        for key in ["atcd_maternels", "grossesse_en_cours", "examens_prenataux", "atcd_obstetricaux"]:
            if key in json_data:
                db.save_module_data(case_id, key, json_data[key])

        return jsonify({"message": "Importé", "case_id": case_id})

    return jsonify({"error": t('errors.data_required')}), 400


# ── Proxy Luminarium (slide thumbnails) ──────────────────────────────────

def _viewer_url_local():
    """URL locale du viewer pour les appels backend (thumbnails, etc.)."""
    port = db.get_setting("viewer_port", "5080")
    return f"http://127.0.0.1:{port}"


def _viewer_url():
    """URL du viewer pour le frontend (proxy ou override externe)."""
    override = db.get_setting("viewer_url", "")
    if override:
        return override.rstrip("/")
    return "/viewer"


@admin_bp.route("/api/viewer-url")
@login_required
def api_viewer_url():
    return jsonify({"url": _viewer_url()})


@admin_bp.route("/api/slide-thumbnail")
@login_required
def proxy_slide_thumbnail():
    path = request.args.get("path", "")
    w = request.args.get("w", "300")
    h = request.args.get("h", "200")
    try:
        resp = http_requests.get(
            f"{_viewer_url_local()}/api/slide/thumbnail",
            params={"path": path, "w": w, "h": h},
            timeout=5,
        )
        if resp.ok:
            return Response(resp.content, mimetype=resp.headers.get("Content-Type", "image/jpeg"))
        abort(resp.status_code)
    except http_requests.RequestException:
        abort(502)


# ── Lumi integration (read-only) ─────────────────────────────────────────

from services.lumi import get_slides_for_case, get_slide_counts


@admin_bp.route("/api/cases/<int:case_id>/lumi-slides")
@login_required
def api_lumi_slides(case_id):
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": "Cas non trouvé"}), 404
    data = get_slides_for_case(case["numero_dossier"])
    data["viewer_url"] = _viewer_url()
    return jsonify(data)


@admin_bp.route("/api/lumi-counts")
@login_required
def api_lumi_counts():
    numeros = request.args.get("numeros", "").split(",")
    numeros = [n.strip() for n in numeros if n.strip()]
    if not numeros:
        return jsonify({})
    return jsonify(get_slide_counts(numeros))


@admin_bp.route("/api/cases/<int:case_id>/annotation-report")
@login_required
def api_annotation_report(case_id):
    """Fetch bilan histo from viewer, persist in module bilan_histo, return it."""
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": "Cas non trouvé"}), 404

    # Always try live viewer first — saves to DB on success
    lumi_data = get_slides_for_case(case["numero_dossier"])
    slides = lumi_data.get("slides", [])
    first_path = next((s["full_path"] for s in slides if s.get("full_path")), None) if slides else None
    if first_path:
        folder = str(Path(first_path).parent)
        try:
            resp = http_requests.get(
                f"{_viewer_url_local()}/api/annotations/report",
                params={"folder": folder},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                db.save_module_data(case_id, "bilan_histo", data)
                return jsonify(data)
        except http_requests.RequestException:
            pass

    # Fallback: DB copy when viewer is off
    saved = db.get_module_data(case_id, "bilan_histo")
    if saved:
        return jsonify(saved)
    return jsonify({"slides": []})


# ── Dashboard lames (admin) ──────────────────────────────────────────────

@admin_bp.route("/lames")
@role_required("admin", "admin_centre")
def admin_lames():
    return render_template("admin_lames.html")


@admin_bp.route("/api/lames/dashboard")
@role_required("admin", "admin_centre")
def api_lames_dashboard():
    from services.lumi import _lames_db_path, _connect_readonly

    db_path = _lames_db_path()
    result = {
        "lames_db": db_path,
        "stats": {"total": 0, "in_viewer": 0, "annotated": 0, "embedded": 0, "diagnosed": 0, "cases": 0},
        "slides": [],
    }

    conn = _connect_readonly(db_path)
    if not conn:
        return jsonify(result)

    try:
        rows = conn.execute(
            "SELECT id, nom_lame, taille_mo, chemin, storage, cold_root FROM lames "
            "WHERE storage != 'deleted' ORDER BY nom_lame"
        ).fetchall()
    except Exception:
        conn.close()
        return jsonify(result)

    cases_seen = set()
    slides_map = {}
    for r in rows:
        name = r["nom_lame"]
        case_prefix = name.split("_")[0]
        cases_seen.add(case_prefix)
        slides_map[name] = {
            "nom_lame": name,
            "case": case_prefix,
            "taille_mo": r["taille_mo"],
            "storage": r["storage"] or "hot",
            "in_viewer": False,
            "tissue_type": None,
            "diag_count": 0,
            "annot_count": 0,
            "embed_count": 0,
            "full_path": None,
        }

    result["stats"]["total"] = len(slides_map)
    result["stats"]["cases"] = len(cases_seen)

    try:
        vrows = conn.execute(
            "SELECT slide_id, tissue_type, folder, filename FROM slides"
        ).fetchall()
        for vr in vrows:
            sid = vr["slide_id"]
            if sid in slides_map:
                slides_map[sid]["in_viewer"] = True
                slides_map[sid]["tissue_type"] = vr["tissue_type"]
                if vr["folder"] and vr["filename"]:
                    slides_map[sid]["full_path"] = vr["folder"] + "/" + vr["filename"]
                result["stats"]["in_viewer"] += 1

        drows = conn.execute("SELECT slide_id, COUNT(*) as cnt FROM diagnoses GROUP BY slide_id").fetchall()
        for dr in drows:
            if dr["slide_id"] in slides_map:
                slides_map[dr["slide_id"]]["diag_count"] = dr["cnt"]
        result["stats"]["diagnosed"] = sum(1 for s in slides_map.values() if s["diag_count"] > 0)

        arows = conn.execute("SELECT slide_id, COUNT(*) as cnt FROM annotations GROUP BY slide_id").fetchall()
        for ar in arows:
            if ar["slide_id"] in slides_map:
                slides_map[ar["slide_id"]]["annot_count"] = ar["cnt"]
        result["stats"]["annotated"] = sum(1 for s in slides_map.values() if s["annot_count"] > 0)

        erows = conn.execute("SELECT slide_id, COUNT(*) as cnt FROM embeddings GROUP BY slide_id").fetchall()
        for er in erows:
            if er["slide_id"] in slides_map:
                slides_map[er["slide_id"]]["embed_count"] = er["cnt"]
        result["stats"]["embedded"] = sum(1 for s in slides_map.values() if s["embed_count"] > 0)

    except Exception as e:
        log.debug("Lames dashboard query failed: %s", e)
    finally:
        conn.close()

    result["slides"] = list(slides_map.values())
    return jsonify(result)


# ── Sous-blueprints ──────────────────────────────────────────────────────

from admin_photos_bp import admin_photos_bp
from admin_llm_bp import admin_llm_bp
from admin_cr_bp import admin_cr_bp
from admin_pwa_bp import admin_pwa_bp

admin_bp.register_blueprint(admin_photos_bp)
admin_bp.register_blueprint(admin_llm_bp)
admin_bp.register_blueprint(admin_cr_bp)
admin_bp.register_blueprint(admin_pwa_bp)
