"""FoetoPath — Shared CR Blueprint Factory.

Creates a CR blueprint parameterized by entity type (foetus/placenta).
Provides: template listing, CR generation, user templates CRUD,
generated docs CRUD, LLM reformulation, template variables palette.
"""

import logging

from flask import Blueprint, jsonify, request
from markupsafe import escape as html_escape

from cr_helpers import render_user_template
from i18n import t

log = logging.getLogger(__name__)


def _cr_text_to_html(text: str) -> str:
    """Convert CR template output (plain text + embedded HTML) to display HTML."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped and i + 1 < len(lines):
            next_stripped = lines[i + 1].strip()
            if next_stripped and len(next_stripped) >= 3 and all(c == "=" for c in next_stripped):
                out.append(f'<h2 style="margin:18px 0 6px;font-size:15px;color:var(--accent)">{html_escape(stripped)}</h2>')
                i += 2
                continue
            if next_stripped and len(next_stripped) >= 3 and all(c == "-" for c in next_stripped):
                out.append(f'<h3 style="margin:14px 0 4px;font-size:13px;color:var(--text)">{html_escape(stripped)}</h3>')
                i += 2
                continue

        if stripped == "---":
            out.append("<hr style='margin:12px 0;border-color:var(--border)'>")
            i += 1
            continue

        if stripped.startswith("<"):
            out.append(line)
            i += 1
            continue

        if not stripped:
            out.append("<br>")
        else:
            out.append(str(html_escape(line)) + "<br>")
        i += 1

    return "\n".join(out)


def make_cr_blueprint(
    entity: str,
    db_mod,
    cr_templates_mod,
    llm_pipeline_fn,
    default_template: str,
    build_context_fn,
):
    """Create a CR blueprint for the given entity.

    Args:
        entity: 'foetus' or 'placenta'
        db_mod: DB module (db or placenta_db) — must have get_case,
                get_all_modules, save_module_data, get_module_data,
                list_cr_templates, get_cr_template, create_cr_template,
                update_cr_template, delete_cr_template, duplicate_cr_template,
                save_generated_doc, list_generated_docs, get_generated_doc,
                delete_generated_doc
        cr_templates_mod: module with get_available_templates, render_cr,
                          get_all_versions_info, get_template_changelog,
                          cr_helpers
        llm_pipeline_fn: callable(text, model) -> result dict
        default_template: default template ID ('soffoet' or 'standard')
        build_context_fn: callable(case, modules_data, **kw) -> context dict
    """
    bp = Blueprint(f"cr_{entity}", __name__)

    # ── File templates ──────────────────────────────────────────────

    @bp.route("/api/cr/templates", methods=["GET"])
    def api_cr_templates():
        return jsonify({"templates": cr_templates_mod.get_available_templates()})

    @bp.route("/api/cr/templates/versions", methods=["GET"])
    def api_cr_template_versions():
        return jsonify(cr_templates_mod.get_all_versions_info())

    @bp.route("/api/cr/templates/<template_id>/changelog", methods=["GET"])
    def api_cr_template_changelog(template_id):
        changelog = cr_templates_mod.get_template_changelog(template_id)
        if not changelog:
            return jsonify({"error": t('errors.template_not_found', template_id=template_id)}), 404
        return jsonify({"template_id": template_id, "changelog": changelog})

    # ── CR generation ───────────────────────────────────────────────

    @bp.route("/api/cases/<int:case_id>/cr/generate", methods=["POST"])
    def api_cr_generate(case_id):
        case = db_mod.get_case(case_id)
        if not case:
            return jsonify({"error": t('errors.case_not_found')}), 404

        body = request.get_json() or {}
        template_id = body.get("template_id", default_template)

        all_modules = db_mod.get_all_modules(case_id)
        modules_data = {name: mod["data"] for name, mod in all_modules.items()}

        try:
            context = build_context_fn(case, modules_data, template_id=template_id)

            from services.lumi import (
                build_labellisation_micro_text, build_labellisation_table,
                build_composite_micro_cr,
            )
            numero = case.get("numero_dossier", "")
            context["labellisation_micro_text"] = build_labellisation_micro_text(numero)
            context["labellisation_table"] = build_labellisation_table(numero)
            context["composite_micro_text"], context["composite_conclusion_items"] = \
                build_composite_micro_cr(numero)

            cr_text = cr_templates_mod.render_cr(template_id, context)
        except Exception as exc:
            log.exception("CR render failed for case %s, template %s", case_id, template_id)
            return jsonify({"error": f"Erreur de rendu : {exc}"}), 500

        try:
            cr_html = _cr_text_to_html(cr_text)
        except Exception:
            log.exception("CR text→html conversion failed for case %s", case_id)
            cr_html = str(html_escape(cr_text)).replace("\n", "<br>")

        db_mod.save_module_data(case_id, "last_cr", {
            "template_id": template_id,
            "text": cr_text,
            "html": cr_html,
        })

        doc_id = db_mod.save_generated_doc(case_id, template_id, cr_html, cr_text)

        return jsonify({
            "template_id": template_id,
            "text": cr_text,
            "html": cr_html,
            "doc_id": doc_id,
        })

    # ── LLM reformulation ───────────────────────────────────────────

    @bp.route("/api/cases/<int:case_id>/cr/llm", methods=["POST"])
    def api_cr_llm(case_id):
        case = db_mod.get_case(case_id)
        if not case:
            return jsonify({"error": t('errors.case_not_found')}), 404

        body = request.get_json() or {}
        source_text = body.get("text", "")

        if not source_text:
            last_cr = db_mod.get_module_data(case_id, "last_cr")
            if last_cr:
                source_text = last_cr.get("text", "")
        if not source_text:
            return jsonify({"error": t('errors.no_report')}), 400

        model = body.get("model") or None

        try:
            import llm_pipeline
            result = llm_pipeline_fn(source_text, model)

            db_mod.save_module_data(case_id, "last_cr_llm", {
                "text": result["generated_text"],
                "thinking": result.get("thinking", ""),
                "model": result.get("model", ""),
                "tokens": result.get("tokens", 0),
                "elapsed_s": result.get("elapsed_s", 0),
            })

            return jsonify(result)
        except RuntimeError as e:
            log.warning("LLM CR %s — erreur: %s", entity, e)
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            log.error("LLM CR %s — erreur inattendue: %s", entity, e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    # ── User templates CRUD ─────────────────────────────────────────

    @bp.route("/api/cr/user-templates", methods=["GET"])
    def api_cr_user_templates():
        return jsonify({"templates": db_mod.list_cr_templates()})

    @bp.route("/api/cr/user-templates", methods=["POST"])
    def api_cr_create_template():
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        ttype = data.get("type", "custom")
        content = data.get("content_jinja2", "")
        if not name:
            return jsonify({"error": "Nom requis"}), 400
        try:
            tid = db_mod.create_cr_template(name, ttype, content)
            return jsonify({"ok": True, "id": tid})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @bp.route("/api/cr/user-templates/<int:template_id>", methods=["PUT"])
    def api_cr_update_template(template_id):
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        ttype = data.get("type", "custom")
        content = data.get("content_jinja2", "")
        if not name:
            return jsonify({"error": "Nom requis"}), 400
        db_mod.update_cr_template(template_id, name, ttype, content)
        return jsonify({"ok": True})

    @bp.route("/api/cr/user-templates/<int:template_id>", methods=["DELETE"])
    def api_cr_delete_template(template_id):
        db_mod.delete_cr_template(template_id)
        return jsonify({"ok": True})

    @bp.route("/api/cr/user-templates/<int:template_id>/duplicate", methods=["POST"])
    def api_cr_duplicate_template(template_id):
        new_id = db_mod.duplicate_cr_template(template_id)
        if new_id is None:
            return jsonify({"error": "Template introuvable"}), 404
        return jsonify({"ok": True, "id": new_id})

    # ── Generate from user template ─────────────────────────────────

    @bp.route("/api/cases/<int:case_id>/cr/generate-user", methods=["POST"])
    def api_cr_generate_user(case_id):
        case = db_mod.get_case(case_id)
        if not case:
            return jsonify({"error": t('errors.case_not_found')}), 404

        body = request.get_json() or {}
        template_id = body.get("template_id")
        if not template_id:
            return jsonify({"error": "template_id requis"}), 400

        tpl = db_mod.get_cr_template(template_id)
        if not tpl:
            return jsonify({"error": "Template introuvable"}), 404

        all_modules = db_mod.get_all_modules(case_id)
        modules_data = {name: mod["data"] for name, mod in all_modules.items()}
        context = build_context_fn(case, modules_data)

        from services.lumi import (
            build_labellisation_micro_text, build_labellisation_table,
            build_composite_micro_cr,
        )
        numero = case.get("numero_dossier", "")
        context["labellisation_micro_text"] = build_labellisation_micro_text(numero)
        context["labellisation_table"] = build_labellisation_table(numero)
        context["composite_micro_text"], context["composite_conclusion_items"] = \
            build_composite_micro_cr(numero)

        helpers = cr_templates_mod.cr_helpers(context)
        html, text = render_user_template(tpl["content_jinja2"], {**context, **helpers})

        doc_id = db_mod.save_generated_doc(case_id, template_id, html, text)

        return jsonify({"ok": True, "doc_id": doc_id, "html": html, "text": text})

    # ── Generated docs CRUD ─────────────────────────────────────────

    @bp.route("/api/cases/<int:case_id>/cr/docs", methods=["GET"])
    def api_cr_docs(case_id):
        return jsonify({"docs": db_mod.list_generated_docs(case_id)})

    @bp.route("/api/cr/docs/<int:doc_id>", methods=["GET"])
    def api_cr_doc(doc_id):
        doc = db_mod.get_generated_doc(doc_id)
        if not doc:
            return jsonify({"error": "Document introuvable"}), 404
        return jsonify(doc)

    @bp.route("/api/cr/docs/<int:doc_id>", methods=["DELETE"])
    def api_cr_delete_doc(doc_id):
        db_mod.delete_generated_doc(doc_id)
        return jsonify({"ok": True})

    # ── Template variables palette ──────────────────────────────────

    @bp.route("/api/cr/template-variables", methods=["GET"])
    def api_cr_template_variables():
        if entity == "placenta":
            from cr_template_vars import TEMPLATE_VARIABLES_PLACENTA
            return jsonify({"variables": TEMPLATE_VARIABLES_PLACENTA})
        from cr_template_vars import TEMPLATE_VARIABLES
        return jsonify({"variables": TEMPLATE_VARIABLES})

    return bp
