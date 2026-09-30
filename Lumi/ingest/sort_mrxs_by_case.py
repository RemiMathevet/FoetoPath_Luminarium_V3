#!/usr/bin/env python3
"""
sort_mrxs_by_case.py
--------------------
Trie les fichiers .mrxs et leurs dossiers de données (DAT) dans des
sous-dossiers correspondant au nom du cas.

Convention de nommage : aaP[b...]_bloc_coupe.mrxs
  - Le nom du cas = tout avant le premier '_' (ex: 26P123)
  - Chaque cas obtient un dossier (ex: 26P123/) contenant ses lames

Fonctionnalités :
  - Déplacement (défaut) ou copie (--copy) des .mrxs + dossiers DAT
  - Vérification d'intégrité optionnelle (--check) via check_mrxs_integrity
  - Mode dry-run pour prévisualiser sans toucher aux fichiers
  - Rapport TSV récapitulatif

Usage :
    python sort_mrxs_by_case.py /data/lames_vrac /data/lames_triees
    python sort_mrxs_by_case.py /data/lames_vrac /data/lames_triees --check
    python sort_mrxs_by_case.py /data/lames_vrac /data/lames_triees --copy --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_mrxs_integrity import check_one_slide, COLUMNS as INTEGRITY_COLUMNS


def extract_case_name(mrxs_path: Path) -> str:
    stem = mrxs_path.stem
    parts = stem.split("_")
    return parts[0]


def find_mrxs_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() == ".mrxs":
        return [root]
    if not root.is_dir():
        return []
    found = []
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() == ".mrxs":
            found.append(p)
    found.sort()
    return found


def get_slide_dir(mrxs_path: Path) -> Path | None:
    d = mrxs_path.parent / mrxs_path.stem
    return d if d.is_dir() else None


def move_slide(mrxs_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(mrxs_path), str(dest_dir / mrxs_path.name))
    slide_dir = get_slide_dir(mrxs_path)
    if slide_dir:
        shutil.move(str(slide_dir), str(dest_dir / slide_dir.name))


def copy_slide(mrxs_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mrxs_path, dest_dir / mrxs_path.name)
    slide_dir = get_slide_dir(mrxs_path)
    if slide_dir:
        dest_slide_dir = dest_dir / slide_dir.name
        if dest_slide_dir.exists():
            shutil.rmtree(dest_slide_dir)
        shutil.copytree(slide_dir, dest_slide_dir)


def human_size(nbytes: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if nbytes < 1024:
            return f"{nbytes:.0f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} To"


def slide_total_size(mrxs_path: Path) -> int:
    total = mrxs_path.stat().st_size if mrxs_path.is_file() else 0
    slide_dir = get_slide_dir(mrxs_path)
    if slide_dir:
        for p in slide_dir.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Trie les .mrxs dans des dossiers par cas (aaP[num])."
    )
    ap.add_argument("input_dir", type=Path,
                    help="Dossier source contenant les .mrxs en vrac.")
    ap.add_argument("output_dir", type=Path,
                    help="Dossier de destination (sous-dossiers par cas).")
    ap.add_argument("--copy", action="store_true",
                    help="Copier au lieu de déplacer.")
    ap.add_argument("--check", action="store_true",
                    help="Vérifier l'intégrité de chaque lame avant tri.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Afficher les opérations sans les exécuter.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Ignorer les cas dont le dossier existe déjà dans output_dir.")
    ap.add_argument("--tsv", type=Path, default=None,
                    help="Chemin du rapport TSV (défaut: output_dir/sort_report.tsv).")
    ap.add_argument("--db", type=Path, default=None,
                    help="Base SQLite : met à jour la colonne chemin dans la table lames.")
    args = ap.parse_args()

    if not args.input_dir.is_dir():
        print(f"[ERREUR] Dossier source introuvable : {args.input_dir}", file=sys.stderr)
        return 2

    mrxs_files = find_mrxs_files(args.input_dir)
    if not mrxs_files:
        print(f"[INFO] Aucun .mrxs trouvé dans {args.input_dir}", file=sys.stderr)
        return 0

    cases: dict[str, list[Path]] = defaultdict(list)
    for f in mrxs_files:
        cases[extract_case_name(f)].append(f)

    if args.skip_existing:
        existing = {d.name for d in args.output_dir.iterdir() if d.is_dir()} if args.output_dir.is_dir() else set()
        skipped = {c for c in cases if c in existing}
        if skipped:
            skipped_slides = sum(len(cases[c]) for c in skipped)
            print(
                f"[INFO] --skip-existing : {len(skipped)} cas ignoré(s) "
                f"({skipped_slides} lame(s)) : {', '.join(sorted(skipped))}",
                file=sys.stderr,
            )
            for c in skipped:
                del cases[c]
            mrxs_files = [f for f in mrxs_files if extract_case_name(f) in cases]

    action = "Copie" if args.copy else "Déplacement"
    print(
        f"[INFO] {len(mrxs_files)} lame(s), {len(cases)} cas détecté(s). "
        f"Action : {action}{'  [DRY-RUN]' if args.dry_run else ''}",
        file=sys.stderr,
    )

    conn = None
    if args.db:
        conn = sqlite3.connect(str(args.db))
        conn.execute("PRAGMA journal_mode=WAL")

    report_rows: list[dict] = []
    fail_count = 0

    for case_name in sorted(cases.keys()):
        slides = cases[case_name]
        dest_case_dir = args.output_dir / case_name
        print(f"\n  {case_name}/ ({len(slides)} lame(s))", file=sys.stderr)

        for mrxs in slides:
            slide_dir = get_slide_dir(mrxs)
            size = slide_total_size(mrxs)
            dat_status = "OK" if slide_dir else "MANQUANT"
            integrity_status = ""

            if args.check:
                result = check_one_slide(mrxs)
                integrity_status = result.get("status", "?")
                if integrity_status == "FAIL":
                    fail_count += 1
                    print(
                        f"    ✗ {mrxs.name}  [{human_size(size)}]  "
                        f"intégrité=FAIL  ({result.get('errors', '')})",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"    ✓ {mrxs.name}  [{human_size(size)}]  "
                        f"intégrité={integrity_status}",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"    {'→' if not args.dry_run else '~'} {mrxs.name}  "
                    f"[{human_size(size)}]  dat={dat_status}",
                    file=sys.stderr,
                )

            if not args.dry_run:
                try:
                    if args.copy:
                        copy_slide(mrxs, dest_case_dir)
                    else:
                        move_slide(mrxs, dest_case_dir)
                    op_status = "OK"
                    if conn is not None:
                        new_chemin = f"{case_name}/{mrxs.name}"
                        conn.execute(
                            "UPDATE lames SET chemin = ? WHERE nom_lame = ?",
                            (new_chemin, mrxs.stem),
                        )
                        conn.commit()
                except Exception as e:
                    op_status = f"ERREUR:{e}"
                    print(f"      [ERREUR] {e}", file=sys.stderr)
            else:
                op_status = "DRY-RUN"

            report_rows.append({
                "case": case_name,
                "slide": mrxs.name,
                "dat_folder": dat_status,
                "size": human_size(size),
                "integrity": integrity_status,
                "operation": op_status,
            })

    tsv_path = args.tsv or args.output_dir / "sort_report.tsv"
    if not args.dry_run:
        tsv_path.parent.mkdir(parents=True, exist_ok=True)
        cols = ["case", "slide", "dat_folder", "size", "integrity", "operation"]
        with open(tsv_path, "w", encoding="utf-8") as f:
            f.write("\t".join(cols) + "\n")
            for row in report_rows:
                f.write("\t".join(row.get(c, "") for c in cols) + "\n")
        print(f"\n[FAIT] Rapport : {tsv_path}", file=sys.stderr)

    if conn is not None:
        conn.close()

    ok = sum(1 for r in report_rows if r["operation"] == "OK")
    print(
        f"[RÉSUMÉ] {ok}/{len(mrxs_files)} triée(s), "
        f"{len(cases)} cas, "
        f"{fail_count} échec(s) intégrité",
        file=sys.stderr,
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
