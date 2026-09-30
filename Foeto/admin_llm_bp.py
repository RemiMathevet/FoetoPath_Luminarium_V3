"""FoetoPath — Sous-blueprint Admin LLM (monté sous /admin). Backend: Magos."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request

import db
from i18n import t

log = logging.getLogger(__name__)

admin_llm_bp = Blueprint("admin_llm", __name__)


# ── Calculs biométriques ──────────────────────────────────────────────────

@admin_llm_bp.route("/api/cases/<int:case_id>/compute", methods=["POST"])
def api_compute(case_id):
    """
    Lance les calculs biométriques pour un cas.
    Lit les modules macro_frais et macro_autopsie, calcule DS + ratios,
    sauvegarde les résultats dans le module 'computed_biometrics',
    et retourne le rapport textuel Jinja2.
    """
    import biometrics

    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    macro_frais = db.get_module_data(case_id, "macro_frais")
    macro_autopsie = db.get_module_data(case_id, "macro_autopsie")

    if not macro_frais and not macro_autopsie:
        return jsonify({"error": t('errors.no_macro_data')}), 400

    terme = None
    maceration = 0

    if macro_frais:
        terme_obj = macro_frais.get("terme")
        if isinstance(terme_obj, dict):
            terme = terme_obj.get("sa")
        elif isinstance(terme_obj, (int, float)):
            terme = int(terme_obj)

        if not terme:
            bio = macro_frais.get("biometries", macro_frais.get("biometrie", {}))
            terme = bio.get("terme_sa") or bio.get("terme")

        mac_obj = macro_frais.get("maceration")
        if isinstance(mac_obj, dict):
            maceration = mac_obj.get("maroun_score", 0) or 0
        elif isinstance(mac_obj, (int, float)):
            maceration = int(mac_obj)

    if not terme and case.get("terme_issue"):
        m = re.match(r"(\d+)", str(case["terme_issue"]))
        if m:
            terme = int(m.group(1))

    body = request.get_json() or {}
    # Terme déterminé : body > DB module > terme clinique
    td = db.get_module_data(case_id, "terme_determine")
    terme = body.get("terme_sa") or (td.get("sa") if td else None) or terme
    maceration = body.get("maceration_grade", maceration)

    if not terme:
        return jsonify({"error": t('errors.terme_not_found')}), 400

    terme = int(terme)

    results = biometrics.compute_all(
        terme_sa=terme,
        macro_frais=macro_frais,
        macro_autopsie=macro_autopsie,
        maceration_grade=maceration,
    )

    report_text = biometrics.render_report(results)

    db.save_module_data(case_id, "computed_biometrics", {
        "results": results,
        "report_text": report_text,
    })

    return jsonify({
        "results": results,
        "report_text": report_text,
    })


# ── Save module data ──────────────────────────────────────────────────────

@admin_llm_bp.route("/api/cases/<int:case_id>/modules/<module_name>", methods=["PUT"])
def api_save_module(case_id, module_name):
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    data = request.get_json()
    if data is None:
        return jsonify({"error": "No data"}), 400
    db.save_module_data(case_id, module_name, data)
    return jsonify({"ok": True})


# ── Aide diagnostique (matrice de convergence) ───────────────────────────

@admin_llm_bp.route("/api/cases/<int:case_id>/aide-diag", methods=["POST"])
def api_aide_diag(case_id):
    """Collecte HPO + alertes + texte, appelle la matrice de convergence."""
    from concat.hpo import _extract_hpo_findings, _collect_constatations_libres_recursive

    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": "Cas non trouvé"}), 404

    modules = db.get_all_modules(case_id)

    # 1. Collect HPO from all modules
    all_hpo = []
    seen_codes = set()
    for mod_name, mod_data in modules.items():
        if not isinstance(mod_data, dict):
            continue
        for f in _extract_hpo_findings(mod_data):
            if f["code"] not in seen_codes:
                all_hpo.append(f)
                seen_codes.add(f["code"])

    # 2. Collect free text (constatations without HPO match)
    free_texts = []
    for mod_name, mod_data in modules.items():
        if not isinstance(mod_data, dict):
            continue
        free_texts.extend(_collect_constatations_libres_recursive(mod_data))

    # 3. Biometric alerts
    computed = modules.get("computed_biometrics", {})
    results_bio = computed.get("results", {}) if isinstance(computed, dict) else {}
    alertes = results_bio.get("alertes", [])

    # 4. Case-level text fields
    indication = case.get("indication_examen", "") or ""
    contexte = case.get("contexte_clinique", "") or ""

    # 5. Build clinical text for matrix query
    parts = []
    if indication:
        parts.append(indication)
    if contexte:
        parts.append(contexte)
    if all_hpo:
        parts.append("Signes HPO: " + ", ".join(f.get("term", f["code"]) for f in all_hpo))
    if alertes:
        parts.append("Alertes biométriques: " + "; ".join(alertes))
    if free_texts:
        parts.append("Constatations: " + "; ".join(t.get("constatation", str(t)) if isinstance(t, dict) else str(t) for t in free_texts[:20]))

    clinical_text = "\n".join(parts)

    # 6. Query convergence matrix
    hypotheses = []
    matrix_error = None
    if clinical_text.strip():
        try:
            from services.convergence import query as matrix_query
            hypotheses = matrix_query(clinical_text, top_k=15)
        except Exception as e:
            log.exception("Convergence matrix error")
            matrix_error = str(e)

    # 7. Persist and return
    result = {
        "hpo": all_hpo,
        "free_texts": free_texts[:30],
        "alertes": alertes,
        "indication": indication,
        "contexte": contexte,
        "clinical_text": clinical_text,
        "hypotheses": hypotheses,
        "matrix_error": matrix_error,
    }
    db.save_module_data(case_id, "aide_diag", result)
    return jsonify(result)


# ── LLM (Magos) — Statut, listing modèles, génération ────────────────────

@admin_llm_bp.route("/api/llm/status", methods=["POST"])
def api_llm_status():
    """
    Vérifie si Magos tourne et liste les modèles disponibles.
    Accepte {"url": "http://..."} dans le body pour spécifier/changer l'URL.
    """
    from services.magos import check_magos_status

    body = request.get_json(silent=True) or {}
    url_override = (body.get("url") or "").strip()
    if url_override:
        if not url_override.startswith(("http://", "https://")):
            url_override = "http://" + url_override
        url_override = url_override.rstrip("/")
        db.set_setting("magos_url", url_override)
        log.info("Magos URL mise à jour → %s", url_override)

    try:
        result = check_magos_status()
        return jsonify(result)
    except Exception as e:
        log.error("Magos status — erreur: %s", e, exc_info=True)
        return jsonify({
            "error": str(e),
            "running": False,
            "models": [],
        }), 500


@admin_llm_bp.route("/api/cases/<int:case_id>/llm-biometrics", methods=["POST"])
def api_llm_biometrics(case_id):
    """
    Envoie le rapport biométrique à Magos pour reformulation
    en texte médical rédigé.
    """
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    computed = db.get_module_data(case_id, "computed_biometrics")
    if not computed or not computed.get("report_text"):
        return jsonify({"error": t('errors.no_report')}), 400

    report_text = computed["report_text"]
    body = request.get_json() or {}
    model = body.get("model") or db.get_setting("llm_model", "Qwen3.6-35B")

    try:
        import llm_pipeline
        result = llm_pipeline.pipeline_biometrics(report_text, model)

        computed["llm_text"] = result["generated_text"]
        computed["llm_model"] = model
        db.save_module_data(case_id, "computed_biometrics", computed)

        return jsonify(result)
    except RuntimeError as e:
        log.warning("LLM biometrics — erreur: %s", e)
        return jsonify({"error": str(e)}), 502


# ── Foekinator (diagnostic bayésien) ─────────────────────────────────────

@admin_llm_bp.route("/api/foekinator/databases", methods=["GET"])
def api_foekinator_databases():
    """Liste les bases de données Foekinator disponibles (fichiers JSON)."""
    foek_dir = Path(__file__).parent / "Foekinator"
    databases = []
    if foek_dir.is_dir():
        for p in sorted(foek_dir.iterdir()):
            if p.suffix.lower() == ".json" and p.is_file():
                try:
                    import json as _json
                    data = _json.loads(p.read_text(encoding="utf-8"))
                    meta = data.get("_meta", {})
                    databases.append({
                        "id": p.stem,
                        "filename": p.name,
                        "name": meta.get("name", p.stem.replace("_", " ").title()),
                        "version": meta.get("version", "?"),
                        "diseases_count": meta.get("diseases_count", len(data.get("diseases", []))),
                        "hpo_terms_count": meta.get("hpo_terms_count", len(data.get("hpo_terms", {}))),
                    })
                except (OSError, json.JSONDecodeError, ValueError):
                    log.debug("Failed to load database metadata", exc_info=True)
                    databases.append({"id": p.stem, "filename": p.name, "name": p.stem, "version": "?", "diseases_count": 0, "hpo_terms_count": 0})
    return jsonify({"databases": databases})


@admin_llm_bp.route("/api/foekinator/load", methods=["GET"])
def api_foekinator_load():
    """Charge une base de données Foekinator par son ID (stem du fichier)."""
    db_id = request.args.get("id", "").strip()
    if not db_id:
        return jsonify({"error": t('errors.data_required')}), 400

    foek_dir = (Path(__file__).parent / "Foekinator").resolve()
    filepath = (foek_dir / (db_id + ".json")).resolve()
    if not filepath.is_relative_to(foek_dir) or not filepath.is_file():
        return jsonify({"error": t('errors.db_not_found')}), 404

    import json as _json
    data = _json.loads(filepath.read_text(encoding="utf-8"))
    return jsonify(data)


# ── Microscopie (grilles de lecture) ──────────────────────────────────────

@admin_llm_bp.route("/api/micro/templates", methods=["GET"])
def api_micro_templates():
    """Liste les templates de grilles de lecture microscopie."""
    templates_dir = Path(__file__).parent / "templates" / "micro"
    templates = []
    if templates_dir.is_dir():
        for p in sorted(templates_dir.iterdir()):
            if p.suffix.lower() == ".json" and p.is_file():
                try:
                    import json as _json
                    data = _json.loads(p.read_text(encoding="utf-8"))
                    templates.append({
                        "id": p.stem,
                        "name": data.get("name", p.stem),
                        "description": data.get("description", ""),
                        "icon": data.get("icon", "&#128203;"),
                    })
                except (OSError, json.JSONDecodeError, ValueError):
                    log.debug("Failed to load template metadata", exc_info=True)
                    templates.append({"id": p.stem, "name": p.stem, "description": "", "icon": "&#128203;"})
    return jsonify({"templates": templates})


# ── Export JSON concaténé pour LLM ────────────────────────────────────────

def _prune_empty(obj):
    """
    Nettoyage récursif : retire les None, chaînes vides, listes vides,
    dicts vides (après nettoyage de leurs enfants).
    Conserve les booléens (False est informatif) et les zéros numériques.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            v2 = _prune_empty(v)
            if v2 is not None:
                cleaned[k] = v2
        return cleaned if cleaned else None
    if isinstance(obj, list):
        cleaned = [_prune_empty(item) for item in obj]
        cleaned = [item for item in cleaned if item is not None]
        return cleaned if cleaned else None
    if obj is None:
        return None
    if isinstance(obj, str) and obj.strip() == "":
        return None
    return obj


