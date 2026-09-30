#!/usr/bin/env python3
"""
FoetoPath — Fonctions filesystem partagées.

Utilisées par admin_bp.py, placenta_bp.py et app.py pour :
  - Lister photos / lames dans un dossier
  - Servir photos / thumbnails
  - Labelliser les photos par catégorie
"""

import io
import os
from pathlib import Path

from config import PHOTO_EXTENSIONS, SLIDE_EXTENSIONS, MIME_MAP


# ── Listage fichiers ──────────────────────────────────────────────────────

def list_photos_in(folder: str) -> list[dict]:
    """Liste les photos d'un dossier avec métadonnées.

    Filtre les fichiers < 1 Ko (thumbnails/icônes) et ne garde
    que les extensions définies dans PHOTO_EXTENSIONS.
    """
    photos = []
    p = Path(folder)
    if not p.is_dir():
        return photos
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in PHOTO_EXTENSIONS and f.is_file():
            try:
                size = f.stat().st_size
                if size < 1024:
                    continue
            except OSError:
                continue
            photos.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f),
                "size_kb": round(size / 1024, 1),
            })
    return photos


def list_slides_in(folder: str) -> list[dict]:
    """Liste les lames (WSI) d'un dossier."""
    slides = []
    p = Path(folder)
    if not p.is_dir():
        return slides
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in SLIDE_EXTENSIONS and f.is_file():
            slides.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f),
                "extension": f.suffix.lower(),
            })
    return slides


# ── Thumbnails ────────────────────────────────────────────────────────────

def generate_thumbnail(path: str, w: int = 160, h: int = 160) -> bytes:
    """Génère un thumbnail JPEG pour une photo.

    Retourne les bytes JPEG. En cas d'erreur ou fichier introuvable,
    retourne un placeholder gris.
    """
    from PIL import Image

    if not path or not os.path.isfile(path):
        return _placeholder(w, h)

    try:
        img = Image.open(path)
        img.thumbnail((w, h), Image.LANCZOS)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        return buf.read()
    except (OSError, ValueError):
        return _placeholder(w, h)


def extract_exif_datetime(path: str) -> str | None:
    """Extrait la date EXIF (DateTimeOriginal ou DateTime) d'une photo.

    Retourne une chaîne ISO 'YYYY-MM-DD HH:MM' ou None.
    """
    from PIL import Image
    from PIL.ExifTags import Base

    try:
        img = Image.open(path)
        exif = img.getexif()
        if not exif:
            return None
        raw = exif.get(Base.DateTimeOriginal) or exif.get(Base.DateTime)
        if not raw:
            return None
        # Format EXIF : "2024:03:15 14:32:10"
        dt = raw.replace(":", "-", 2)  # → "2024-03-15 14:32:10"
        return dt[:16]  # "2024-03-15 14:32"
    except (OSError, ValueError, AttributeError):
        return None


def find_photo_avant_ouverture(macro_path: str, dossier: str) -> str | None:
    """Cherche la photo avant ouverture dans le dossier photos d'un cas."""
    photos_dir = Path(macro_path) / "photos"
    if not photos_dir.is_dir():
        return None
    for f in photos_dir.iterdir():
        if f.stem == f"{dossier}_p_avant_ouv" and f.suffix.lower() in PHOTO_EXTENSIONS:
            return str(f)
    return None


def _placeholder(w: int, h: int) -> bytes:
    """Génère un placeholder gris."""
    from PIL import Image

    img = Image.new("RGB", (w, h), (60, 60, 70))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


# ── Serving ───────────────────────────────────────────────────────────────

def get_photo_mime(path: str) -> str:
    """Retourne le type MIME d'une photo d'après son extension."""
    ext = Path(path).suffix.lower()
    return MIME_MAP.get(ext, "image/jpeg")


import re

_SAFE_PHOTO_KEY = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_photo_key(key: str) -> bool:
    """Valide un photo_key (pas de path traversal, que alphanum/_/-)."""
    return bool(key and _SAFE_PHOTO_KEY.match(key) and len(key) <= 128)


def validate_photo_path(path: str, allowed_dir: str | None = None) -> tuple[bool, str]:
    """Valide un chemin photo. Retourne (ok, error_message).

    Si allowed_dir est fourni, vérifie que le chemin résolu est bien
    un sous-chemin de ce répertoire (protection path traversal).
    """
    if not path or not os.path.isfile(path):
        return False, "Photo non trouvée"
    ext = Path(path).suffix.lower()
    if ext not in PHOTO_EXTENSIONS:
        return False, "Type non supporté"
    # Protection path traversal
    if allowed_dir:
        resolved = Path(path).resolve()
        base = Path(allowed_dir).resolve()
        if not resolved.is_relative_to(base):
            return False, "Accès refusé"
    return True, ""


