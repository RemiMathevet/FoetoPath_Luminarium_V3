#!/usr/bin/env python3
"""
FoetoPath — Configuration persistante hors base de données.

Stocke les paramètres qui doivent être lus AVANT l'initialisation des BDD
(notamment le chemin du répertoire de données).

Fichier : ~/.config/foetopath/config.json
Format  : {"db_directory": "/chemin/vers/data", ...}

Ce fichier est indépendant des BDD SQLite et peut être édité
manuellement en cas de problème.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Emplacement fixe, indépendant du data_dir
_CONFIG_DIR = Path(os.path.expanduser("~/.config/foetopath"))
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _ensure_dir():
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    """Charge la configuration persistante. Retourne {} si fichier absent."""
    if not _CONFIG_FILE.is_file():
        return {}
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Erreur lecture config persistante: %s", e)
        return {}


def save(config: dict):
    """Sauvegarde la configuration persistante."""
    _ensure_dir()
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    log.info("Config persistante sauvegardée: %s", _CONFIG_FILE)


def get(key: str, default: str = "") -> str:
    """Lit une clé de la config persistante."""
    return load().get(key, default)


def set_key(key: str, value: str):
    """Met à jour une clé dans la config persistante."""
    config = load()
    config[key] = value
    save(config)


def get_db_directory(cli_arg: str = "") -> str:
    """Détermine le répertoire des bases de données.

    Priorité :
      1. Argument CLI --data-dir (si non vide)
      2. Variable d'environnement FOETOPATH_DATA_DIR
      3. Config persistante (db_directory)
      4. Défaut ~/Documents/FoetoPath
    """
    if cli_arg:
        return cli_arg
    env = os.environ.get("FOETOPATH_DATA_DIR", "")
    if env:
        return env
    persisted = get("db_directory", "")
    if persisted:
        return persisted
    return os.path.expanduser("~/Documents/FoetoPath")


def get_config_file_path() -> str:
    """Retourne le chemin du fichier de config (pour affichage)."""
    return str(_CONFIG_FILE)