def _collect_hpo_codes(modules_data: dict) -> list:
    """
    Parcourt tous les modules et collecte les codes HPO trouvés.

    Cherche dans 3 emplacements par module :
      1. module.hpo_codes[]          (neuropath, radio)
      2. module.hpo.findings[]       (macro_frais, macro_autopsie, macro_fixe)
      3. sous-dicts module.X.hpo_codes[]  (fallback)
    """
    hpo_codes = []
    seen = set()

    def _add(code_id, label, term, source):
        if code_id and code_id not in seen:
            seen.add(code_id)
            entry = {"code": code_id, "source": source}
            lbl = label or term or ""
            if lbl:
                entry["label"] = lbl
            hpo_codes.append(entry)

    for mod_name, mod_data in modules_data.items():
        if not isinstance(mod_data, dict):
            continue

        codes = mod_data.get("hpo_codes", [])
        if isinstance(codes, list):
            for c in codes:
                if isinstance(c, dict):
                    _add(c.get("code"), c.get("label", ""),
                         c.get("term", c.get("term_fr", "")), mod_name)
                else:
                    _add(str(c), "", "", mod_name)

        hpo_obj = mod_data.get("hpo", {})
        if isinstance(hpo_obj, dict):
            findings = hpo_obj.get("findings", [])
            if isinstance(findings, list):
                for f in findings:
                    if isinstance(f, dict):
                        _add(f.get("code"), f.get("label", ""),
                             f.get("term", ""), mod_name)

        for key, val in mod_data.items():
            if isinstance(val, dict) and "hpo_codes" in val:
                sub_codes = val["hpo_codes"]
                if isinstance(sub_codes, list):
                    for c in sub_codes:
                        if isinstance(c, dict):
                            _add(c.get("code"), c.get("label", ""),
                                 c.get("term", c.get("term_fr", "")),
                                 f"{mod_name}.{key}")
                        else:
                            _add(str(c), "", "", f"{mod_name}.{key}")

    return hpo_codes


