#!/usr/bin/env python3
"""
ingest_mrxs.py
--------------
Déplace les lames Mirax (.mrxs + dossier dat) d'un SSD source vers un
répertoire de destination, et enregistre chaque lame dans une base SQLite.

Le déplacement est robuste : rsync --checksum puis suppression de la source
uniquement après vérification. En cas d'interruption, rien n'est perdu.

Table `lames` :
    id          UUID (PK)
    nom_lame    TEXT UNIQUE  (stem du .mrxs, ex: 25P1234_15_3)
    taille_mo   REAL         (taille .mrxs + dossier dat en Mo)
    date_import TEXT         (ISO 8601, UTC)

Usage :
    python ingest_mrxs.py /media/mathevet/SSD_2024 /media/toshiba1/hot
    python ingest_mrxs.py /media/mathevet/SSD_2024 /media/toshiba1/hot --dry-run
    python ingest_mrxs.py /media/mathevet/SSD_2024 /media/toshiba1/hot --db /path/to/lames.db
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# env-driven, défaut = registre réel (jamais le stub 0-octet de Lames/lames.db)
DB_DEFAULT = os.environ.get("LAMES_DB_PATH", "/media/SSDsamsung/db/lames.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── database ────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lames (
            id          TEXT PRIMARY KEY,
            nom_lame    TEXT NOT NULL UNIQUE,
            taille_mo   REAL NOT NULL,
            date_import TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def insert_lame(conn: sqlite3.Connection, nom_lame: str, taille_mo: float) -> str:
    lame_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO lames (id, nom_lame, taille_mo, date_import) VALUES (?, ?, ?, ?)",
        (lame_id, nom_lame, round(taille_mo, 2), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return lame_id


def lame_exists(conn: sqlite3.Connection, nom_lame: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM lames WHERE nom_lame = ?", (nom_lame,)
    ).fetchone()
    return row is not None


# ── filesystem helpers ──────────────────────────────────────────────────

def dir_size_bytes(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def slide_size_mo(mrxs_file: Path, dat_dir: Path | None) -> float:
    total = mrxs_file.stat().st_size
    if dat_dir and dat_dir.is_dir():
        total += dir_size_bytes(dat_dir)
    return total / (1024 * 1024)


def rsync_robust(src: Path, dst: Path) -> None:
    """rsync with checksum verification. Raises on failure."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync") is None:
        # Windows : pas de rsync. Copie Python ; verify_transfer passe ensuite
        # avant toute suppression de la source, comme après rsync.
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return
    cmd = [
        "rsync", "-a", "--checksum", "--whole-file",
        str(src) + ("/" if src.is_dir() else ""),
        str(dst) + ("/" if src.is_dir() else ""),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"rsync failed: {result.stderr.strip()}")


def verify_transfer(src: Path, dst: Path) -> bool:
    """Vérifie que la destination contient au moins autant de données que la source."""
    if src.is_file():
        return dst.is_file() and dst.stat().st_size == src.stat().st_size
    if src.is_dir():
        src_files = sorted(f.relative_to(src) for f in src.rglob("*") if f.is_file())
        for rel in src_files:
            dst_f = dst / rel
            src_f = src / rel
            if not dst_f.is_file():
                return False
            if dst_f.stat().st_size != src_f.stat().st_size:
                return False
        return True
    return False


def safe_remove(path: Path) -> None:
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


# ── discovery ───────────────────────────────────────────────────────────

def discover_slides(src_dir: Path) -> list[tuple[Path, Path | None]]:
    """Retourne la liste (mrxs_file, dat_dir_or_None) triée par nom."""
    slides = []
    for mrxs in sorted(src_dir.glob("*.mrxs")):
        dat_dir = src_dir / mrxs.stem
        slides.append((mrxs, dat_dir if dat_dir.is_dir() else None))
    return slides


# ── space check ─────────────────────────────────────────────────────────

