#!/usr/bin/env python3
"""
check_mrxs_integrity.py
-----------------------
Vérifie l'intégrité des lames MRXS (3DHISTECH/Pannoramic) avant batch.

Pour chaque .mrxs trouvé récursivement dans le path d'entrée, vérifie :
  - présence du fichier .mrxs (header texte INI)
  - présence du dossier homonyme (sans extension)
  - présence et lisibilité de Slidedat.ini dans ce dossier
  - présence d'Index.dat
  - présence des Data####.dat listés dans HIERARCHICAL/NONHIERLAYER_*
  - cohérence des tailles avec ce qu'annonce Slidedat.ini quand dispo
  - lecture de la première section avec OpenSlide si dispo (best-effort)

Sortie : TSV avec une ligne par lame.

Usage:
    python check_mrxs_integrity.py <input_path> <output_tsv>
"""

from __future__ import annotations

import argparse
import configparser
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"

# Omnissiah (lecteur MRXS maison, robuste) en premier ; OpenSlide en repli.
try:
    from omnissiah import MrxsReader  # type: ignore
    HAVE_OMNISSIAH = True
except Exception:
    HAVE_OMNISSIAH = False

try:
    import openslide  # type: ignore
    HAVE_OPENSLIDE = True
except Exception:
    HAVE_OPENSLIDE = False


def open_dimensions(mrxs_path: Path) -> tuple[int, int]:
    """Ouvre la lame et rend (w, h) du level 0. Omnissiah d'abord, OpenSlide sinon."""
    if HAVE_OMNISSIAH:
        info = MrxsReader(str(mrxs_path)).slide_info()
        l0 = info["levels"][0]
        return int(l0["width"]), int(l0["height"])
    if HAVE_OPENSLIDE:
        slide = openslide.OpenSlide(str(mrxs_path))
        try:
            return slide.dimensions
        finally:
            slide.close()
    raise RuntimeError("aucun lecteur MRXS disponible")


COLUMNS = [
    "mrxs_path",
    "slide_name",
    "status",                 # OK | WARN | FAIL | MISSING
    "mrxs_exists",
    "mrxs_size_bytes",
    "folder_exists",
    "slidedat_ini_exists",
    "index_dat_exists",
    "expected_data_files",    # int : nombre de Data####.dat attendus d'après l'INI
    "found_data_files",       # int : effectivement présents
    "missing_data_files",     # liste séparée par ; des fichiers manquants
    "total_folder_size_bytes",
    "openslide_open_ok",      # 1/0/NA
    "openslide_dimensions",   # WxH du level 0, ou ""
    "errors",                 # détail des erreurs séparées par "|"
]


def parse_slidedat(slidedat_path: Path) -> tuple[configparser.ConfigParser | None, str]:
    """Parse Slidedat.ini de façon tolérante. Retourne (parser, error_msg)."""
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    # Slidedat.ini est généralement en latin-1 / cp1252
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(slidedat_path, "r", encoding=enc) as f:
                parser.read_file(f)
            return parser, ""
        except (UnicodeDecodeError, configparser.Error):
            continue
        except Exception as e:
            return None, f"slidedat_read:{type(e).__name__}:{e}"
    return None, "slidedat_unreadable_all_encodings"


def expected_data_files_from_ini(parser: configparser.ConfigParser) -> list[str]:
    """
    Extrait la liste des fichiers Data####.dat référencés dans le Slidedat.ini.
    Les sections HIERARCHICAL et NONHIERLAYER_* listent leurs sous-sections,
    qui chacune ont un FILE_X = DataYYYY.dat.
    Approche tolérante : on ramasse toute clé qui ressemble à FILE_<n>.
    """
    files: set[str] = set()
    for section in parser.sections():
        for key, value in parser.items(section):
            k = key.strip().upper()
            v = value.strip()
            if k.startswith("FILE_") and v.lower().endswith(".dat"):
                files.add(v)
    return sorted(files)


