"""FoetoPath — Sous-blueprint Admin CR (monté sous /admin).

Uses the shared CR blueprint factory + foetus-specific routes (histo, concat).
"""

import logging

from flask import Blueprint, jsonify, request

import db
from i18n import t
from cr_shared_bp import make_cr_blueprint

log = logging.getLogger(__name__)


# ── Build context callback for foetus ───────────────────────────────────

def _build_foetus_context(case, modules_data, template_id=None):
    import cr_templates
    computed = modules_data.get("computed_biometrics", {})
    if template_id == "neuropath":
        return cr_templates.build_neuropath_context(case, modules_data)
    elif template_id == "radio":
        return cr_templates.build_radio_context(case, modules_data)
    else:
        return cr_templates.build_cr_context(case, modules_data, computed)


def _llm_foetus(text, model):
    import llm_pipeline
    return llm_pipeline.pipeline_foetus_cr(text, model)


# ── Shared CR blueprint (templates, generate, user-tpl, docs, LLM) ──

import cr_templates as _cr_tpl

admin_cr_bp = make_cr_blueprint(
    entity="foetus",
    db_mod=db,
    cr_templates_mod=_cr_tpl,
    llm_pipeline_fn=_llm_foetus,
    default_template="soffoet",
    build_context_fn=_build_foetus_context,
)


# ── Foetus-specific: histologie ─────────────────────────────────────────

@admin_cr_bp.route("/api/cases/<int:case_id>/histo", methods=["GET"])
def api_histo_get(case_id):
    """Retourne les données histologiques d'un cas."""
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404
    histo = db.get_module_data(case_id, "histologie") or {}
    return jsonify({"histo": histo})


@admin_cr_bp.route("/api/cases/<int:case_id>/histo", methods=["PUT"])
def api_histo_save(case_id):
    """Sauvegarde les données histologiques d'un cas."""
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404
    body = request.get_json() or {}
    db.save_module_data(case_id, "histologie", body)
    return jsonify({"ok": True})
