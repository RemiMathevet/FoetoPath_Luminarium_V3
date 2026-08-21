"""FoetoPath — Sous-blueprint Admin PWA (monté sous /admin)."""

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

import db
from config import PHOTO_EXTENSIONS
from i18n import t

log = logging.getLogger(__name__)

admin_pwa_bp = Blueprint("admin_pwa", __name__)


@admin_pwa_bp.route("/api/pwa/submit", methods=["POST"])
def api_pwa_submit():
    """
    Réception des données depuis la PWA fœtus.
    FormData attendu :
      - json_data: string JSON (macro_frais, macro_autopsie, macro_fixe, neuropath)
      - dossier: numéro de dossier
      - module: nom du module
      - photo_<key>: fichiers image (multiples, un par clé)
      - b64_<key>: photos en base64 dataURL (alternative aux fichiers)
    """
    from flask import session as flask_session

    json_str = request.form.get("json_data", "{}")
    dossier = request.form.get("dossier", "").strip()
    module = request.form.get("module", "macro_frais")

    if not dossier:
        return jsonify({"error": t('errors.dossier_required')}), 400

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return jsonify({"error": t('errors.invalid_json')}), 400

    submit_user = flask_session.get("username", "") or request.form.get("user", "pwa")

    # ── Trouver ou créer le cas ──
    existing = db.get_case_by_numero(dossier)
    if existing:
        case_id = existing["id"]
        db.update_case(case_id, {"modified_by": submit_user})
    else:
        case_id = db.create_case({
            "numero_dossier": dossier,
            "sexe": data.get("sexe"),
            "terme_issue": str(data.get("terme", {}).get("sa", "")) if data.get("terme") else None,
            "created_by": submit_user,
            "modified_by": submit_user,
        })

    # ── Sauvegarder les données du module (avec tracking utilisateur) ──
    if data.get("dossier") and data["dossier"] != dossier:
        log.warning("PWA dossier mismatch: form=%s, json=%s — forcing form value", dossier, data["dossier"])
    data["dossier"] = dossier
    data["_submitted_by"] = submit_user
    data["_submitted_at"] = datetime.now(timezone.utc).isoformat()
    data["_submitted_via"] = "pwa"
    db.save_module_data(case_id, module, data)

    # ── Déterminer le répertoire de stockage ──
    data_root = db.get_setting("data_root")
    if data_root:
        base_dir = Path(data_root) / "Foetus" / dossier
    elif existing and existing.get("dossier_macro_path"):
        base_dir = Path(existing["dossier_macro_path"])
    else:
        base_dir = db.get_db_path().parent / "Foetus" / dossier

    case_dir = base_dir / "photos"
    case_dir.mkdir(parents=True, exist_ok=True)

    json_path = base_dir / f"{dossier}_{module}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    db.update_case(case_id, {"dossier_macro_path": str(base_dir)})

    # ── Sauvegarder les photos sur disque ──
    photos_saved = 0

    for key in request.files:
        if key.startswith("photo_"):
            photo_key = key[6:]
            fobj = request.files[key]
            if fobj and fobj.filename:
                ext = Path(fobj.filename).suffix.lower() or ".jpg"
                if ext not in PHOTO_EXTENSIONS:
                    continue
                photo_path = case_dir / f"{dossier}_{photo_key}{ext}"
                fobj.save(str(photo_path))
                photos_saved += 1

    for key in request.form:
        if key.startswith("b64_"):
            photo_key = key[4:]
            b64_data = request.form[key]
            if "," in b64_data:
                header, b64_content = b64_data.split(",", 1)
                ext = ".jpg"
                if "png" in header:
                    ext = ".png"
                elif "webp" in header:
                    ext = ".webp"
            else:
                b64_content = b64_data
                ext = ".jpg"
            try:
                img_bytes = base64.b64decode(b64_content)
                photo_path = case_dir / f"{dossier}_{photo_key}{ext}"
                with open(photo_path, "wb") as f:
                    f.write(img_bytes)
                photos_saved += 1
            except (ValueError, OSError):
                log.warning("Failed to save photo for %s", dossier, exc_info=True)

    try:
        db.scan_macro_folders(case_id, str(base_dir))
    except Exception:
        log.warning("Failed to scan macro folders for case %s", case_id, exc_info=True)

    return jsonify({
        "status": "ok",
        "case_id": case_id,
        "module": module,
        "photos_saved": photos_saved,
        "message": f"Module {module} sauvegardé pour {dossier}",
    })


