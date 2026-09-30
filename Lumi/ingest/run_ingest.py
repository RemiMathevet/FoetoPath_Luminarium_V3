#!/usr/bin/env python3
"""
run_ingest.py — point d'entrée UNIQUE de la CHAÎNE JOUR (CPU) pour Lumi2.

Remplace les pipelines éparpillés (tmux_supervisor/omezarr, Lumi_v3/V4…).
Enchaîne 5 étapes vérifiées et idempotentes :

  1. ingest    : rsync --checksum SRC -> hot (flat), insère row storage='hot',
                 supprime la source APRÈS vérif. SKIP si nom_lame déjà en base.
  2. sort      : range les .mrxs flat en <cas>/ ET fixe lames.chemin.
  3. integrity : check_mrxs_integrity récursif -> table integrite + TSV.
  4. mask      : masque tissu (vignette sous-échantillonnée) -> GeoJSON + TSV.
  5. blur      : OPT-IN (--with-blur) seulement. CPU lent (décode plein-format) ;
                 la netteté utile se dérive des embeddings la nuit.

La partie NUIT (chroma -> embeddings, GPU) est dans run_night.py, lancée par
cron à 22h — PAS ici.

Chemins via env (défauts = infra P620) :
  LAMES_DB_PATH    registre réel (jamais le stub 0-octet de Lames/)
  LAMES_HOT_DIR    SSD hot
  LAMES_MASK_DIR   sortie masques tissu GeoJSON
  LAMES_REPORTS_DIR  TSV integrite/blur

Usage :
    python run_ingest.py /media/mathevet/SSD_2024/Lames
    python run_ingest.py /media/mathevet/SSD_2024/Lames --dry-run   # ingest+sort seuls
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
HOT = Path(os.environ.get("LAMES_HOT_DIR", "/media/toshiba1/hot"))
DB = Path(os.environ.get("LAMES_DB_PATH", "/media/SSDsamsung/db/lames.db"))
# doit matcher MASKS_DIR d'embed_cron.py (masque nommé {nom_lame}.geojson)
MASK_DIR = Path(os.environ.get("LAMES_MASK_DIR", "/media/SSDsamsung/Lames/masks"))
REPORTS = Path(os.environ.get("LAMES_REPORTS_DIR", "/media/SSDsamsung/pipeline_reports"))


def run(cmd: list[str]) -> None:
    print(f"\n$ {' '.join(str(c) for c in cmd)}\n", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"[ABANDON] échec (code {r.returncode}) : {Path(cmd[1]).name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Chaîne JOUR ingestion MRXS Lumi2.")
    ap.add_argument("src", type=Path, help="Dossier source des .mrxs")
    ap.add_argument("--dry-run", action="store_true",
                    help="ingest+sort en dry-run, saute integrity/mask")
    ap.add_argument("--with-blur", action="store_true",
                    help="ajoute le blur_detect CPU (lent, décode plein-format) — "
                         "off par défaut : la netteté se dérive des embeddings la nuit")
    args = ap.parse_args()

    if not args.src.is_dir():
        sys.exit(f"Source introuvable : {args.src}")

    py = sys.executable
    dry = ["--dry-run"] if args.dry_run else []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. SRC -> hot (flat), insert rows
    run([py, HERE / "ingest_mrxs.py", args.src, HOT, "--db", DB, *dry])

    # 2. hot flat -> hot/<cas>/, set chemin. input==output==hot : sort ne relit
    #    que les .mrxs au top-level, pas ceux déjà rangés.
    run([py, HERE / "sort_mrxs_by_case.py", HOT, HOT, "--db", DB, *dry])

    if args.dry_run:
        print("\n[OK] Dry-run terminé (integrity/blur/mask sautés).")
        return

    REPORTS.mkdir(parents=True, exist_ok=True)
    MASK_DIR.mkdir(parents=True, exist_ok=True)

    # 3. intégrité (récursif) -> table integrite + TSV
    run([py, HERE / "check_mrxs_integrity.py", HOT, REPORTS / f"integrity_{ts}.tsv", "--db", DB])

    # 4. masque tissu (vignette sous-échantillonnée = rapide) -> GeoJSON + TSV
    run([py, HERE / "Preanalytique_integrite_mask.py", HOT, MASK_DIR])

    # 5. blur CPU : opt-in seulement. Décode plein-format (lent). La netteté
    #    utile se dérive des patch-embeddings la nuit ; blur_detect reste un
    #    outil de diagnostic standalone.
    if args.with_blur:
        run([py, HERE / "blur_detect.py", HOT, "--db", DB])

    print("\n[OK] Chaîne jour terminée. Nuit (chroma+embeddings) : run_night.py @22h.")


if __name__ == "__main__":
    main()
