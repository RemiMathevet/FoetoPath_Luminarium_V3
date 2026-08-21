#!/usr/bin/env python3
"""
FoetoPath — Internationalisation (i18n).

Fournit une fonction de traduction `t(key)` utilisable dans :
  - Les templates Jinja2 : {{ t('nav.home') }}
  - Le code Python : from i18n import t; t('errors.not_found')

La langue active est lue depuis le setting 'language' (défaut : 'fr').
Les fichiers de traduction sont dans locales/<code>.json.
"""

import json
import logging
from pathlib import Path
from functools import lru_cache

log = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "fr"
FALLBACK_LANG = "fr"

# Cache des fichiers de traduction chargés
_translations: dict[str, dict] = {}


def _load_locale(lang: str) -> dict:
    """Charge un fichier locale JSON. Retourne {} si introuvable."""
    if lang in _translations:
        return _translations[lang]
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        log.warning("Locale file not found: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _translations[lang] = data
        log.info("Loaded locale: %s (%d top-level keys)", lang, len(data))
        return data
    except (OSError, json.JSONDecodeError) as e:
        log.error("Failed to load locale %s: %s", lang, e)
        return {}


def reload_translations():
    """Force le rechargement de toutes les traductions (après changement de fichier)."""
    _translations.clear()


def available_languages() -> list[dict]:
    """Retourne la liste des langues disponibles [{code, name}, ...]."""
    langs = []
    for f in sorted(LOCALES_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                meta = data.get("meta", {})
                langs.append({
                    "code": meta.get("code", f.stem),
                    "name": meta.get("name", f.stem),
                })
        except (OSError, json.JSONDecodeError):
            langs.append({"code": f.stem, "name": f.stem})
    return langs


def _resolve(data: dict, key: str) -> str | None:
    """Résout une clé pointée (ex: 'nav.home') dans un dict imbriqué."""
    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current if isinstance(current, str) else None


def get_lang() -> str:
    """Retourne la langue active depuis les settings de la BDD."""
    try:
        import db as settings_db
        lang = settings_db.get_setting("language", DEFAULT_LANG)
        return lang if lang else DEFAULT_LANG
    except Exception:
        return DEFAULT_LANG


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Traduit une clé.

    Args:
        key: Clé pointée (ex: 'nav.home', 'errors.not_found')
        lang: Code langue (optionnel, sinon utilise le setting global)
        **kwargs: Variables de substitution (ex: t('auth.rate_limited', seconds=30))

    Returns:
        La traduction, ou la clé elle-même si non trouvée.
    """
    if lang is None:
        lang = get_lang()

    # Chercher dans la langue demandée
    data = _load_locale(lang)
    result = _resolve(data, key)

    # Fallback sur la langue par défaut
    if result is None and lang != FALLBACK_LANG:
        data = _load_locale(FALLBACK_LANG)
        result = _resolve(data, key)

    # Dernier recours : retourner la clé
    if result is None:
        return key

    # Substitution de variables {var}
    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return result


def get_locale_json(lang: str | None = None) -> dict:
    """Retourne le dictionnaire complet de traductions pour une langue.
    Utile pour injecter côté JS."""
    if lang is None:
        lang = get_lang()
    return _load_locale(lang)


def init_app(app):
    """Enregistre les helpers i18n dans l'application Flask.

    Rend disponible dans tous les templates Jinja2 :
      - {{ t('key') }}
      - {{ lang }}
      - {{ available_languages }}
    """
    @app.context_processor
    def inject_i18n():
        lang = get_lang()
        return {
            "t": lambda key, **kw: t(key, lang=lang, **kw),
            "lang": lang,
            "available_languages": available_languages,
        }

    # Route API pour servir les traductions au JS
    from flask import jsonify

    @app.route("/api/i18n/<lang_code>.json")
    def api_locale(lang_code):
        """Sert le fichier de traduction pour le JS côté client."""
        data = _load_locale(lang_code)
        if not data:
            return jsonify({"error": "Locale not found"}), 404
        return jsonify(data)

    @app.route("/api/i18n/current.json")
    def api_locale_current():
        """Sert les traductions de la langue active."""
        lang = get_lang()
        return jsonify(get_locale_json(lang))
