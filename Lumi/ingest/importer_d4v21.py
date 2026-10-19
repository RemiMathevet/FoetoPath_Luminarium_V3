#!/usr/bin/env python3
"""Range à côté de chaque lame ingérée ce que la release D4V2.1 (Pipeline_D4V21_WSI) a déjà calculé.

Sortie de la release : <src>/<lame>/mirax/<lame>[_x28].mrxs, <src>/<lame>/heatmaps/<lame>__*.json,
<src>/_d4v21/superpixels/<lame>_sp<um>v<V>_<col>_<row>.geojson (spx90, spx500). La release calcule sur la
lame du scanner, donc sous son nom d'origine : renommés ici au nom de la lame en base (suffixe _x28,
renommage OCR -> lames.nom_ocr) et posés dans <dossier de la lame>/superpixels/ et heatmaps/, là où le
viewer les cherche. Coordonnées inchangées : une copie _x28 annonce toujours le niveau 0 d'origine.
Un fichier déjà présent n'est pas écrasé.

    python importer_d4v21.py SRC nom_lame [nom_lame ...]
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

DB = Path(os.environ.get("LAMES_DB_PATH", "/media/SSDsamsung/db/lames.db"))
HOT = Path(os.environ.get("LAMES_HOT_DIR", "/media/toshiba1/hot"))   # comme run_ingest (pas de table config sous Windows)


def a_copier(src: Path, nom: str, orig: str, dossier: Path):
    """[(source, destination)] des caches de la lame `nom` (nom d'origine `orig`) vers `dossier`."""
    for base in dict.fromkeys((orig, re.sub(r"_x\d+$", "", orig))):
        # « base_sp » / « base__ » : 25P1234_1_1 ne ramasse pas 25P1234_1_10
        paires = [(f, dossier / "superpixels" / (nom + f.name[len(base):]))
                  for f in sorted((src / "_d4v21" / "superpixels").glob(f"{base}_sp*.geojson"))]
        paires += [(f, dossier / "heatmaps" / (nom + f.name[len(base):]))
                   for f in sorted((src / base / "heatmaps").glob(f"{base}__*.json"))]
        if paires:
            return paires
    return []


def main(src: Path, noms: list[str]) -> None:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(lames)")}
        ocr = "nom_ocr" if "nom_ocr" in cols else "NULL"
        rows = c.execute(f"SELECT nom_lame, chemin, {ocr} FROM lames WHERE chemin IS NOT NULL").fetchall()
    for nom, chemin, nom_ocr in rows:
        if nom not in noms:
            continue
        paires = a_copier(src, nom, nom_ocr or nom, (HOT / chemin).parent)
        n = 0
        for f, d in paires:
            if not d.exists():
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, d)
                n += 1
        if paires:
            print(f"D4V2.1  {nom} : {n} fichiers importés ({len(paires) - n} déjà là)")


def _check():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        src, dos = Path(t) / "src", Path(t) / "hot" / "25P1234"
        (src / "_d4v21" / "superpixels").mkdir(parents=True)
        (src / "25P1234_1_1" / "heatmaps").mkdir(parents=True)
        for n in ("25P1234_1_1_sp90v3_0_0", "25P1234_1_1_sp500v3_2_1", "25P1234_1_10_sp90v3_0_0"):
            (src / "_d4v21" / "superpixels" / f"{n}.geojson").touch()
        (src / "25P1234_1_1" / "heatmaps" / "25P1234_1_1__villos.json").touch()
        got = {d.relative_to(dos).as_posix() for _, d in a_copier(src, "25P1234_1_1_x28", "25P1234_1_1_x28", dos)}
        assert got == {"superpixels/25P1234_1_1_x28_sp90v3_0_0.geojson", "superpixels/25P1234_1_1_x28_sp500v3_2_1.geojson",
                       "heatmaps/25P1234_1_1_x28__villos.json"}, got
        # renommage OCR : nom d'origine « 06 » -> fichiers « 06_* » rangés sous le nouveau nom
        (src / "_d4v21" / "superpixels" / "06_sp90v3_0_0.geojson").touch()
        got = [d.name for _, d in a_copier(src, "25P1234_2_1", "06", dos)]
        assert got == ["25P1234_2_1_sp90v3_0_0.geojson"], got
        assert a_copier(src, "25P1234_3_1", "25P1234_3_1", dos) == []
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        _check()
    else:
        main(Path(sys.argv[1]), sys.argv[2:])