@admin_llm_bp.route("/api/cases/<int:case_id>/concat-ollama", methods=["POST"])
def api_concat_ollama(case_id):
    """
    Exporte un JSON concaténé du cas pour consommation LLM.
    Body optionnel : {"version": "v3"} (défaut: v3)
    V3 = schéma foetopath_llm_export_v3 (brief + dossier_complet pour pipeline LLM)
    V2 = schéma foetopath_llm_export_v2.2 (narratif, HPO inline, ratios diagnostiques)
    V1 = ancien format (rétrocompatibilité)
    """
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    dossier = case.get("numero_dossier", "")
    if not dossier:
        return jsonify({"error": t('errors.dossier_required')}), 400

    body = request.get_json() or {}
    version = body.get("version", "v3")

    all_modules = db.get_all_modules(case_id)
    modules_data = {name: mod["data"] for name, mod in all_modules.items()
                    if isinstance(mod, dict) and "data" in mod}

    data_root = db.get_setting("data_root")
    if data_root:
        base_dir = Path(data_root) / "Foetus" / dossier
    elif case.get("dossier_macro_path"):
        base_dir = Path(case["dossier_macro_path"])
    else:
        base_dir = db.get_db_path().parent / "Foetus" / dossier
    base_dir.mkdir(parents=True, exist_ok=True)

    if version == "v1":
        concat = _build_concat_v1(case_id, case, dossier, modules_data)
        json_path = base_dir / "cas_concat_ollama_v1.json"
        hpo_count = len(concat.get("hpo_codes", []))
        schema_version = concat.get("_meta", {}).get("version", "1.1.0")
    elif version == "v2":
        import concat as concat_mod
        concat = concat_mod.build_v2(case_id, case, modules_data)
        json_path = base_dir / "cas_concat_llm_v2.json"
        hpo_count = concat.get("hpo_summary", {}).get("total_count", 0)
        schema_version = concat.get("_meta", {}).get("version", "2.2.0")
    else:
        import concat as concat_mod
        concat = concat_mod.build_v3(case_id, case, modules_data)
        json_path = base_dir / "cas_concat_llm.json"
        hpo_count = concat.get("brief", {}).get("hpo_summary", {}).get("total_count", 0)
        schema_version = "3.0.0"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(concat, f, ensure_ascii=False, indent=2)

    log.info("Exported concat-llm %s JSON for case %s → %s", version, dossier, json_path)

    if version == "v3":
        terme_sa = concat.get("brief", {}).get("identite", {}).get("terme_sa")
        sections = list(concat.keys())
    else:
        terme_sa = concat.get("identite", {}).get("terme_sa") or \
                   concat.get("biometries_fraiches", {}).get("terme_reference_sa")
        sections = [k for k in concat.keys() if not k.startswith("_")]

    return jsonify({
        "status": "ok",
        "path": str(json_path),
        "version": schema_version,
        "hpo_count": hpo_count,
        "has_zscores": True,
        "terme_sa": terme_sa,
        "sections": sections,
    })


