#!/usr/bin/env python3
"""Renomme d'après l'étiquette les lames dont le nom ne suit pas <cas>_<bloc>_<coupe> (ex. « 06 », « DS_B08R_01S »).

Étiquette standard : « 25P1234 | N | Flc:1 | Blc:11/18 » -> 25P1234_11_1 (Blc = bloc, Flc = lame).
Renomme le .mrxs et son dossier de données, les range dans hot/<cas>/, met à jour lames.nom_lame/chemin
et pose lames.nom_ocr = ancien nom (non NULL = nom lu par OCR, affiché avec un symbole dans le viewer).
Rien n'est renommé si l'étiquette est incomplète ou si le nom cible existe déjà : la lame est signalée.

    python renommer_ocr.py [nom_lame ...]     (défaut : toutes les lames hot au nom atypique)
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Bureau/Pipeline_mrxs_blur_IA"))

DB = Path(os.environ.get("LAMES_DB_PATH", "/media/SSDsamsung/db/lames.db"))
HOT = Path(os.environ.get("LAMES_HOT_DIR", "/media/toshiba1/hot"))   # comme run_ingest (pas de table config sous Windows)
NOM_OK = re.compile(r"^\d{2}P\d+_\d+_\d+(_x\d+)?$")


def nom_depuis_etiquette(texte: str) -> str | None:
    """« 25P1234 | N | Flc : 1 | Bic:13/18 » -> « 25P1234_13_1 » ; None si un champ manque."""
    cas = re.search(r"\b(\d{2}P\d{3,6})\b", texte)
    bloc = re.search(r"B[lI1i]c\s*:\s*(\d+)", texte)
    lame = re.search(r"F[lI1i]c\s*:\s*(\d+)", texte)
    if not (cas and bloc and lame):
        return None
    return f"{cas.group(1)}_{int(bloc.group(1))}_{int(lame.group(1))}"


def main(noms: list[str]) -> int:
    db = sqlite3.connect(DB)
    if "nom_ocr" not in {r[1] for r in db.execute("PRAGMA table_info(lames)")}:
        db.execute("ALTER TABLE lames ADD COLUMN nom_ocr TEXT")
    hot = HOT
    rows = db.execute("SELECT id, nom_lame, chemin FROM lames WHERE storage='hot' AND chemin IS NOT NULL").fetchall()
    rows = [r for r in rows if not NOM_OK.match(r[1]) and (not noms or r[1] in noms)]
    if not rows:
        return 0
    try:
        from etiquettes_ocr import lire
    except ImportError as e:                         # release Windows : pas de RapidOCR, noms gardés tels quels
        print(f"OCR indisponible ({e}) : {len(rows)} lame(s) au nom atypique gardées telles quelles")
        return 0
    pris = {n for (n,) in db.execute("SELECT nom_lame FROM lames")}
    pris |= {re.sub(r"_x\d+$", "", n) for n in pris}
    signales = 0
    for lid, ancien, chemin in rows:
        mrxs = hot / chemin
        _, texte, _, _ = lire((ancien, str(mrxs)))
        cible = nom_depuis_etiquette(texte)
        suffixe = (re.search(r"_x\d+$", ancien) or [""])[0]
        if not cible or cible in pris:
            print(f"SIGNALÉE  {ancien}  étiquette « {texte} »  -> {cible or 'incomplète'}"
                  f"{' déjà en base' if cible else ''}")
            signales += 1
            continue
        nouveau = cible + suffixe
        dest = hot / cible.split("_")[0]
        dest.mkdir(exist_ok=True)
        mrxs.rename(dest / f"{nouveau}.mrxs")
        if mrxs.with_suffix("").is_dir():
            mrxs.with_suffix("").rename(dest / nouveau)
        db.execute("UPDATE lames SET nom_lame=?, chemin=?, nom_ocr=? WHERE id=?",
                   (nouveau, f"{dest.name}/{nouveau}.mrxs", ancien, lid))
        db.commit()
        pris |= {nouveau, cible}
        try:
            mrxs.parent.rmdir()                      # dossier-cas factice (« 06/ », « DS/ ») s'il est vide
        except OSError:
            pass
        print(f"RENOMMÉE  {ancien} -> {nouveau}  (étiquette « {texte} »)")
    return signales


if __name__ == "__main__":
    assert nom_depuis_etiquette("25P1234 | N | Flc : 1 | Blc:11/18 | RM") == "25P1234_11_1"
    assert nom_depuis_etiquette("：25P1234 | N | Fic:1 | Bic:9/18") == "25P1234_9_1"
    assert nom_depuis_etiquette("CHU | 26P1") is None
    assert NOM_OK.match("25P1234_11_1_x28") and not NOM_OK.match("DS_B08R_01S_x28")
    main(sys.argv[1:])
