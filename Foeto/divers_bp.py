# divers_bp.py — Blueprint Flask pour les cas divers (Curetage, Placenta Gémellaire)
# Pattern identique à placenta_bp.py

import json
import logging
import os
import sqlite3

from flask import Blueprint, jsonify, render_template, request

from divers_db import (
    init_table, save_cas, load_cas, list_cas, soft_delete_cas
)
from i18n import t

log = logging.getLogger(__name__)

# Le dossier templates_divers/ est dédié à ce blueprint
# (le dossier templates/ existant du FUSE mount n'est pas toujours accessible en écriture)
_template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates_divers')

divers_bp = Blueprint('divers', __name__,
                       url_prefix='/divers',
                       template_folder=_template_dir)


# ─── Auth : protéger toutes les routes sauf soumission PWA ────────
from auth_bp import make_before_request

divers_bp.before_request(make_before_request(
    api_prefix="/divers/api/",
    exempt_paths={"/divers/api/save"},
    check_mutations=False,
))


# ─── Initialisation ───────────────────────────────────────────────
@divers_bp.before_app_request
def _ensure_table():
    """Crée la table cas_divers au premier appel (idempotent)."""
    if not getattr(divers_bp, '_table_ready', False):
        try:
            init_table()
            divers_bp._table_ready = True
        except sqlite3.Error as e:
            log.warning("Erreur init table cas_divers: %s", e)


# ─── Pages HTML ───────────────────────────────────────────────────

@divers_bp.route('/')
def index():
    """Page d'accueil Cas Divers — choix du template + liste des cas récents."""
    cas_recents = []
    try:
        cas_recents = list_cas(limit=20)
    except sqlite3.Error:
        log.warning("Échec chargement cas récents", exc_info=True)
    return render_template('divers_index.html', cas_recents=cas_recents)


@divers_bp.route('/curetage')
def curetage():
    """Sert le formulaire curetage."""
    return render_template('divers_curetage.html')


@divers_bp.route('/gemellaire')
def gemellaire():
    """Sert le formulaire placenta gémellaire."""
    return render_template('divers_gemellaire.html')


# ─── API REST ─────────────────────────────────────────────────────

@divers_bp.route('/api/save', methods=['POST'])
def api_save():
    """
    Sauvegarde (insert ou update) un cas divers.
    Body JSON attendu :
    {
        "type_cas": "curetage" | "gemellaire",
        "dossier": "...",
        "date_prel": "2025-04-05",
        "operateur": "...",
        "ag_sa": 22,
        "ag_j": 3,
        "indication": "...",
        "etat": "frais",
        "form_data": { ... },
        "cr_text": "...",
        "id": 42              // optionnel, pour update
    }
    Retourne : { "id": 42, "status": "ok" }
    """
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "JSON body requis"}), 400

        # Validation type_cas
        type_cas = data.get('type_cas', '')
        if type_cas not in ('curetage', 'gemellaire'):
            return jsonify({"error": f"type_cas invalide : {type_cas}"}), 400

        # Sanitisation basique du form_data
        form_data = data.get('form_data', {})
        if isinstance(form_data, str):
            try:
                form_data = json.loads(form_data)
            except json.JSONDecodeError:
                form_data = {}
            data['form_data'] = form_data

        # Conversion types numériques
        for field in ('ag_sa', 'ag_j'):
            val = data.get(field)
            if val is not None:
                try:
                    data[field] = int(val)
                except (ValueError, TypeError):
                    data[field] = None

        cas_id = save_cas(data)
        return jsonify({"id": cas_id, "status": "ok"})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (sqlite3.Error, OSError) as e:
        return jsonify({"error": f"Erreur serveur : {str(e)}"}), 500


@divers_bp.route('/api/load/<int:cas_id>')
def api_load(cas_id):
    """Charge un cas existant par son id."""
    try:
        cas = load_cas(cas_id)
        if cas is None:
            return jsonify({"error": "Cas non trouvé"}), 404
        return jsonify(cas)
    except (sqlite3.Error, ValueError) as e:
        return jsonify({"error": str(e)}), 500


@divers_bp.route('/api/list')
def api_list():
    """
    Liste des cas avec filtres optionnels.
    Query params: type_cas, limit, offset
    """
    try:
        type_cas = request.args.get('type_cas')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        results = list_cas(type_cas=type_cas, limit=limit, offset=offset)
        return jsonify({"cas": results, "count": len(results)})
    except (sqlite3.Error, ValueError) as e:
        return jsonify({"error": str(e)}), 500


@divers_bp.route('/api/delete/<int:cas_id>', methods=['POST'])
def api_delete(cas_id):
    """Soft-delete d'un cas."""
    try:
        # Vérifier que le cas existe
        cas = load_cas(cas_id)
        if cas is None:
            return jsonify({"error": "Cas non trouvé"}), 404

        soft_delete_cas(cas_id)
        return jsonify({"status": "ok", "id": cas_id})
    except (sqlite3.Error, ValueError) as e:
        return jsonify({"error": str(e)}), 500


@divers_bp.route('/api/cr/<int:cas_id>', methods=['POST'])
def api_cr(cas_id):
    """
    Phase 2 — Soumet le CR au pipeline LLM pour amélioration.
    Pour la phase 1, retourne simplement le CR existant.
    """
    try:
        cas = load_cas(cas_id)
        if cas is None:
            return jsonify({"error": "Cas non trouvé"}), 404

        cr_text = cas.get('cr_text', '')

        # Phase 2 : intégrer le pipeline LLM ici
        # from llm_pipeline import process_cr
        # cr_improved = process_cr(cr_text, cas.get('form_data', {}))
        # return jsonify({"cr_text": cr_improved, "status": "ok"})

        # Phase 1 : retourner le CR tel quel
        return jsonify({"cr_text": cr_text, "status": "ok", "note": "Pipeline LLM non actif (Phase 1)"})

    except (sqlite3.Error, ValueError) as e:
        return jsonify({"error": str(e)}), 500
