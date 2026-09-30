"""
Sync service: scanning and importing cases from local FoetoPath directory.
"""

import json
import logging
import sqlite3
from pathlib import Path

import db
from config import PHOTO_EXTENSIONS

log = logging.getLogger(__name__)


def _scan_one_case(entry: Path, case_type: str, stats: dict):
    """
    Scanne un dossier de cas individuel et importe en BDD.

    Args:
        entry: Path to case directory
        case_type: Type of case ('foetus' or 'placentas')
        stats: Statistics dictionary to update

    Returns:
        Dictionary with scan details
    """
    detail = {"name": entry.name, "type": case_type, "ok": True, "photos": 0, "jsons_found": []}
    case_id_str = entry.name  # ex: "25P1234"

    # ── 1. Compter les photos ─────────────────────────────────────
    photos_dir = entry / "photos"
    if photos_dir.is_dir():
        for f in photos_dir.iterdir():
            if f.is_file() and f.suffix.lower() in PHOTO_EXTENSIONS:
                try:
                    if f.stat().st_size >= 1024:
                        detail["photos"] += 1
                        stats["photos"] += 1
                except OSError:
                    log.debug("File stat error: %s", f, exc_info=True)

    # ── 2. Trouver ou créer le cas en BDD ─────────────────────────
    existing = db.get_case_by_numero(case_id_str)
    if existing:
        case_id = existing["id"]
        db.update_case(case_id, {"dossier_macro_path": str(entry)})
        detail["action"] = "updated"
        stats["updated"] += 1
    else:
        try:
            case_id = db.create_case({
                "numero_dossier": case_id_str,
                "dossier_macro_path": str(entry),
            })
            detail["action"] = "created"
            stats["imported"] += 1
        except (sqlite3.Error, ValueError) as e:
            detail["ok"] = False
            detail["error"] = str(e)
            stats["errors"] += 1
            return detail

    detail["case_id"] = case_id

    # ── 3. Importer TOUS les .json trouvés dans le dossier ────────
    #    Noms réels : 25P1234_macro_frais.json, 25P1234_macro_autopsie.json, etc.
    for f in sorted(entry.iterdir()):
        if not f.is_file() or f.suffix.lower() != ".json":
            continue
        fname = f.name  # ex: "25P1234_macro_frais.json"

        # Déduire le nom du module : retirer le préfixe "{CASE_ID}_" et le ".json"
        # "25P1234_macro_frais.json" → "macro_frais"
        # "macro_frais.json" → "macro_frais" (sans préfixe)
        stem = f.stem  # "25P1234_macro_frais"
        if stem.startswith(case_id_str + "_"):
            module_name = stem[len(case_id_str) + 1:]  # "macro_frais"
        else:
            module_name = stem  # "macro_frais"

        try:
            with open(f, "r", encoding="utf-8") as fh:
                json_data = json.load(fh)
            db.save_module_data(case_id, module_name, json_data)
            detail["jsons_found"].append(fname)
            stats["jsons"] += 1
        except (OSError, json.JSONDecodeError) as e:
            detail.setdefault("json_errors", []).append(f"{fname}: {e}")
            stats["errors"] += 1

    # ── 4. Scanner les sous-dossiers photos ───────────────────────
    db.scan_macro_folders(case_id, str(entry))

    return detail


def run_sync(data_root: str, import_placentas: bool = False) -> dict:
    """
    Scanne le dossier FoetoPath local et importe/fusionne les cas en BDD.

    Structure attendue :
      data_root/                          ← ex: /home/remi/Bureau/FoetoPath
      ├── Foetus/
      │   ├── 25P1234/
      │   │   ├── 25P1234_macro_frais.json
      │   │   ├── 25P1234_macro_autopsie.json
      │   │   └── photos/
      │   │       ├── 25P1234_photo_face.jpg
      │   │       └── ...
      │   └── 25P5678/
      │       └── ...
      └── Placentas/
          ├── 25P9012/
          │   ├── macro_frais.json
          │   └── photos/
          └── ...

    Scanne Foetus/ et Placentas/ (et tout sous-dossier direct contenant des cas).

    Args:
        data_root: Root directory path to scan
        import_placentas: Whether to also import placentas (default: False)

    Returns:
        Dictionary with scan statistics and results
    """
    source = Path(data_root)
    if not source.is_dir():
        raise ValueError(f"Dossier introuvable : {data_root}")

    stats = {"scanned": 0, "imported": 0, "updated": 0, "photos": 0, "jsons": 0, "errors": 0, "details": []}

    # Déterminer les dossiers à scanner :
    # Si data_root contient Foetus/ ou Placentas/, scanner ces sous-dossiers
    # Sinon, scanner directement data_root (chaque sous-dossier = un cas)
    categories = []
    for candidate in ["Foetus", "foetus", "Placentas", "placentas"]:
        cat_dir = source / candidate
        if cat_dir.is_dir():
            case_type = candidate.lower()
            # Skip placentas if not requested
            if "placenta" in case_type and not import_placentas:
                continue
            categories.append((cat_dir, case_type))

    # Si aucune catégorie trouvée, scanner la racine directement
    if not categories:
        categories = [(source, "inconnu")]

    for cat_dir, case_type in categories:
        for entry in sorted(cat_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            stats["scanned"] += 1
            detail = _scan_one_case(entry, case_type, stats)
            stats["details"].append(detail)

    return {
        "status": "ok",
        "message": (
            f"Scan terminé : {stats['scanned']} dossier(s), "
            f"{stats['imported']} créé(s), {stats['updated']} mis à jour, "
            f"{stats['jsons']} JSON importé(s), {stats['photos']} photo(s)"
        ),
        "stats": stats,
        "source": str(source),
    }


def scan_macro_for_case(case_id: int) -> dict:
    """
    Scanne les sous-dossiers macro d'un cas.

    Args:
        case_id: Case ID to scan macros for

    Returns:
        Dictionary with folders list and path
    """
    case = db.get_case(case_id)
    if not case:
        raise ValueError(f"Cas non trouvé : {case_id}")

    macro_path = case.get("dossier_macro_path")
    if not macro_path:
        raise ValueError("Chemin macro non défini")

    macro_path_obj = Path(macro_path)
    if not macro_path_obj.is_dir():
        raise ValueError(f"Chemin macro introuvable : {macro_path}")

    results = db.scan_macro_folders(case_id, macro_path)
    return {"folders": results, "path": macro_path}
