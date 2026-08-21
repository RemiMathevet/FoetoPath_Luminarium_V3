#!/usr/bin/env python3
"""
FoetoPath — Blueprint Placenta.

Routes pour :
  - Servir la PWA (/pwa/placentas/)
  - API CRUD cas placenta
  - Réception des données + photos depuis la PWA
  - Viewer photos
  - Génération CR Jinja2
"""

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file, send_from_directory
from i18n import t

log = logging.getLogger(__name__)

import audit
import placenta_db as pdb
from services.embed_queue import enqueue_for_embedding
from config import PHOTO_EXTENSIONS, SLIDE_EXTENSIONS, MIME_MAP, KNOWN_MODULES_PLACENTA
from utils.file_ops import (
    list_photos_in, list_slides_in, generate_thumbnail,
    validate_photo_path, validate_photo_key, get_photo_mime,
)

placenta_bp = Blueprint(
    "placenta",
    __name__,
    url_prefix="/placenta",
)


# ── Auth : protéger les routes API (pas les PWA) ────────────────────────
from auth_bp import make_before_request, login_required

placenta_bp.before_request(make_before_request(
    api_prefix="/placenta/api/",
    exempt_paths={"/placenta/api/cases/submit"},
    exempt_prefixes=("/placenta/pwa/",),
    check_mutations=True,
    redirect_on_unauth=False,
))


# ── Servir les fichiers PWA ──────────────────────────────────────────────

PWA_DIR = Path(__file__).parent / "pwa" / "placentas"


@placenta_bp.route("/pwa/<path:filename>")
def pwa_static(filename):
    """Sert les fichiers statiques de la PWA placenta."""
    return send_from_directory(str(PWA_DIR), filename)


# ── Routes PWA (sans préfixe /placenta pour un accès direct) ─────────────
# Ces routes sont enregistrées séparément dans app.py via un second blueprint


# ── API : Check dossier ──────────────────────────────────────────────────

@placenta_bp.route("/api/cases/check")
def api_check_case():
    """Vérifie si un dossier placenta existe."""
    numero = request.args.get("numero", "")
    if not numero:
        return jsonify({"exists": False})
    case = pdb.get_case_by_numero(numero)
    return jsonify({
        "exists": case is not None,
        "case_id": case["id"] if case else None,
    })


# ── API : Soumission depuis PWA (FormData avec photos) ──────────────────

def _resolve_or_create_case(dossier: str, module: str, data: dict, user: str) -> int | None:
    """Crée ou retrouve le cas placenta pour un submit PWA. Retourne case_id ou None."""
    if module == "macro_frais":
        return pdb.import_from_macro_frais_json(data, user=user)
    existing = pdb.get_case_by_numero(dossier)
    case_id = existing["id"] if existing else pdb.create_case({"numero_dossier": dossier}, user=user)
    # Le commentaire se saisit dans le hub, jamais dans la PWA : sans ce report
    # la resynchro d'un formulaire le supprime. Le garde anti-clobber ne le voit
    # pas, il compare au JSON sur disque que seule la PWA écrit.
    if "commentaire" not in data:
        prev = pdb.get_module_data(case_id, module) or {}
        if prev.get("commentaire"):
            data["commentaire"] = prev["commentaire"]
    pdb.save_module_data(case_id, module, data, user=user)
    return case_id


def _save_pwa_photos(req, case_id: int, dossier: str, module: str,
                     photos_dir: Path, user: str) -> int:
    """Sauvegarde les photos envoyées par la PWA (3 formats). Retourne le nombre sauvé."""
    import base64

    saved = 0

    def _persist(photo_key, filename, filepath):
        nonlocal saved
        pdb.save_photo(
            case_id=case_id, photo_key=photo_key, filename=filename,
            label=photo_key.replace("_", " ").title(), module=module,
            file_path=str(filepath),
            size_bytes=filepath.stat().st_size if filepath.exists() else 0,
            user=user,
        )
        saved += 1

    for key in req.files:
        if key.startswith("photo_"):
            photo_key = key[6:]
            if not validate_photo_key(photo_key):
                continue
            fobj = req.files[key]
            if fobj and fobj.filename:
                ext = Path(fobj.filename).suffix or ".jpg"
                photo_path = photos_dir / f"{dossier}_{photo_key}{ext}"
                fobj.save(str(photo_path))
                _persist(photo_key, photo_path.name, photo_path)

    for key in req.form:
        if key.startswith("b64_"):
            photo_key = key[4:]
            if not validate_photo_key(photo_key):
                continue
            b64_data = req.form[key]
            if "," in b64_data:
                header, b64_content = b64_data.split(",", 1)
                ext = ".png" if "png" in header else ".jpg"
            else:
                b64_content = b64_data
                ext = ".jpg"
            try:
                img_bytes = base64.b64decode(b64_content)
                photo_path = photos_dir / f"{dossier}_{photo_key}{ext}"
                with open(photo_path, "wb") as f:
                    f.write(img_bytes)
                _persist(photo_key, photo_path.name, photo_path)
            except (ValueError, OSError):
                log.warning("Placenta: échec décodage b64 pour %s/%s", dossier, photo_key, exc_info=True)

    for photo_file in req.files.getlist("photos"):
        if photo_file and photo_file.filename:
            filename = photo_file.filename
            filepath = photos_dir / filename
            photo_file.save(str(filepath))
            stem = Path(filename).stem
            photo_key = stem[len(dossier) + 1:] if stem.startswith(dossier + "_") else stem
            _persist(photo_key, filename, filepath)

    return saved


