"""
Pairing service: matching slides with macro photos for a case.
"""

import json
import logging
import os
from pathlib import Path

import db
from utils.file_ops import list_photos_in, list_slides_in

log = logging.getLogger(__name__)


def build_pairing_table(case_id: int) -> dict:
    """
    Construit le tableau d'appairage pour un cas :
    - Photos macro frais
    - Photos macro fixé (= cassettes)
    - Lames correspondantes
    - Contrôle cassettes vs lames

    Args:
        case_id: Case ID to build pairing for

    Returns:
        Dictionary with pairing table, stats, and paths
    """
    case = db.get_case(case_id)
    if not case:
        raise ValueError(f"Cas non trouvé : {case_id}")

    macro_path = case.get("dossier_macro_path", "")
    lames_path = case.get("dossier_lames_path", "")

    # Si pas de chemin lames défini, demander à Lumi le dossier des lames du cas
    if not lames_path:
        from services import lumi
        lames_path = lumi.get_case_slides_dir(case["numero_dossier"]) or ""

    # Collecter les photos macro
    photos_frais = []
    photos_autopsie = []
    photos_fixe = []
    photos_neuropath = []

    if macro_path and os.path.isdir(macro_path):
        mp = Path(macro_path)
        for sub, target in [
            ("frais", photos_frais),
            ("autopsie", photos_autopsie),
            ("fixe", photos_fixe),
            ("neuropath", photos_neuropath),
        ]:
            sub_path = mp / sub
            if sub_path.is_dir():
                target.extend(list_photos_in(str(sub_path)))

    # Collecter les lames
    slides = []
    if lames_path and os.path.isdir(lames_path):
        slides = list_slides_in(lames_path)

    # Lire les données JSON de l'examen macro frais (pour les organes/cassettes)
    cassettes_data = db.get_module_data(case_id, "interne") or {}
    macro_frais_json = None
    if macro_path:
        for jname in ["macro_frais.json", "tranches_section.json"]:
            jpath = Path(macro_path) / jname
            if jpath.is_file():
                try:
                    with open(jpath, "r", encoding="utf-8") as f:
                        if jname == "macro_frais.json":
                            macro_frais_json = json.load(f)
                        else:
                            cassettes_data["tranches"] = json.load(f)
                except (OSError, json.JSONDecodeError):
                    log.debug("Failed to load JSON metadata: %s", jpath, exc_info=True)

    # Construire l'appairage par organe/ID
    # On tente de matcher par nom de fichier (convention: organe_xxx)
    pairing_rows = []

    # Extraire les organes depuis les photos macro fixé (= cassettes)
    organ_ids = set()
    photo_map_frais = {}
    photo_map_fixe = {}

    for ph in photos_frais:
        # Convention : nom du fichier = ID_organe_xxx.jpg
        key = ph["name"].split("_")[0].upper() if "_" in ph["name"] else ph["name"].upper()
        photo_map_frais.setdefault(key, []).append(ph)
        organ_ids.add(key)

    for ph in photos_fixe:
        key = ph["name"].split("_")[0].upper() if "_" in ph["name"] else ph["name"].upper()
        photo_map_fixe.setdefault(key, []).append(ph)
        organ_ids.add(key)

    # Matcher les lames par nom
    slide_map = {}
    for sl in slides:
        key = sl["name"].split("_")[0].upper() if "_" in sl["name"] else sl["name"].upper()
        slide_map.setdefault(key, []).append(sl)
        organ_ids.add(key)

    for organ_id in sorted(organ_ids):
        pairing_rows.append({
            "organ_id": organ_id,
            "photos_frais": photo_map_frais.get(organ_id, []),
            "photos_fixe": photo_map_fixe.get(organ_id, []),
            "slides": slide_map.get(organ_id, []),
        })

    # Statistiques de contrôle
    total_cassettes = len(photos_fixe)
    total_lames = len(slides)

    return {
        "case_id": case_id,
        "numero_dossier": case["numero_dossier"],
        "pairing": pairing_rows,
        "stats": {
            "photos_frais": len(photos_frais),
            "photos_autopsie": len(photos_autopsie),
            "photos_fixe": total_cassettes,
            "photos_neuropath": len(photos_neuropath),
            "slides": total_lames,
            "cassettes_vs_lames_ok": total_cassettes == total_lames if total_cassettes > 0 else None,
        },
        "paths": {
            "macro": macro_path,
            "lames": lames_path,
        },
        "macro_frais_json": macro_frais_json,
    }