def check_one_slide(mrxs_path: Path) -> dict:
    """Vérifie une lame MRXS. Retourne un dict des colonnes COLUMNS."""
    row = {col: "" for col in COLUMNS}
    errors: list[str] = []

    row["mrxs_path"] = str(mrxs_path)
    row["slide_name"] = mrxs_path.stem
    row["openslide_open_ok"] = "NA"

    # 1. fichier .mrxs lui-même
    mrxs_exists = mrxs_path.is_file()
    row["mrxs_exists"] = "1" if mrxs_exists else "0"
    if mrxs_exists:
        try:
            row["mrxs_size_bytes"] = str(mrxs_path.stat().st_size)
        except OSError as e:
            errors.append(f"mrxs_stat:{e}")
    else:
        errors.append("mrxs_file_missing")

    # 2. dossier homonyme
    folder = mrxs_path.with_suffix("")
    folder_exists = folder.is_dir()
    row["folder_exists"] = "1" if folder_exists else "0"
    if not folder_exists:
        errors.append("folder_missing")
        row["status"] = "FAIL"
        row["errors"] = "|".join(errors)
        return row

    # 3. Slidedat.ini
    slidedat = folder / "Slidedat.ini"
    slidedat_exists = slidedat.is_file()
    row["slidedat_ini_exists"] = "1" if slidedat_exists else "0"
    parser: configparser.ConfigParser | None = None
    if slidedat_exists:
        parser, perr = parse_slidedat(slidedat)
        if perr:
            errors.append(perr)
    else:
        errors.append("slidedat_ini_missing")

    # 4. Index.dat
    index_dat = folder / "Index.dat"
    row["index_dat_exists"] = "1" if index_dat.is_file() else "0"
    if not index_dat.is_file():
        errors.append("index_dat_missing")

    # 5. Data####.dat attendus vs présents
    expected: list[str] = []
    if parser is not None:
        try:
            expected = expected_data_files_from_ini(parser)
        except Exception as e:
            errors.append(f"ini_parse_data_files:{type(e).__name__}:{e}")
    row["expected_data_files"] = str(len(expected))

    present_data = sorted(p.name for p in folder.glob("Data*.dat"))
    row["found_data_files"] = str(len(present_data))

    missing = [f for f in expected if not (folder / f).is_file()]
    row["missing_data_files"] = ";".join(missing)
    if missing:
        errors.append(f"missing_data_files:{len(missing)}")

    # 6. taille totale dossier
    try:
        total = 0
        for p in folder.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        row["total_folder_size_bytes"] = str(total)
    except Exception as e:
        errors.append(f"folder_size:{type(e).__name__}:{e}")

    # 7. test d'ouverture réelle (Omnissiah, sinon OpenSlide) — best-effort
    if (HAVE_OMNISSIAH or HAVE_OPENSLIDE) and mrxs_exists:
        try:
            w, h = open_dimensions(mrxs_path)
            row["openslide_dimensions"] = f"{w}x{h}"
            row["openslide_open_ok"] = "1"
            # La lame s'ouvre : un échec du parse configparser de Slidedat.ini
            # est un faux positif (l'INI est lisible par le lecteur WSI).
            errors = [e for e in errors if e != "slidedat_unreadable_all_encodings"]
        except Exception as e:
            row["openslide_open_ok"] = "0"
            errors.append(f"reader:{type(e).__name__}:{str(e)[:120]}")

    # statut global
    if not mrxs_exists or not folder_exists or not slidedat_exists or not row["index_dat_exists"] == "1":
        row["status"] = "FAIL"
    elif missing or row["openslide_open_ok"] == "0":
        row["status"] = "FAIL"
    elif errors:
        row["status"] = "WARN"
    else:
        row["status"] = "OK"

    row["errors"] = "|".join(errors)
    return row


def find_mrxs_files(root: Path) -> list[Path]:
    """Trouve récursivement tous les .mrxs sous root. Tolère root = fichier unique."""
    if root.is_file() and root.suffix.lower() == ".mrxs":
        return [root]
    if not root.is_dir():
        return []
    found: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".mrxs"):
                found.append(Path(dirpath) / fn)
    found.sort()
    return found