# ── Labels photos ─────────────────────────────────────────────────────────

# Catégories de photos (foetus)
PHOTO_CATEGORIES = {
    "anomalie":       ("Anomalies",              "⚠️"),
    "externe":        ("Examen externe",          "👤"),
    "extra_externe":  ("Suppl. examen externe",   "📷"),
    "autopsie":       ("Autopsie",                "🔬"),
    "extra_autopsie": ("Suppl. autopsie",         "📷"),
    "fixe":           ("Macro fixé — Tranches",   "🧪"),
    "fixe_lesion":    ("Macro fixé — Lésions",    "🔎"),
    "extra_fixe":     ("Suppl. macro fixé",       "📷"),
    "neuropath":      ("Neuropathologie",         "🧠"),
    "extra_neuropath":("Suppl. neuropath",        "📷"),
    "autre":          ("Autres",                  "📁"),
}


def cat_info(cat_key: str) -> tuple:
    """Retourne (label, icon) pour une clé de catégorie."""
    return PHOTO_CATEGORIES.get(cat_key, ("Autres", "📁"))


# Labels lisibles pour les suffixes de noms de photos
PHOTO_LABELS = {
    # ── Macro frais — Examen externe (PWA) ──
    "p_dos_gen": "Générale (dos)", "p_dos_face": "Tête face",
    "p_dos_oge": "OGE",
    "p_dos_main_d_paume": "Main D paume", "p_dos_main_d_dos": "Main D dos",
    "p_dos_main_g_paume": "Main G paume", "p_dos_main_g_dos": "Main G dos",
    "p_dos_pied_d": "Pied droit", "p_dos_pied_g": "Pied gauche",
    "p_dos_anus": "Anus",
    "p_droit_gen": "Côté D général", "p_droit_profil": "Profil D",
    "p_gauche_gen": "Côté G général", "p_gauche_profil": "Profil G",
    "p_ventre_gen": "Dos (sur ventre)",
    # ── Macro frais — anciens noms (compat Android) ──
    "photo_face": "Face", "photo_dos": "Dos",
    "photo_profil_droit": "Profil droit", "photo_profil_gauche": "Profil gauche",
    "photo_vue_gen": "Vue générale", "photo_oge": "OGE",
    "photo_mains_droite": "Main droite", "photo_mains_gauche": "Main gauche",
    "photo_pied_droit": "Pied droit", "photo_pied_gauche": "Pied gauche",
    # ── Autopsie ──
    "p_avant_ouv": "Avant ouverture", "p_ouverture": "Ouverture thoraco-abdo",
    "p_situs": "Situs", "p_diaphragme": "Diaphragme",
    "p_thymus": "Thymus", "p_pericarde": "Péricarde",
    "p_tvi": "TVI", "p_tsa": "TSA",
    "p_od_fo": "OD / FO", "p_septum": "Septum IV",
    "p_vd_ej": "VD éjection", "p_vg_ej": "VG éjection",
    "p_vd_av": "VD AV", "p_vg_av": "VG AV",
    "p_coeur": "Cœur", "p_docimasie": "Docimasie",
    "p_poumon_d": "Poumon D", "p_poumon_g": "Poumon G",
    "p_ret_vein_d": "Ret. veineux D", "p_ret_vein_g": "Ret. veineux G",
    "p_tube_dig": "Tube digestif", "p_pancreas": "Pancréas",
    "p_rate": "Rate", "p_reins": "Reins", "p_foie": "Foie",
    "p_estomac": "Estomac", "p_airway": "Voies aériennes",
    "p_surrenales": "Surrénales", "p_cerveau": "Cerveau",
    "p_veine_omb": "V. ombilicale", "p_art_omb": "A. ombilicales",
    "p_appendice": "Appendice", "p_vb": "Vés. biliaire",
    "p_ogi": "OGI", "p_vessie": "Vessie",
    "p_post_restit": "Post-restitution",
    # ── Neuropathologie ──
    "neuropath_face_frontale": "Face frontale",
    "neuropath_cote_droit": "Côté droit",
    "neuropath_cote_gauche": "Côté gauche",
    "neuropath_par_derriere": "Par derrière",
    "neuropath_dessus": "Dessus", "neuropath_dessous": "Dessous",
    "neuropath_coupe_sagittale": "Coupe sagittale",
    "neuropath_vue_posterieure": "Vue postérieure",
    "neuropath_photo_aqueduc": "Aqueduc",
}


def photo_label(suffix: str) -> str:
    """Transforme un suffixe de fichier en label lisible."""
    for key, label in PHOTO_LABELS.items():
        if suffix.startswith(key):
            return label
    # Fallback : cleanup
    return suffix.replace("_", " ").replace("photo ", "").replace("p ", "").capitalize()