def check_disk_space(slides: list[tuple[Path, Path | None]], dst_dir: Path) -> None:
    total_bytes = 0
    for mrxs, dat_dir in slides:
        total_bytes += mrxs.stat().st_size
        if dat_dir:
            total_bytes += dir_size_bytes(dat_dir)

    free = shutil.disk_usage(dst_dir).free
    total_go = total_bytes / (1024 ** 3)
    free_go = free / (1024 ** 3)

    log.info("Espace nécessaire : %.1f Go  |  Espace libre : %.1f Go", total_go, free_go)
    if total_bytes >= free:
        log.error("Espace insuffisant sur %s. Abandon.", dst_dir)
        sys.exit(1)


# ── main loop ───────────────────────────────────────────────────────────

def ingest(src_dir: Path, dst_dir: Path, db_path: Path, dry_run: bool) -> None:
    slides = discover_slides(src_dir)
    if not slides:
        log.warning("Aucune lame .mrxs trouvée dans %s", src_dir)
        return

    log.info("Lames trouvées : %d", len(slides))

    conn = init_db(db_path)

    # Filtrer les lames déjà importées
    to_process = []
    for mrxs, dat_dir in slides:
        if lame_exists(conn, mrxs.stem):
            log.info("SKIP  %s  (déjà en base)", mrxs.stem)
        else:
            to_process.append((mrxs, dat_dir))

    if not to_process:
        log.info("Toutes les lames sont déjà importées.")
        conn.close()
        return

    log.info("Lames à importer : %d", len(to_process))

    if not dry_run:
        check_disk_space(to_process, dst_dir)

    ok, fail = 0, 0

    for i, (mrxs, dat_dir) in enumerate(to_process, 1):
        nom = mrxs.stem
        log.info("[%d/%d]  %s", i, len(to_process), nom)

        if dry_run:
            taille = slide_size_mo(mrxs, dat_dir)
            log.info("  DRY-RUN  %.1f Mo", taille)
            ok += 1
            continue

        dst_mrxs = dst_dir / mrxs.name
        dst_dat = dst_dir / nom if dat_dir else None

        try:
            # 1. rsync .mrxs
            log.info("  rsync %s", mrxs.name)
            rsync_robust(mrxs, dst_mrxs)
            if not verify_transfer(mrxs, dst_mrxs):
                raise RuntimeError(f"Vérification échouée pour {mrxs.name}")

            # 2. rsync dossier dat
            if dat_dir:
                log.info("  rsync %s/", nom)
                rsync_robust(dat_dir, dst_dat)
                if not verify_transfer(dat_dir, dst_dat):
                    raise RuntimeError(f"Vérification échouée pour {nom}/")

            # 3. Enregistrer en base
            taille = slide_size_mo(dst_mrxs, dst_dat)
            lame_id = insert_lame(conn, nom, taille)
            log.info("  DB  id=%s  %.1f Mo", lame_id[:8], taille)

            # 4. Supprimer la source (uniquement après insertion DB réussie)
            safe_remove(mrxs)
            if dat_dir:
                safe_remove(dat_dir)
            log.info("  OK  source supprimée")

            ok += 1

        except Exception:
            log.exception("  ERREUR  %s — source conservée", nom)
            # Nettoyage partiel côté destination
            if dst_mrxs.exists() and not lame_exists(conn, nom):
                safe_remove(dst_mrxs)
            if dst_dat and dst_dat.exists() and not lame_exists(conn, nom):
                safe_remove(dst_dat)
            fail += 1

    conn.close()
    log.info("Terminé : %d OK, %d erreurs sur %d", ok, fail, len(to_process))


# ── CLI ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestion robuste de lames Mirax vers un SSD + SQLite"
    )
    parser.add_argument("src", type=Path, help="Répertoire source (ex: /media/mathevet/SSD_2024)")
    parser.add_argument("dst", type=Path, help="Répertoire destination (ex: /media/toshiba1/hot)")
    parser.add_argument("--db", type=Path, default=None,
                        help=f"Chemin de la base SQLite (défaut: <dst>/{DB_DEFAULT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Lister les lames sans rien déplacer")
    args = parser.parse_args()

    if not args.src.is_dir():
        log.error("Source introuvable : %s", args.src)
        sys.exit(1)

    args.dst.mkdir(parents=True, exist_ok=True)
    db_path = args.db or Path(DB_DEFAULT)

    ingest(args.src, args.dst, db_path, args.dry_run)


if __name__ == "__main__":
    main()
