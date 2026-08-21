"""
Factory CRUD pour les blueprints admin et placenta.

Enregistre 7 routes CRUD standard + 1 route users/list sur un blueprint :
  GET    /api/cases                              → list
  POST   /api/cases                              → create (merge si existe)
  GET    /api/cases/<case_id>                    → detail
  PUT    /api/cases/<case_id>                    → update
  DELETE /api/cases/<case_id>                    → delete
  GET    /api/cases/<case_id>/modules/<name>     → get module
  PUT    /api/cases/<case_id>/modules/<name>     → save module
  GET    /api/users/list                         → list active users
"""

import logging
import sqlite3

from flask import jsonify, request, session

from i18n import t

log = logging.getLogger(__name__)


def register_crud_routes(bp, db_mod, known_modules, hooks=None):
    """
    Enregistre les routes CRUD standard sur un blueprint existant.

    Args:
        bp: Blueprint Flask
        db_mod: module DB (db ou placenta_db) — doit exposer :
            list_cases, create_case, get_case, get_case_by_numero,
            update_case, delete_case, get_all_modules,
            get_module_data, save_module_data
        known_modules: set de noms de modules autorisés
        hooks: dict optionnel de callbacks :
            enrich_list_item(case)       — enrichir chaque cas dans la liste
            enrich_detail(case, case_id) — enrichir le détail d'un cas
            list_kwargs(request)         — kwargs supplémentaires pour list_cases
            prepare_create(data)         — modifier data avant create
            prepare_update(data)         — modifier data avant update
            on_create(case_id, data, merged: bool)
            on_update(case_id, data)
            on_delete(case_id)
            on_save_module(case_id, module_name)
    """
    hooks = hooks or {}

    @bp.route("/api/cases", methods=["GET"])
    def api_list_cases():
        kwargs = {
            "statut": request.args.get("statut"),
            "search": request.args.get("q"),
        }
        extra_fn = hooks.get("list_kwargs")
        if extra_fn:
            kwargs.update(extra_fn(request))
        cases = db_mod.list_cases(**{k: v for k, v in kwargs.items() if v is not None})

        for c in cases:
            modules = db_mod.get_all_modules(c["id"])
            c["module_count"] = len(modules)
            c["modules_filled"] = list(modules.keys())
            enrich = hooks.get("enrich_list_item")
            if enrich:
                enrich(c)

        return jsonify({"cases": cases, "total": len(cases)})

    @bp.route("/api/cases", methods=["POST"])
    def api_create_case():
        data = request.get_json()
        if not data or not data.get("numero_dossier"):
            return jsonify({"error": t('errors.dossier_required')}), 400

        prepare = hooks.get("prepare_create")
        if prepare:
            prepare(data)

        existing = db_mod.get_case_by_numero(data["numero_dossier"])
        if existing:
            db_mod.update_case(existing["id"], data)
            on_create = hooks.get("on_create")
            if on_create:
                on_create(existing["id"], data, True)
            return jsonify({"id": existing["id"], "message": t('cases.merged'), "merged": True}), 200

        try:
            case_id = db_mod.create_case(data)
            on_create = hooks.get("on_create")
            if on_create:
                on_create(case_id, data, False)
            return jsonify({"id": case_id, "message": t('cases.created')}), 201
        except (sqlite3.Error, ValueError) as e:
            log.exception("Erreur création de cas")
            return jsonify({"error": t('errors.internal')}), 500

    @bp.route("/api/cases/<int:case_id>", methods=["GET"])
    def api_get_case(case_id):
        case = db_mod.get_case(case_id)
        if not case:
            return jsonify({"error": t('errors.case_not_found')}), 404

        case["modules"] = db_mod.get_all_modules(case_id)
        enrich = hooks.get("enrich_detail")
        if enrich:
            enrich(case, case_id)

        return jsonify(case)

    @bp.route("/api/cases/<int:case_id>", methods=["PUT"])
    def api_update_case(case_id):
        data = request.get_json()
        if not data:
            return jsonify({"error": t('errors.data_required')}), 400

        case = db_mod.get_case(case_id)
        if not case:
            return jsonify({"error": t('errors.case_not_found')}), 404

        prepare = hooks.get("prepare_update")
        if prepare:
            prepare(data)

        db_mod.update_case(case_id, data)
        on_update = hooks.get("on_update")
        if on_update:
            on_update(case_id, data)

        return jsonify({"message": t('cases.updated'), "id": case_id})

    @bp.route("/api/cases/<int:case_id>", methods=["DELETE"])
    def api_delete_case(case_id):
        if db_mod.delete_case(case_id):
            on_delete = hooks.get("on_delete")
            if on_delete:
                on_delete(case_id)
            return jsonify({"message": t('cases.deleted')})
        return jsonify({"error": t('errors.case_not_found')}), 404

    @bp.route("/api/cases/<int:case_id>/modules/<module_name>", methods=["GET"])
    def api_get_module(case_id, module_name):
        if module_name not in known_modules:
            return jsonify({"error": t('errors.unknown_module')}), 400
        data = db_mod.get_module_data(case_id, module_name)
        if data is None:
            return jsonify({"error": t('errors.module_not_found')}), 404
        return jsonify({"module": module_name, "data": data})

    @bp.route("/api/cases/<int:case_id>/modules/<module_name>", methods=["PUT"])
    def api_save_module(case_id, module_name):
        if module_name not in known_modules:
            return jsonify({"error": t('errors.unknown_module')}), 400
        data = request.get_json()
        if not data:
            return jsonify({"error": t('errors.data_required')}), 400

        case = db_mod.get_case(case_id)
        if not case:
            return jsonify({"error": t('errors.case_not_found')}), 404

        db_mod.save_module_data(case_id, module_name, data)
        on_save = hooks.get("on_save_module")
        if on_save:
            on_save(case_id, module_name)

        return jsonify({"message": f"Module {module_name} sauvegardé"})

    @bp.route("/api/users/list", methods=["GET"])
    def api_users_list():
        import auth_db
        users = auth_db.list_users()
        return jsonify({
            "users": [
                {"id": u["id"], "username": u["username"],
                 "display_name": u.get("display_name", ""), "role": u["role"]}
                for u in users if u.get("active", 1)
            ]
        })