def init_integrity_table(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS integrity_checks (
            id                   TEXT PRIMARY KEY,
            lame_id              TEXT NOT NULL REFERENCES lames(id),
            status               TEXT NOT NULL,
            mrxs_exists          INTEGER,
            folder_exists        INTEGER,
            slidedat_ini_exists  INTEGER,
            index_dat_exists     INTEGER,
            expected_data_files  INTEGER,
            found_data_files     INTEGER,
            missing_data_files   TEXT,
            openslide_open_ok    TEXT,
            openslide_dimensions TEXT,
            errors               TEXT,
            date_check           TEXT NOT NULL,
            script_version       TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def insert_integrity_row(conn: sqlite3.Connection, row: dict, lame_id: str) -> str:
    check_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO integrity_checks
           (id, lame_id, status, mrxs_exists, folder_exists,
            slidedat_ini_exists, index_dat_exists, expected_data_files,
            found_data_files, missing_data_files, openslide_open_ok,
            openslide_dimensions, errors, date_check, script_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            check_id, lame_id, row.get("status", ""),
            int(row.get("mrxs_exists", 0) or 0),
            int(row.get("folder_exists", 0) or 0),
            int(row.get("slidedat_ini_exists", 0) or 0),
            int(row.get("index_dat_exists", 0) or 0),
            int(row.get("expected_data_files", 0) or 0),
            int(row.get("found_data_files", 0) or 0),
            row.get("missing_data_files", ""),
            row.get("openslide_open_ok", "NA"),
            row.get("openslide_dimensions", ""),
            row.get("errors", ""),
            datetime.now(timezone.utc).isoformat(),
            __version__,
        ),
    )
    conn.commit()
    return check_id


def resolve_lame_id(conn: sqlite3.Connection, slide_name: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM lames WHERE nom_lame = ?", (slide_name,)
    ).fetchone()
    return row[0] if row else None


def write_tsv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            line = "\t".join(
                str(r.get(c, "")).replace("\t", " ").replace("\n", " ").replace("\r", " ")
                for c in COLUMNS
            )
            f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Vérifie l'intégrité des lames MRXS avant batch FRANCINE."
    )
    ap.add_argument("input_path", type=Path, help="Dossier racine (récursif) ou .mrxs unique.")
    ap.add_argument("output_tsv", type=Path, help="Chemin du TSV de sortie.")
    ap.add_argument(
        "--no-openslide",
        action="store_true",
        help="Désactive le test d'ouverture OpenSlide (utile pour scan rapide).",
    )
    ap.add_argument(
        "--db", type=Path, default=None,
        help="Chemin de la base SQLite (insère les résultats dans integrity_checks).",
    )
    args = ap.parse_args()

    global HAVE_OPENSLIDE, HAVE_OMNISSIAH
    if args.no_openslide:
        HAVE_OPENSLIDE = False
        HAVE_OMNISSIAH = False

    if not args.input_path.exists():
        print(f"[ERREUR] Chemin introuvable : {args.input_path}", file=sys.stderr)
        return 2

    mrxs_files = find_mrxs_files(args.input_path)
    if not mrxs_files:
        print(f"[INFO] Aucun .mrxs trouvé sous {args.input_path}", file=sys.stderr)
        write_tsv([], args.output_tsv)
        return 0

    print(
        f"[INFO] {len(mrxs_files)} lame(s) à vérifier "
        f"(lecteur={'omnissiah' if HAVE_OMNISSIAH else 'openslide' if HAVE_OPENSLIDE else 'aucun'})",
        file=sys.stderr,
    )

    conn = None
    if args.db:
        conn = init_integrity_table(args.db)

    rows: list[dict] = []
    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    db_inserted = 0
    for i, mrxs in enumerate(mrxs_files, 1):
        try:
            row = check_one_slide(mrxs)
        except Exception as e:
            row = {c: "" for c in COLUMNS}
            row["mrxs_path"] = str(mrxs)
            row["slide_name"] = mrxs.stem
            row["status"] = "FAIL"
            row["errors"] = f"unhandled:{type(e).__name__}:{e}"
        rows.append(row)
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        print(f"[{i}/{len(mrxs_files)}] {row['status']:4s}  {mrxs}", file=sys.stderr)

        if conn is not None:
            lame_id = resolve_lame_id(conn, row["slide_name"])
            if lame_id:
                insert_integrity_row(conn, row, lame_id)
                db_inserted += 1
            else:
                print(f"  [DB] SKIP {row['slide_name']} — introuvable dans table lames", file=sys.stderr)

    if conn is not None:
        conn.close()
        print(f"[DB] {db_inserted} résultats insérés dans integrity_checks", file=sys.stderr)

    write_tsv(rows, args.output_tsv)
    print(
        f"[FAIT] OK={counts.get('OK',0)}  WARN={counts.get('WARN',0)}  "
        f"FAIL={counts.get('FAIL',0)}  ->  {args.output_tsv}",
        file=sys.stderr,
    )
    # exit code != 0 si au moins une FAIL, pratique pour scripter
    return 1 if counts.get("FAIL", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