@admin_llm_bp.route("/api/cases/<int:case_id>/llm-pipeline", methods=["POST"])
def api_llm_pipeline(case_id):
    """
    Pipeline LLM deux passes.
    Query params :
      ?passe=1     → Passe 1 seule (orientation syndromique)
      ?passe=2     → Passe 2 seule (nécessite body.syndromique)
      (rien)       → Pipeline complet (Passe 1 + Passe 2)
    Body optionnel :
      {"syndromique": {...}}  → output syndromique pour passe 2 seule
      {"config": {...}}       → override de la config LLM
    """
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": t('errors.case_not_found')}), 404

    all_modules = db.get_all_modules(case_id)
    modules_data = {name: mod["data"] for name, mod in all_modules.items()
                    if isinstance(mod, dict) and "data" in mod}

    import concat as concat_mod
    case_json = concat_mod.build_v3(case_id, case, modules_data)

    body = request.get_json() or {}
    passe = request.args.get("passe", type=int)
    config = body.get("config")

    # Rendre le template CR choisi pour guider la passe 2
    template_cr = None
    template_id = body.get("template_id")
    if template_id and passe != 1:
        try:
            import cr_templates
            computed = modules_data.get("computed_biometrics", {})
            ctx = cr_templates.build_cr_context(case, modules_data, computed)
            template_cr = cr_templates.render_cr(template_id, ctx)
        except Exception as e:
            log.warning("Template render for LLM guide failed: %s", e)

    try:
        import llm_pipeline

        if passe == 1:
            result = llm_pipeline.pipeline_passe1(case_json, config)
            try:
                db.save_module_data(case_id, "last_cr_syndromique", {
                    "output_syndromique": result.get("output_syndromique", {}),
                    "thinking": result.get("thinking", ""),
                    "model": result.get("meta", {}).get("model", ""),
                    "tokens": result.get("meta", {}).get("eval_count", 0),
                    "elapsed_s": result.get("meta", {}).get("elapsed_s", 0),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                log.warning("save last_cr_syndromique failed: %s", e)
            return jsonify({"status": "ok", "passe": 1, **result})

        elif passe == 2:
            syndromique = body.get("syndromique")
            if not syndromique:
                return jsonify({
                    "error": "Passe 2 nécessite body.syndromique "
                             "(output de la passe 1)"
                }), 400
            result = llm_pipeline.pipeline_passe2(
                case_json, syndromique, config,
                template_cr=template_cr)
            try:
                db.save_module_data(case_id, "last_cr_passe2", {
                    "compte_rendu_markdown": result.get("compte_rendu_markdown", ""),
                    "thinking": result.get("thinking", ""),
                    "model": result.get("meta", {}).get("model", ""),
                    "tokens": result.get("meta", {}).get("eval_count", 0),
                    "elapsed_s": result.get("meta", {}).get("elapsed_s", 0),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                log.warning("save last_cr_passe2 failed: %s", e)
            return jsonify({"status": "ok", "passe": 2, **result})

        else:
            result = llm_pipeline.pipeline_llm(case_json, config,
                                                     template_cr=template_cr)

            dossier = case.get("numero_dossier", "")
            data_root = db.get_setting("data_root")
            if data_root:
                base_dir = Path(data_root) / "Foetus" / dossier
            elif case.get("dossier_macro_path"):
                base_dir = Path(case["dossier_macro_path"])
            else:
                base_dir = db.get_db_path().parent / "Foetus" / dossier
            base_dir.mkdir(parents=True, exist_ok=True)

            synd_path = base_dir / "orientation_syndromique.json"
            with open(synd_path, "w", encoding="utf-8") as f:
                json.dump(result["orientation_syndromique"], f,
                          ensure_ascii=False, indent=2)

            cr_path = base_dir / "compte_rendu_llm.md"
            with open(cr_path, "w", encoding="utf-8") as f:
                f.write(result["compte_rendu_markdown"])

            log.info("LLM pipeline completed for case %s — "
                     "P1: %.1fs, P2: %.1fs",
                     dossier,
                     result["meta"]["passe1_elapsed_s"],
                     result["meta"]["passe2_elapsed_s"])

            return jsonify({
                "status": "ok",
                "orientation_path": str(synd_path),
                "cr_path": str(cr_path),
                **result,
            })

    except ImportError:
        return jsonify({
            "error": "Module llm_pipeline non disponible."
        }), 500
    except Exception as e:
        log.error("LLM pipeline error for case %s: %s", case_id, e)
        return jsonify({"error": str(e)}), 500


def _build_concat_v1(case_id, case, dossier, modules_data):
    """Ancien export v1 (rétrocompatibilité)."""
    import biometrics

    macro_frais = modules_data.get("macro_frais", {})
    macro_autopsie = modules_data.get("macro_autopsie", {})

    terme = None
    maceration = 0
    if macro_frais:
        terme_obj = macro_frais.get("terme")
        if isinstance(terme_obj, dict):
            terme = terme_obj.get("sa")
        elif isinstance(terme_obj, (int, float)):
            terme = int(terme_obj)
        if not terme:
            bio = macro_frais.get("biometries", macro_frais.get("biometrie", {}))
            terme = bio.get("terme_sa") or bio.get("terme")
        mac_obj = macro_frais.get("maceration")
        if isinstance(mac_obj, dict):
            maceration = mac_obj.get("maroun_score", 0) or 0
    if not terme and case.get("terme_issue"):
        m = re.match(r"(\d+)", str(case["terme_issue"]))
        if m:
            terme = int(m.group(1))

    computed_results = {}
    if terme:
        terme = int(terme)
        computed_results = biometrics.compute_all(
            terme_sa=terme, macro_frais=macro_frais or None,
            macro_autopsie=macro_autopsie or None, maceration_grade=maceration)

    hpo_codes = _collect_hpo_codes(modules_data)
    skip_keys = {"_submitted_by", "_submitted_at", "_submitted_via",
                 "photos", "photo_keys", "toggles", "timestamp", "type",
                 "dossier", "sa_from_frais", "maroun_from_frais",
                 "hpo", "hpo_codes", "hpo_meta"}

    modules_clean = {}
    for name, data in modules_data.items():
        if name in ("computed_biometrics", "last_cr", "last_cr_llm",
                    "last_cr_syndromique", "last_cr_passe2"):
            continue
        stripped = {k: v for k, v in data.items() if k not in skip_keys}
        cleaned = _prune_empty(stripped) or {}
        if cleaned:
            modules_clean[name] = cleaned

    return {
        "_meta": {
            "case_id": case_id, "numero_dossier": dossier,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.1.0",
        },
        "case_admin": _prune_empty({
            "numero_dossier": dossier, "sexe": case.get("sexe"),
            "terme_issue": case.get("terme_issue"),
            "indication_examen": case.get("indication_examen"),
            "nom_mere": case.get("nom_mere"),
        }) or {},
        "modules": modules_clean,
        "biometrics_zscores": _prune_empty(computed_results) or {},
        "hpo_codes": hpo_codes,
    }
