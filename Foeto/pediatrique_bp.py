"""
FoetoPath — Blueprint Pédiatrique.

Routes pour :
  - Page admin pédiatrique (CRUD via crud_factory)
  - Détails pédiatriques
  - Calcul biométrique Molina 2019

Utilise pediatrique_db (DB indépendante pediatrique.db).
"""

import json
import logging

from flask import Blueprint, jsonify, render_template, request, session

log = logging.getLogger(__name__)

import pediatrique_db as ped_db
from auth_bp import login_required, make_before_request
from config import KNOWN_MODULES_PEDIATRIQUE
from crud_factory import register_crud_routes

pediatrique_bp = Blueprint(
    "pediatrique",
    __name__,
    template_folder="templates",
    url_prefix="/pediatrique",
)

pediatrique_bp.before_request(make_before_request(
    api_prefix="/pediatrique/api/",
    exempt_paths=set(),
    check_mutations=True,
    redirect_on_unauth=False,
))


# ── Page admin ─────────────────────────────────────────────────────────────

@pediatrique_bp.route("/")
def admin_pediatrique():
    return render_template("admin_pediatrique.html")


# ── CRUD via factory (list/create/detail/update/delete/modules) ────────────

def _prepare_create(data):
    username = session.get("username", "")
    if username:
        data.setdefault("created_by", username)
        data["modified_by"] = username


register_crud_routes(pediatrique_bp, ped_db, KNOWN_MODULES_PEDIATRIQUE, hooks={
    "prepare_create": _prepare_create,
})


# ── Pediatric details ─────────────────────────────────────────────────────

@pediatrique_bp.route("/api/cases/<int:case_id>/pediatric-details", methods=["GET"])
def api_get_ped_details(case_id):
    details = ped_db.get_pediatric_details(case_id)
    return jsonify({"details": details or {}})


@pediatrique_bp.route("/api/cases/<int:case_id>/pediatric-details", methods=["PUT"])
def api_save_ped_details(case_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400
    ped_db.save_pediatric_details(case_id, data)
    return jsonify({"ok": True})


# ── Biométries pédiatriques (Molina 2019) ──────────────────────────────────

@pediatrique_bp.route("/api/cases/<int:case_id>/compute-pediatric", methods=["POST"])
def api_compute_pediatric(case_id):
    case = ped_db.get_case(case_id)
    if not case:
        return jsonify({"error": "case not found"}), 404

    ped = ped_db.get_pediatric_details(case_id) or {}
    modules = ped_db.get_all_modules(case_id)
    autopsie_raw = (modules.get("macro_autopsie") or {}).get("data", {})
    # PWA saves {data: {masse_*}}, unwrap if nested
    autopsie = autopsie_raw.get("data", autopsie_raw) if isinstance(autopsie_raw.get("data"), dict) else autopsie_raw

    age_days = ped.get("age_deces_jours")
    poids_g = ped.get("poids_deces_g")
    taille_cm = ped.get("taille_deces_cm")
    gender = case.get("sexe", "I")

    organes = {}
    for key in ("cerveau", "coeur", "foie", "rate",
                "poumon_d", "poumon_g", "rein_d", "rein_g"):
        val = autopsie.get(f"masse_{key}") or autopsie.get(key, {}).get("masse")
        if val is not None:
            organes[key] = val

    try:
        from biometrics_pediatric import compute_pediatric_all
        results = compute_pediatric_all(age_days, gender, poids_g, taille_cm, organes)
    except Exception as e:
        log.exception("Pediatric biometry computation failed")
        return jsonify({"error": str(e)}), 500

    ped_db.save_module_data(case_id, "computed_biometrics", results)
    return jsonify({"ok": True, "results": results})
