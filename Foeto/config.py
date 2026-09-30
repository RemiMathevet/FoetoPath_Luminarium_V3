#!/usr/bin/env python3
"""
FoetoPath — Configuration centralisée.

Toutes les constantes partagées entre app.py, admin_bp.py, placenta_bp.py,
db.py et placenta_db.py sont définies ici.
"""

import os
from pathlib import Path

# ── Chemins DB externes ──────────────────────────────────────────────────

FOETO_DB_PATH = os.environ.get(
    "FOETO_DB_PATH",
    str(Path.home() / "Bureau" / "foeto_base" / "syndromes_foetaux.db"),
)

# ── Codes institutionnels BaMaRa ─────────────────────────────────────────

BAMARA_SITE_CODE = "S0034"
BAMARA_SITE_LABEL = "ADEST [CST] PIARD"
BAMARA_SITE_ID = 33

# ── Extensions fichiers ───────────────────────────────────────────────────

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tga"}

SLIDE_EXTENSIONS = {
    ".mrxs", ".svs", ".ndpi", ".tiff", ".tif",
    ".scn", ".bif", ".vms", ".vmu",
}

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tga": "image/x-tga",
}

# ── Modules connus ────────────────────────────────────────────────────────

KNOWN_MODULES_FOETUS = [
    "pre_exam", "externe", "biometries", "interne",
    "imagerie", "prelevements", "placenta", "neuropath", "radio", "synthese",
    "macro_frais", "macro_autopsie", "macro_fixe", "computed_biometrics",
    "atcd_maternels", "atcd_obstetricaux", "grossesse_en_cours", "examens_prenataux",
    "last_cr", "last_cr_llm", "last_cr_syndromique",
]

KNOWN_MODULES_PLACENTA = [
    "macro_frais", "tranches_section", "micro", "cr", "computed",
]

KNOWN_MODULES_PEDIATRIQUE = [
    "macro_autopsie", "macro_fixe", "neuropath", "radio",
    "prelevements", "histologie", "descriptions", "computed_biometrics",
    "last_cr", "last_cr_llm",
]

# ── Dossiers macro (foetus) ──────────────────────────────────────────────

MACRO_FOLDER_TYPES = ["photos", "frais", "autopsie", "fixe", "neuropath"]

# ── Paramètres par défaut (table settings, foetus DB) ────────────────────

DEFAULT_SETTINGS = {
    "data_root": "",
    "viewer_port": "5080",
    "auto_sync": "false",
}

# ── Session & sécurité ──────────────────────────────────────────────────

DEFAULT_IDLE_TIMEOUT_MIN = 8
MIN_IDLE_TIMEOUT_MIN = 1
MAX_IDLE_TIMEOUT_MIN = 30
MAX_ABSOLUTE_SESSION_HOURS = 12
DEFAULT_TOTP_COOKIE_HOURS = 4
MIN_TOTP_COOKIE_HOURS = 1
MAX_TOTP_COOKIE_HOURS = 12