@placenta_bp.route("/api/cases/submit", methods=["POST"])
@login_required
def api_submit():
    """Réception des données depuis la PWA (FormData avec JSON + photos)."""
    json_str = request.form.get("json_data", "{}")
    dossier = request.form.get("dossier", "")
    module = request.form.get("module", "macro_frais")

    log.info("PWA submit placenta: dossier=%s module=%s json_len=%d files=%s",
             dossier, module, len(json_str), list(request.files.keys()))

    if not dossier:
        return jsonify({"error": t('errors.dossier_required')}), 400

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        log.warning("PWA submit placenta: invalid JSON for dossier=%s", dossier)
        return jsonify({"error": t('errors.invalid_json')}), 400

    # ── Guard anti-clobber (A) : refuse d'écraser un JSON plus complet par un
    # plus vide. Cause de la perte constatee : resaisie d'un formulaire quasi
    # vide sur un cas déjà rempli. Override explicite via force=1.
    if request.form.get("force") != "1":
        existing = _read_json_from_disk(dossier, module)
        if existing is not None:
            n_old, n_new = _count_filled(existing), _count_filled(data)
            if n_old > n_new:
                log.warning("Clobber bloqué dossier=%s module=%s (%d→%d champs)",
                            dossier, module, n_old, n_new)
                return jsonify({
                    "error": "clobber_blocked",
                    "message": (f"Le dossier {dossier} contient déjà un {module} plus complet "
                                f"({n_old} champs renseignés contre {n_new}). Enregistrement "
                                f"refusé pour éviter d'écraser des données. Rechargez le cas."),
                    "existing_filled": n_old,
                    "incoming_filled": n_new,
                }), 409

    from flask import session as flask_session
    submit_user = flask_session.get("username", "") or request.form.get("user", "pwa")

    if "dossier" not in data:
        data["dossier"] = dossier

    case_id = _resolve_or_create_case(dossier, module, data, submit_user)
    if not case_id:
        return jsonify({"error": t('errors.cannot_create_case')}), 500

    photos_dir = _get_photos_dir(dossier)
    photos_saved = _save_pwa_photos(request, case_id, dossier, module, photos_dir, submit_user)

    pdb.update_case(case_id, {"dossier_photos_path": str(photos_dir)}, user=submit_user)
    _save_json_to_disk(dossier, module, data)

    audit.log_audit(
        action="pwa_submit_placenta",
        resource_type="case",
        resource_id=str(case_id),
        username=submit_user,
        details={"dossier": dossier, "module": module,
                 "photos_saved": photos_saved, "source": "pwa"},
    )

    return jsonify({
        "status": "ok",
        "case_id": case_id,
        "module": module,
        "photos_saved": photos_saved,
    })


def _get_photos_dir(dossier: str) -> Path:
    """Retourne le répertoire photos pour un dossier, le crée si besoin."""
    data_root = _data_root()
    photos_dir = data_root / "Placentas" / dossier / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    log.info("Photos dir for %s: %s (exists=%s)", dossier, photos_dir, photos_dir.exists())
    return photos_dir


def _data_root() -> Path:
    """Retourne le répertoire racine des données."""
    # Essayer le setting global, sinon ~/Documents/FoetoPath
    try:
        import db as foetopath_db
        root = foetopath_db.get_setting("data_root")
        if root:
            return Path(root)
    except Exception:
        log.debug("Failed to load data_root setting, using default", exc_info=True)
    return Path(os.path.expanduser("~/Documents/FoetoPath"))


