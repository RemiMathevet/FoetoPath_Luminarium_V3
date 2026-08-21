"""Utilitaires partagés pour le package concat."""

from typing import Optional


def _prune(obj):
    """
    Nettoyage récursif R1 : retire None, chaînes vides, listes vides,
    dicts vides (après nettoyage récursif des enfants).
    Conserve les booléens (False est informatif) et les zéros numériques.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("//"):
                continue
            v2 = _prune(v)
            if v2 is not None:
                cleaned[k] = v2
        return cleaned if cleaned else None
    if isinstance(obj, list):
        cleaned = [_prune(item) for item in obj]
        cleaned = [item for item in cleaned if item is not None]
        return cleaned if cleaned else None
    if obj is None:
        return None
    if isinstance(obj, str) and obj.strip() == "":
        return None
    return obj


def _get(obj, *keys):
    """Navigation sécurisée dans un dict imbriqué."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _f(val) -> Optional[float]:
    """Conversion sécurisée en float."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _finding(constatation: str, hpo_code: str = None, hpo_label: str = None) -> dict:
    """Construit un objet constatation + HPO inline."""
    obj = {"constatation": constatation}
    if hpo_code:
        obj["hpo"] = hpo_code
    if hpo_label:
        obj["hpo_label"] = hpo_label
    return obj
