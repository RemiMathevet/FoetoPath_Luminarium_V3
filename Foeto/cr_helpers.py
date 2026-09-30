"""
Helpers partagés pour les templates CR (fœtus et placenta).

Fournit l'environnement Jinja2 et les 4 fonctions de registre communes :
  - get_available_templates(registry)
  - get_template_changelog(registry, template_id)
  - get_all_versions_info(registry)
  - render_cr(registry, template_id, context, ...)
"""

import html as _html
import os
import re

from jinja2 import Environment, FileSystemLoader, TemplateError, Template, Undefined

from i18n import t as _t

_template_dir = os.path.join(os.path.dirname(__file__), "templates", "cr")
jinja_env = Environment(loader=FileSystemLoader(_template_dir), autoescape=False)


# ── Rendu des templates CR utilisateur (« custom », stockés en base) ──────────
# Ces templates sont du HTML saisi dans l'éditeur, avec des {{ variables }}.
# Trois règles de rendu, cf. render_user_template().

_EMPTY = "\x00"          # variable appelée mais vide  ┐ sentinelles retirées
_FILLED = "\x01"         # variable appelée et remplie ┘ en fin de rendu
# On coupe aussi sur la virgule : une seule valeur manquante ne doit pas emporter
# toute la phrase (« Le cordon est d'insertion X, long de Ycm, Zspiralé. » garde
# ses deux premiers membres si seule la spiralisation est vide).
# Pas de point-virgule : il termine les entités HTML (&nbsp;) et couperait la
# phrase juste avant sa variable vide, laissant le début orphelin.
# L'éditeur produit des &nbsp; littéraux : à ce stade ce ne sont pas des \s.
_WS = r"(?:\s|&nbsp;)"
# (?!\d) : un point entre deux chiffres est une décimale, pas une fin de phrase.
# (?![^()]*\)) : une virgule à l'intérieur d'une parenthèse n'est pas sécante,
# sinon supprimer « (XDS, » laisse « selon Redline). » orpheline.
_SENTENCE = re.compile(rf"(?:(?<=[.:])|(?<=,)(?![^()]*\)))(?!\d){_WS}*")
# Découpe de repli, à l'intérieur d'un membre qui contient AUSSI une valeur
# remplie : on coupe devant les connecteurs pour ne sacrifier que « de Xcm »
# et garder « pour Yg » (cf. _drop_empty_sentences).
_CONNECTOR = re.compile(
    rf"{_WS}+(?=(?:de|du|des|à|au|aux|pour|avec|sur|par|en|et|x){_WS})")
_TAG = re.compile(r"(<[^>]+>)")
_BLOCK_END = re.compile(r"<\s*(br|/div|/p|/li|/tr|/h[1-6])[^>]*>", re.I)


class SilentUndefined(Undefined):
    """Variable inexistante → chaîne vide, et jamais d'exception au rendu."""

    def __str__(self):
        return _EMPTY

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False


def _flatten(v) -> list[str]:
    """dict/list imbriqués → liste plate de chaînes non vides."""
    if v is None or v == "" or v == [] or v == {}:
        return []
    if isinstance(v, dict):
        v = list(v.values())
    if isinstance(v, (list, tuple)):
        return [s for x in v for s in _flatten(x)]
    return [str(v)]


def _finalize(v):
    """Applique aux valeurs injectées : vide → sentinelle, liste → énumération,
    saut de ligne → <br>, et pas de majuscule initiale (on est en milieu de phrase)."""
    if v is None or (isinstance(v, (str, list, tuple, dict)) and len(v) == 0):
        return _EMPTY
    if isinstance(v, (dict, list, tuple)):       # évite la fuite de repr Python
        v = ", ".join(_flatten(v))
        if not v:
            return _EMPTY
    if isinstance(v, str):
        if "\n" in v:                            # ex. composite_micro_text : un compartiment par ligne
            v = v.replace("\n", "<br>")
        # "Ovale" → "ovale" ; laisse M/F et les sigles (2e lettre majuscule) intacts
        elif len(v) > 1 and v[0].isupper() and v[1].islower():
            v = v[0].lower() + v[1:]
    return f"{_FILLED}{v}"


def _drop_empty_sentences(html_str: str) -> str:
    """Retire les phrases contenant une variable vide, sans toucher aux balises."""
    out = []
    for chunk in _TAG.split(html_str):
        if chunk.startswith("<") or _EMPTY not in chunk:
            out.append(chunk)
            continue
        kept = []
        for seg in _SENTENCE.split(chunk):
            if _EMPTY not in seg:
                kept.append(seg)
            elif _FILLED in seg:
                # le membre porte aussi une valeur remplie : on ne jette que les
                # bouts vides (« de Xcm x Ycm pour 363g » → « pour 363g »)
                kept += [s for s in _CONNECTOR.split(seg) if _EMPTY not in s]
        # la virgule qui précédait le membre supprimé reste orpheline en fin de ligne
        out.append(re.sub(rf",{_WS}*$", "", " ".join(kept)))
    return "".join(out)


def html_to_text(html_str: str) -> str:
    """HTML → texte brut en gardant les retours à la ligne des blocs."""
    s = _BLOCK_END.sub("\n", html_str)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def render_user_template(source: str, context: dict) -> tuple[str, str]:
    """Rend un template CR utilisateur → (html, texte)."""
    html_str = Template(source, undefined=SilentUndefined,
                        finalize=_finalize).render(**context)
    html_str = (_drop_empty_sentences(html_str)
                .replace(_EMPTY, "").replace(_FILLED, ""))
    return html_str, html_to_text(html_str)


def get_available_templates(registry: dict) -> list[dict]:
    return [
        {
            "id": tid,
            "label": t["label"],
            "description": t["description"],
            "version": t.get("version", "1.0.0"),
        }
        for tid, t in registry.items()
    ]


def get_template_changelog(registry: dict, template_id: str) -> list[dict]:
    if template_id not in registry:
        return []
    return registry[template_id].get("changelog", [])


def get_all_versions_info(registry: dict) -> dict:
    return {
        tid: {
            "label": t["label"],
            "current_version": t.get("version", "1.0.0"),
            "changelog": t.get("changelog", []),
        }
        for tid, t in registry.items()
    }


def render_cr(registry: dict, template_id: str, context: dict,
              custom_helpers: dict = None, footer_prefix: str = "") -> str:
    if template_id not in registry:
        return f"Template '{template_id}' non trouvé."

    tpl_entry = registry[template_id]
    tpl_file = tpl_entry["file"]
    version = tpl_entry.get("version", "1.0.0")

    try:
        tpl = jinja_env.get_template(tpl_file)
    except TemplateError as e:
        return f"Erreur chargement template '{tpl_file}': {str(e)}"

    ctx = {**context, "t": _t}
    if custom_helpers:
        ctx.update(custom_helpers)

    rendered = tpl.render(**ctx)
    prefix = f"{footer_prefix}/" if footer_prefix else ""
    rendered += f"\n---\n[Template {prefix}{template_id} v{version}]"

    return rendered