def _read_json_from_disk(dossier: str, module: str):
    """Relit le JSON module déjà sur disque, ou None s'il n'existe pas/illisible."""
    json_path = _data_root() / "Placentas" / dossier / f"{dossier}_{module}.json"
    if not json_path.exists():
        return None
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _count_filled(obj) -> int:
    """Compte les feuilles renseignées (str non vide, nombre, True). Sert à
    détecter un écrasement d'un cas riche par une soumission quasi vide."""
    if isinstance(obj, dict):
        return sum(_count_filled(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return sum(_count_filled(v) for v in obj)
    if isinstance(obj, str):
        return 1 if obj.strip() else 0
    if isinstance(obj, bool):
        return 1 if obj else 0
    if isinstance(obj, (int, float)):
        return 1
    return 0


def _save_json_to_disk(dossier: str, module: str, data: dict):
    """Écrit le JSON du module sur disque dans le dossier du cas."""
    case_dir = _data_root() / "Placentas" / dossier
    case_dir.mkdir(parents=True, exist_ok=True)
    json_path = case_dir / f"{dossier}_{module}.json"
    try:
        # ponytail: filet anti-clobber. Un seul .bak roulant (version précédente).
        # Suffit à récupérer un écrasement accidentel (cookie expiré → resaisie
        # d'un formulaire quasi vide). Historique complet si besoin un jour.
        if json_path.exists():
            shutil.copy2(json_path, json_path.with_suffix(".json.bak"))
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("Placenta JSON saved: %s", json_path)
    except OSError:
        log.warning("Failed to save JSON to disk: %s", json_path, exc_info=True)


# ── API : CRUD Cases ─────────────────────────────────────────────────────

# ── API Cases CRUD + Modules (via factory) ────────────────────────────────

from crud_factory import register_crud_routes


def _enrich_list_item(case):
    case["photos"] = pdb.get_photos(case["id"])


def _enrich_detail(case, case_id):
    case["photos"] = pdb.get_photos(case_id)


def _list_kwargs(req):
    assigned = req.args.get("assigned_to")
    return {"assigned_to": assigned} if assigned else {}


def _on_create(case_id, data, merged):
    action = "update_case_placenta" if merged else "create_case_placenta"
    details = {"dossier": data.get("numero_dossier", "")}
    if merged:
        details["merged"] = True
    audit.log_audit(action=action, resource_type="case",
                    resource_id=str(case_id), details=details)


def _on_update(case_id, data):
    audit.log_audit(action="update_case_placenta", resource_type="case",
                    resource_id=str(case_id),
                    details={"fields": list(data.keys())})
    if data.get("statut") == "archive":
        case = pdb.get_case(case_id)
        if case:
            enqueue_for_embedding(case["numero_dossier"])


def _on_delete(case_id):
    audit.log_audit(action="delete_case_placenta", resource_type="case",
                    resource_id=str(case_id))


def _on_save_module(case_id, module_name):
    audit.log_audit(action="save_module_placenta", resource_type="case",
                    resource_id=str(case_id),
                    details={"module": module_name})


register_crud_routes(placenta_bp, pdb, KNOWN_MODULES_PLACENTA, hooks={
    "enrich_list_item": _enrich_list_item,
    "enrich_detail": _enrich_detail,
    "list_kwargs": _list_kwargs,
    "on_create": _on_create,
    "on_update": _on_update,
    "on_delete": _on_delete,
    "on_save_module": _on_save_module,
})


# ── API : Photos ─────────────────────────────────────────────────────────

# PHOTO_EXTENSIONS et MIME_MAP importés depuis config.py


@placenta_bp.route("/api/cases/<int:case_id>/photos", methods=["GET"])
def api_list_photos(case_id):
    module = request.args.get("module")
    photos = pdb.get_photos(case_id, module=module)
    return jsonify({"photos": photos, "total": len(photos)})


@placenta_bp.route("/api/photos/list", methods=["POST"])
def api_photos_list():
    """
    Liste les photos d'un cas placenta par catégorie, pour le sidebar du viewer.
    Retourne un format compatible avec le viewer (mêmes clés que l'endpoint foetus).
    """
    body = request.get_json() or {}
    case_id = body.get("case_id")
    if not case_id:
        return jsonify({"error": t('errors.data_required')}), 400

    case = pdb.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    photos_path = case.get("dossier_photos_path", "")
    db_photos = pdb.get_photos(case_id)

    # Catégoriser les photos
    categories = {}

    # Photos macro frais
    frais_photos = [p for p in db_photos if p.get("module") == "macro_frais"]
    if frais_photos:
        categories["frais"] = {
            "icon": "&#x1F7E2;",
            "label": "Macro frais",
            "photos": [{"path": p["file_path"], "label": p.get("label") or p.get("photo_key", ""),
                         "name": p.get("photo_key", ""), "filename": p.get("filename", "")}
                        for p in frais_photos if p.get("file_path")]
        }

    # Photos tranches / lésions
    tranches_photos = [p for p in db_photos if p.get("module") == "tranches_section"]
    if tranches_photos:
        categories["tranches"] = {
            "icon": "&#x1F52A;",
            "label": "Tranches & lésions",
            "photos": [{"path": p["file_path"], "label": p.get("label") or p.get("photo_key", ""),
                         "name": p.get("photo_key", ""), "filename": p.get("filename", "")}
                        for p in tranches_photos if p.get("file_path")]
        }

    # Si pas de photos en DB, scanner le dossier
    if not categories and photos_path:
        pp = Path(photos_path)
        photos_sub = pp / "photos"
        scan_dir = str(photos_sub) if photos_sub.is_dir() else str(pp)
        all_photos = _list_photos_in(scan_dir)

        frais = []
        tranches = []
        for ph in all_photos:
            name_lower = ph["name"].lower()
            if any(k in name_lower for k in ("tr_", "tranche", "lesion", "section")):
                tranches.append(ph)
            else:
                frais.append(ph)

        if frais:
            categories["frais"] = {
                "icon": "&#x1F7E2;",
                "label": "Macro frais",
                "photos": [{"path": p["path"], "label": p["filename"],
                             "name": p["name"], "filename": p["filename"]} for p in frais]
            }
        if tranches:
            categories["tranches"] = {
                "icon": "&#x1F52A;",
                "label": "Tranches & lésions",
                "photos": [{"path": p["path"], "label": p["filename"],
                             "name": p["name"], "filename": p["filename"]} for p in tranches]
            }

    return jsonify({"categories": categories, "case_id": case_id})


@placenta_bp.route("/api/photo/serve")
def api_serve_photo():
    path = request.args.get("path", "")
    import db as foetopath_db
    ok, err = validate_photo_path(path, allowed_dir=foetopath_db.get_setting("data_root"))
    if not ok:
        return jsonify({"error": err}), 404 if "trouvée" in err else 403
    return send_file(path, mimetype=get_photo_mime(path))


@placenta_bp.route("/api/photo/thumbnail")
def api_photo_thumbnail():
    path = request.args.get("path", "")
    import db as foetopath_db
    ok, err = validate_photo_path(path, allowed_dir=foetopath_db.get_setting("data_root"))
    if not ok:
        return Response(generate_thumbnail("", w=160, h=160), mimetype="image/jpeg")
    w = int(request.args.get("w", 160))
    h = int(request.args.get("h", 160))
    return Response(generate_thumbnail(path, w, h), mimetype="image/jpeg")


# SLIDE_EXTENSIONS importé depuis config.py


# _list_slides_in et _list_photos_in → utils.file_ops
_list_slides_in = list_slides_in
_list_photos_in = list_photos_in


@placenta_bp.route("/api/cases/<int:case_id>/pairing", methods=["GET"])
def api_pairing(case_id):
    """
    Construit le tableau d'appairage pour un cas placenta :
    - Photos macro (frais + tranches de section)
    - Lames correspondantes
    """
    case = pdb.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    photos_path = case.get("dossier_photos_path", "")
    lames_path = case.get("dossier_lames_path", "")

    # Chercher le dossier lames via Lumi si pas défini
    if not lames_path:
        from services.lumi import get_case_slides_dir
        lames_path = get_case_slides_dir(case["numero_dossier"]) or ""

    # Si toujours pas trouvé, chercher un sous-dossier "lames" dans le dossier du cas
    if not lames_path:
        case_dir = _data_root() / "Placentas" / case["numero_dossier"]
        candidate = case_dir / "lames"
        if candidate.is_dir():
            lames_path = str(candidate)

    # Collecter les photos
    photos_frais = []
    photos_tranches = []

    if photos_path and os.path.isdir(photos_path):
        pp = Path(photos_path)
        # Si c'est le dossier du cas lui-même, chercher photos/
        photos_sub = pp / "photos" if not (pp / "photos").is_dir() else pp / "photos"
        if photos_sub.is_dir():
            all_photos = _list_photos_in(str(photos_sub))
        else:
            all_photos = _list_photos_in(str(pp))

        # Séparer frais vs tranches par convention de nommage
        for ph in all_photos:
            name_lower = ph["name"].lower()
            if any(k in name_lower for k in ("tr_", "tranche", "lesion", "section")):
                photos_tranches.append(ph)
            else:
                photos_frais.append(ph)

    # Collecter les lames
    slides = []
    if lames_path and os.path.isdir(lames_path):
        slides = _list_slides_in(lames_path)

    # Construire l'appairage par ID (première partie du nom de fichier)
    organ_ids = set()
    photo_map_frais = {}
    photo_map_tranches = {}
    slide_map = {}

    for ph in photos_frais:
        key = ph["name"].split("_")[0].upper() if "_" in ph["name"] else ph["name"].upper()
        photo_map_frais.setdefault(key, []).append(ph)
        organ_ids.add(key)

    for ph in photos_tranches:
        key = ph["name"].split("_")[0].upper() if "_" in ph["name"] else ph["name"].upper()
        photo_map_tranches.setdefault(key, []).append(ph)
        organ_ids.add(key)

    for sl in slides:
        key = sl["name"].split("_")[0].upper() if "_" in sl["name"] else sl["name"].upper()
        slide_map.setdefault(key, []).append(sl)
        organ_ids.add(key)

    pairing_rows = []
    for organ_id in sorted(organ_ids):
        pairing_rows.append({
            "organ_id": organ_id,
            "photos_frais": photo_map_frais.get(organ_id, []),
            "photos_tranches": photo_map_tranches.get(organ_id, []),
            "slides": slide_map.get(organ_id, []),
        })

    return jsonify({
        "case_id": case_id,
        "numero_dossier": case["numero_dossier"],
        "pairing": pairing_rows,
        "stats": {
            "photos_frais": len(photos_frais),
            "photos_tranches": len(photos_tranches),
            "slides": len(slides),
        },
        "paths": {
            "photos": photos_path,
            "lames": lames_path,
        },
        "all_photos_frais": photos_frais,
        "all_photos_tranches": photos_tranches,
        "all_slides": slides,
    })


# ── API : Lumi integration (read-only) ──────────────────────────────────

@placenta_bp.route("/api/cases/<int:case_id>/lumi-slides")
def api_lumi_slides(case_id):
    case = pdb.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404
    from services.lumi import get_slides_for_case
    import db as foeto_db
    data = get_slides_for_case(case["numero_dossier"])
    viewer_url = foeto_db.get_setting("viewer_url", "")
    if not viewer_url:
        viewer_url = "/viewer"
    data["viewer_url"] = viewer_url
    return jsonify(data)


@placenta_bp.route("/api/lumi-counts")
def api_lumi_counts():
    from services.lumi import get_slide_counts
    numeros = request.args.get("numeros", "").split(",")
    numeros = [n.strip() for n in numeros if n.strip()]
    if not numeros:
        return jsonify({})
    return jsonify(get_slide_counts(numeros))


# ── Archive pipeline (proxy → Lumi registry) ──────────────────────────



# ── API : Sync dossier local ────────────────────────────────────────────

@placenta_bp.route("/api/sync", methods=["POST"])
def api_sync():
    """
    Scanne le dossier Placentas/ et importe les cas.

    Structure attendue :
      data_root/Placentas/
      ├── 25P9012/
      │   ├── macro_frais.json
      │   ├── tranches_section.json
      │   └── photos/
      └── 25P3456/
          └── ...
    """
    data = request.get_json() or {}
    scan_path = data.get("source_dir")

    if not scan_path:
        scan_path = str(_data_root() / "Placentas")

    source = Path(scan_path)
    if not source.is_dir():
        return jsonify({"error": t('errors.not_found')}), 400

    stats = {"scanned": 0, "imported": 0, "updated": 0, "photos": 0, "jsons": 0, "errors": 0}

    for entry in sorted(source.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        stats["scanned"] += 1

        case_id_str = entry.name
        existing = pdb.get_case_by_numero(case_id_str)

        # Detecter dossier lames
        lames_dir = entry / "lames"
        lames_path = str(lames_dir) if lames_dir.is_dir() else ""
        if not lames_path:
            from services.lumi import get_case_slides_dir
            lames_path = get_case_slides_dir(case_id_str) or ""

        update_data = {"dossier_photos_path": str(entry)}
        if lames_path:
            update_data["dossier_lames_path"] = lames_path

        if existing:
            if existing.get("statut") == "supprime":
                continue
            case_id = existing["id"]
            pdb.update_case(case_id, update_data)
            stats["updated"] += 1
        else:
            try:
                case_id = pdb.create_case({
                    "numero_dossier": case_id_str,
                    **update_data,
                })
                stats["imported"] += 1
            except (sqlite3.Error, ValueError):
                log.warning("Failed to create case for %s", case_id_str, exc_info=True)
                stats["errors"] += 1
                continue

        # Importer les JSON
        for f in sorted(entry.iterdir()):
            if f.is_file() and f.suffix.lower() == ".json":
                stem = f.stem
                if stem.startswith(case_id_str + "_"):
                    module_name = stem[len(case_id_str) + 1:]
                else:
                    module_name = stem
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        json_data = json.load(fh)
                    if module_name == "macro_frais":
                        pdb.import_from_macro_frais_json(json_data)
                    else:
                        pdb.save_module_data(case_id, module_name, json_data)
                    stats["jsons"] += 1
                except (OSError, json.JSONDecodeError):
                    log.warning("Failed to import JSON module %s", module_name, exc_info=True)
                    stats["errors"] += 1

        # Importer les photos
        photos_dir = entry / "photos"
        if photos_dir.is_dir():
            for ph in sorted(photos_dir.iterdir()):
                if ph.is_file() and ph.suffix.lower() in PHOTO_EXTENSIONS:
                    try:
                        sz = ph.stat().st_size
                        if sz >= 1024:
                            photo_key = ph.stem
                            pdb.save_photo(
                                case_id=case_id,
                                photo_key=photo_key,
                                filename=ph.name,
                                label=photo_key.replace("_", " ").title(),
                                module="macro_frais",
                                file_path=str(ph),
                                size_bytes=sz,
                            )
                            stats["photos"] += 1
                    except OSError:
                        log.debug("File stat error: %s", ph, exc_info=True)

    return jsonify({
        "status": "ok",
        "message": (
            f"Scan terminé : {stats['scanned']} dossier(s), "
            f"{stats['imported']} créé(s), {stats['updated']} mis à jour, "
            f"{stats['jsons']} JSON, {stats['photos']} photos"
        ),
        "stats": stats,
    })


# ── CR : sous-blueprint partagé ────────────────────────────────────────

from cr_shared_bp import make_cr_blueprint
import placenta_cr_templates as _pcr


def _build_placenta_context(case, modules_data, template_id=None):
    from services.lumi import get_annotations_for_case
    viewer_ann = get_annotations_for_case(case.get("numero_dossier", ""))
    return _pcr.build_cr_context(case, modules_data, viewer_annotations=viewer_ann)


def _llm_placenta(text, model):
    import llm_pipeline
    return llm_pipeline.pipeline_placenta_cr(text, model)


_placenta_cr_bp = make_cr_blueprint(
    entity="placenta",
    db_mod=pdb,
    cr_templates_mod=_pcr,
    llm_pipeline_fn=_llm_placenta,
    default_template="standard",
    build_context_fn=_build_placenta_context,
)

placenta_bp.register_blueprint(_placenta_cr_bp)


# ── API : Export JSON ─────────────────────────────────────────────────

@placenta_bp.route("/api/cases/<int:case_id>/export-json", methods=["POST"])
def api_export_json(case_id):
    """Exporte toutes les données d'un cas en JSON sur disque."""
    case = pdb.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    dossier = case["numero_dossier"]
    all_modules = pdb.get_all_modules(case_id)

    # Écrire chaque module
    for name, mod in all_modules.items():
        _save_json_to_disk(dossier, name, mod["data"])

    # Écrire un fichier récap admin
    case_dir = _data_root() / "Placentas" / dossier
    case_dir.mkdir(parents=True, exist_ok=True)
    admin_data = {k: v for k, v in case.items() if k not in ("modules", "photos")}
    admin_path = case_dir / f"{dossier}_admin.json"
    try:
        with open(admin_path, "w", encoding="utf-8") as f:
            json.dump(admin_data, f, ensure_ascii=False, indent=2)
    except OSError:
        log.debug("Failed to save admin data to disk: %s", admin_path, exc_info=True)

    return jsonify({
        "ok": True,
        "dossier": dossier,
        "modules_exported": list(all_modules.keys()),
        "path": str(case_dir),
    })

