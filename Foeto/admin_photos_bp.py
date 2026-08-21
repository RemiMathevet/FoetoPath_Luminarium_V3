"""FoetoPath — Sous-blueprint Admin Photos (monté sous /admin)."""

import os
import logging
from collections import OrderedDict
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_file

import db
from config import PHOTO_EXTENSIONS
from i18n import t
from utils.file_ops import (
    list_photos_in, validate_photo_path, get_photo_mime,
    generate_thumbnail, cat_info, photo_label,
)

log = logging.getLogger(__name__)

admin_photos_bp = Blueprint("admin_photos", __name__)


@admin_photos_bp.route("/viewer-photos")
def viewer_photos():
    """Page viewer photos macro pour un cas."""
    case_id = request.args.get("case_id")
    photos_path = request.args.get("path", "")
    return render_template("viewer_photos.html", case_id=case_id, photos_path=photos_path)


@admin_photos_bp.route("/api/photos/list", methods=["POST"])
def api_photos_list():
    """Liste les photos d'un cas dans l'ordre exact des JSON modules.

    Ordre : macro_frais.photos → macro_autopsie.photos → (futur: fixé, neuropath)
    Les extras sont classés selon leur position (entre photo_ = ext, entre p_ = autopsie).
    """
    data = request.get_json() or {}
    folder = data.get("path", "")
    case_id = data.get("case_id")

    # Récupérer le cas et les modules
    json_sections = []  # [(section_label, photos_list)]
    if case_id:
        case = db.get_case(int(case_id))
        if case and case.get("dossier_macro_path") and not folder:
            folder = case["dossier_macro_path"]

        # macro_frais → examen externe + anomalies + extras
        macro_frais = db.get_module_data(int(case_id), "macro_frais")
        if macro_frais and macro_frais.get("photos"):
            json_sections.append(("macro_frais", macro_frais["photos"]))

        # macro_autopsie → autopsie
        macro_autopsie = db.get_module_data(int(case_id), "macro_autopsie")
        if macro_autopsie and macro_autopsie.get("photos"):
            json_sections.append(("macro_autopsie", macro_autopsie["photos"]))

        # macro_fixe → fixé (tranches de section, lésions)
        macro_fixe = db.get_module_data(int(case_id), "macro_fixe")
        if macro_fixe and macro_fixe.get("photos"):
            json_sections.append(("macro_fixe", macro_fixe["photos"]))

        # neuropath → neuropathologie
        neuropath = db.get_module_data(int(case_id), "neuropath")
        if neuropath:
            np_photos = neuropath.get("photos", [])
            if not np_photos and neuropath.get("photo_keys"):
                np_photos = [{"key": k, "label": photo_label(k)} for k in neuropath["photo_keys"]]
            if np_photos:
                json_sections.append(("neuropath", np_photos))

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": t('errors.not_found')}), 400

    # ── Scanner les fichiers sur disque ──
    files_on_disk = {}  # key (sans préfixe dossier) → photo dict
    for check_dir in [folder, os.path.join(folder, "photos")]:
        if os.path.isdir(check_dir):
            for p in list_photos_in(check_dir):
                stem = p["name"].lower()
                parts = stem.split("_", 1)
                key = parts[1] if len(parts) > 1 else stem
                files_on_disk[key] = p
                files_on_disk[stem] = p

    # ── Construire les catégories dans l'ordre du JSON ──
    categories = OrderedDict()
    matched_keys = set()

    for section_name, photo_list in json_sections:
        section_context_map = {
            "macro_frais": "externe",
            "macro_autopsie": "autopsie",
            "macro_fixe": "fixe",
            "neuropath": "neuropath",
        }
        context = section_context_map.get(section_name, "autre")

        for entry in photo_list:
            key = entry.get("key", "").lower()
            label = entry.get("label", "")

            if key.startswith("anomal"):
                cat = "anomalie"
            elif key.startswith("extra") or key.startswith("xp_"):
                cat = f"extra_{context}"
            elif section_name == "macro_fixe":
                if key.startswith("p_tranche"):
                    cat = "fixe"
                elif key.startswith("p_lesion"):
                    cat = "fixe_lesion"
                else:
                    cat = "fixe"
            else:
                cat = context

            photo_file = files_on_disk.get(key)
            if not photo_file:
                continue

            matched_keys.add(key)

            cat_meta = cat_info(cat)
            if cat not in categories:
                categories[cat] = {"label": cat_meta[0], "icon": cat_meta[1], "photos": []}

            photo_file["label"] = label or photo_label(key)
            categories[cat]["photos"].append(photo_file)

    # ── Photos sur disque non matchées dans le JSON → "Autres" ──
    for key, p in files_on_disk.items():
        if key not in matched_keys and p.get("filename") and not any(
            p["filename"] == ep["filename"]
            for cat_data in categories.values()
            for ep in cat_data["photos"]
        ):
            if "autre" not in categories:
                categories["autre"] = {"label": "Autres", "icon": "📁", "photos": []}
            p["label"] = photo_label(key)
            categories["autre"]["photos"].append(p)

    total = sum(len(c["photos"]) for c in categories.values())

    ordered = OrderedDict()
    if "anomalie" in categories:
        ordered["anomalie"] = categories["anomalie"]
    for k, v in categories.items():
        if k != "anomalie":
            ordered[k] = v

    return jsonify({
        "path": folder,
        "total": total,
        "categories": ordered,
    })


@admin_photos_bp.route("/api/photo/serve")
def api_serve_photo():
    """Sert une photo pour preview."""
    path = request.args.get("path", "")
    ok, err = validate_photo_path(path, allowed_dir=db.get_setting("data_root"))
    if not ok:
        return jsonify({"error": err}), 404 if "trouvée" in err else 403
    return send_file(path, mimetype=get_photo_mime(path))


@admin_photos_bp.route("/api/photo/thumbnail")
def api_photo_thumbnail():
    """Génère un thumbnail pour une photo."""
    from flask import Response
    path = request.args.get("path", "")
    ok, err = validate_photo_path(path, allowed_dir=db.get_setting("data_root"))
    if not ok:
        return Response(generate_thumbnail("", w=160, h=160), mimetype="image/jpeg")
    w = int(request.args.get("w", 160))
    h = int(request.args.get("h", 160))
    return Response(generate_thumbnail(path, w, h), mimetype="image/jpeg")