@admin_pwa_bp.route("/api/pwa/load", methods=["GET"])
def api_pwa_load():
    """
    Charge les données d'un cas pour la PWA fœtus.
    Params: dossier=<numero>, module=<nom_module> (optionnel)
    Retourne le cas + données module + liste des photos disponibles.
    """
    dossier = request.args.get("dossier", "").strip()
    module = request.args.get("module")

    if not dossier:
        return jsonify({"error": t('errors.dossier_required')}), 400

    case = db.get_case_by_numero(dossier)
    if not case:
        return jsonify({"found": False}), 200

    # PC macro frais pour auto-fill radio
    mf = db.get_module_data(case["id"], "macro_frais")
    pc_macro = None
    if mf:
        bio = mf.get("biometries", mf.get("biometrie", {}))
        if isinstance(bio, dict):
            pc_macro = bio.get("pc")

    result = {
        "found": True,
        "case_id": case["id"],
        "dossier": dossier,
        "terme_issue": case.get("terme_issue"),
        "pc_macro": pc_macro,
    }

    if module:
        mod_data = db.get_module_data(case["id"], module)
        # Injecter PC macro frais dans les données radio pour restoreData()
        if module == "radio" and pc_macro:
            if not mod_data:
                mod_data = {"type": "imagerie_radio", "biometries": {"pc_radio_mm": pc_macro}}
            elif isinstance(mod_data, dict):
                bio = mod_data.setdefault("biometries", {})
                if isinstance(bio, dict) and not bio.get("pc_radio_mm"):
                    bio["pc_radio_mm"] = pc_macro
        result["data"] = mod_data
    else:
        result["modules"] = db.get_all_modules(case["id"])

    photo_list = []
    macro_path = case.get("dossier_macro_path", "")
    if macro_path:
        photos_dir = Path(macro_path) / "photos"
        if photos_dir.is_dir():
            for p in sorted(photos_dir.iterdir()):
                if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS:
                    stem = p.stem.lower()
                    parts = stem.split("_", 1)
                    key = parts[1] if len(parts) > 1 else stem
                    photo_list.append({
                        "key": key,
                        "filename": p.name,
                        "path": str(p),
                    })

    result["photos_on_disk"] = photo_list
    return jsonify(result)


@admin_pwa_bp.route("/api/pwa/photo", methods=["GET"])
def api_pwa_photo():
    """Sert une photo pour la PWA par clé et dossier."""
    dossier = request.args.get("dossier", "").strip()
    key = request.args.get("key", "").strip()

    if not dossier or not key:
        return jsonify({"error": t('errors.data_required')}), 400

    case = db.get_case_by_numero(dossier)
    if not case or not case.get("dossier_macro_path"):
        return jsonify({"error": t('errors.case_not_found')}), 404

    photos_dir = Path(case["dossier_macro_path"]) / "photos"
    if not photos_dir.is_dir():
        return jsonify({"error": t('errors.not_found')}), 404

    for p in photos_dir.iterdir():
        if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS:
            stem = p.stem.lower()
            parts = stem.split("_", 1)
            file_key = parts[1] if len(parts) > 1 else stem
            if file_key == key.lower() or stem == f"{dossier.lower()}_{key.lower()}":
                mime_map = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".gif": "image/gif",
                    ".bmp": "image/bmp", ".webp": "image/webp",
                }
                return send_file(str(p), mimetype=mime_map.get(p.suffix.lower(), "image/jpeg"))

    return jsonify({"error": t('errors.not_found')}), 404
