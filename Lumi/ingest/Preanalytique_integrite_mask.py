#!/usr/bin/env python3
"""
Preanalytique_integrite_mask.py
-------------------------------
Détection et détourage automatique des tissus sur lame entière (WSI).

Pour chaque lame trouvée récursivement :
  - ouverture via Omnissiah (MRXS) ou OpenSlide (autres formats, fallback)
  - génération d'un masque tissu (seuillage Otsu sur saturation HSV)
  - extraction des contours, filtrage par taille minimale (défaut : 1 mm × 1 mm)
  - export en annotation GeoJSON (compatible QuPath)
  - résumé TSV global

Usage :
    python Preanalytique_integrite_mask.py <input_path> <output_dir>
    python Preanalytique_integrite_mask.py /data/lames /data/masks --min-size-mm 2.0
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from omnissiah import MrxsReader
    HAVE_OMNISSIAH = True
except ImportError:
    HAVE_OMNISSIAH = False

try:
    import openslide
    HAVE_OPENSLIDE = True
except ImportError:
    HAVE_OPENSLIDE = False

if not HAVE_OMNISSIAH and not HAVE_OPENSLIDE:
    print("[ERREUR] omnissiah ou openslide-python requis.", file=sys.stderr)
    sys.exit(1)

try:
    import cv2
except ImportError:
    print("[ERREUR] opencv-python requis. pip install opencv-python-headless", file=sys.stderr)
    sys.exit(1)


SUPPORTED_EXTENSIONS = {".mrxs", ".svs", ".ndpi", ".tif", ".tiff", ".vms", ".vmu", ".scn", ".bif"}

COLUMNS = [
    "slide_path",
    "slide_name",
    "status",                  # OK | WARN | FAIL
    "mpp",
    "dimensions",              # WxH level 0
    "tissue_regions",
    "total_tissue_area_mm2",
    "min_region_area_mm2",
    "max_region_area_mm2",
    "compute_time_s",
    "geojson_path",
    "errors",
]


# ---------------------------------------------------------------------------
#  Wrapper Omnissiah (interface compatible OpenSlide)
# ---------------------------------------------------------------------------

class OmnissiahSlide:
    def __init__(self, path: str):
        self.reader = MrxsReader(path)
        self.info = self.reader.slide_info()

    @property
    def dimensions(self) -> tuple[int, int]:
        l0 = self.info["levels"][0]
        return (l0["width"], l0["height"])

    @property
    def properties(self) -> dict[str, str]:
        return {
            "openslide.mpp-x": str(self.info["mpp_x"]),
            "mirax.LAYER_0_LEVEL_0_SECTION.MICROMETER_PER_PIXEL_X": str(self.info["mpp_x"]),
        }

    def get_thumbnail(self, size: tuple[int, int]) -> Image.Image:
        target_w, target_h = size
        l0 = self.info["levels"][0]
        full_w, full_h = l0["width"], l0["height"]
        needed_ds = max(full_w / max(target_w, 1), full_h / max(target_h, 1))
        thumb_level = 0
        for lvl in self.info["levels"]:
            if lvl["downsample"] <= needed_ds + 1e-3:
                thumb_level = lvl["level"]
        lvl = self.info["levels"][thumb_level]
        all_coords = self.reader.tile_coords(thumb_level)
        if not all_coords:
            return Image.new("RGB", size, (255, 255, 255))
        coords_np = np.array(all_coords, dtype=np.int64)
        tiles = self.reader.read_tiles_batch(coords_np, thumb_level)
        tw, th = lvl["tile_w"], lvl["tile_h"]
        lw, lh = lvl["width"], lvl["height"]
        canvas = np.zeros((lh, lw, 3), dtype=np.uint8)
        for idx, (tx, ty) in enumerate(all_coords):
            xs, ys = tx * tw, ty * th
            tile = tiles[idx]
            h, w = tile.shape[:2]
            canvas[ys:ys + min(h, lh - ys), xs:xs + min(w, lw - xs)] = \
                tile[:min(h, lh - ys), :min(w, lw - xs)]
        thumb = Image.fromarray(canvas)
        thumb.thumbnail(size, Image.LANCZOS)
        return thumb

    def close(self):
        pass


def open_slide(path: Path):
    if path.suffix.lower() == ".mrxs" and HAVE_OMNISSIAH:
        return OmnissiahSlide(str(path))
    if HAVE_OPENSLIDE:
        return openslide.OpenSlide(str(path))
    raise RuntimeError(f"Pas de lecteur disponible pour {path.suffix}")


# ---------------------------------------------------------------------------
#  Utilitaires
# ---------------------------------------------------------------------------

def get_slide_mpp(slide) -> float:
    for key in ["openslide.mpp-x",
                "mirax.LAYER_0_LEVEL_0_SECTION.MICROMETER_PER_PIXEL_X"]:
        val = slide.properties.get(key)
        if val:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return 0.25


def find_slides(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() in SUPPORTED_EXTENSIONS:
        return [root]
    if not root.is_dir():
        return []
    found: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if Path(fn).suffix.lower() in SUPPORTED_EXTENSIONS:
                found.append(Path(dirpath) / fn)
    found.sort()
    return found


# ---------------------------------------------------------------------------
#  Masque tissu
# ---------------------------------------------------------------------------

def tissue_mask_from_array(
    rgb: np.ndarray,
    bridge_px: int = 0,
    sat_sensitivity: float = 1.0,
    fill: bool = True,
    thresh: int | None = None,
    open_iters: int = 2,
) -> np.ndarray:
    """Masque tissu (Otsu sur la saturation HSV) sur un tableau RGB déjà chargé. -> uint8 0/255.

    `fill=False` garde les trous internes : indispensable pour superpixeliser, sinon la chambre
    intervilleuse est rendue au tissu et SLIC dépense ses superpixels dans le vide.

    `thresh` court-circuite l'Otsu local. Sur une tuile, Otsu recalcule un seuil à partir des
    seuls pixels présents : mesuré de 17 à 74 sur les 42 tuiles à tissu d'une même lame, si bien
    qu'une tuile de parenchyme dense place la barre à 74 et rejette tout ce qui est pâle. Passer
    le seuil de la lame entière rend les tuiles comparables (+13 % de tissu retenu).
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]

    if thresh is None:
        thresh, _ = cv2.threshold(saturation, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    lowered_thresh = max(1, int(thresh * sat_sensitivity))
    mask = (saturation >= lowered_thresh).astype(np.uint8) * 255

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    if open_iters:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=open_iters)

    if bridge_px > 0:
        k = 2 * bridge_px + 1
        bridge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, bridge_kernel)

    if not fill:
        return mask
    contours_fill, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask_filled = np.zeros_like(mask)
    cv2.drawContours(mask_filled, contours_fill, -1, 255, cv2.FILLED)
    return mask_filled


def generate_tissue_mask(
    slide,
    downsample: int = 64,
    bridge_px: int = 0,
    sat_sensitivity: float = 1.0,
) -> tuple[np.ndarray, tuple[int, int]]:
    dims = slide.dimensions
    thumb_w = max(1, dims[0] // downsample)
    thumb_h = max(1, dims[1] // downsample)
    thumbnail = slide.get_thumbnail((thumb_w, thumb_h))
    thumb_np = np.array(thumbnail.convert("RGB"))

    mask_filled = tissue_mask_from_array(thumb_np, bridge_px, sat_sensitivity)
    return mask_filled, (thumb_np.shape[1], thumb_np.shape[0])


# ---------------------------------------------------------------------------
#  Extraction contours → level 0
# ---------------------------------------------------------------------------

def extract_tissue_contours(
    mask: np.ndarray,
    thumb_size: tuple[int, int],
    slide_dims: tuple[int, int],
    min_area_px2: float,
    epsilon_factor: float = 0.001,
) -> list[dict]:
    scale_x = slide_dims[0] / thumb_size[0]
    scale_y = slide_dims[1] / thumb_size[1]

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions: list[dict] = []
    for cnt in contours:
        area_thumb = cv2.contourArea(cnt)
        area_level0 = area_thumb * scale_x * scale_y
        if area_level0 < min_area_px2:
            continue

        peri = cv2.arcLength(cnt, True)
        simplified = cv2.approxPolyDP(cnt, epsilon_factor * peri, True)
        if len(simplified) < 3:
            continue

        coords = [[float(pt[0][0] * scale_x), float(pt[0][1] * scale_y)]
                   for pt in simplified]
        coords.append(coords[0])

        regions.append({"coords": coords, "area_px2": area_level0})

    return regions


# ---------------------------------------------------------------------------
#  GeoJSON QuPath
# ---------------------------------------------------------------------------

MASK_VERSION = "1.0"    # À INCRÉMENTER dès qu'un paramètre par défaut ou l'algo change. Un masque
                        # régénéré élargit ou rétrécit la grille de patchs : tout .h5 encodé avant
                        # n'est plus row-aligné avec un encodage postérieur, et rien ne le signale.
                        # Mesuré le 2026-07-30 : 362 lames sur 1447 dans ce cas depuis la reprise
                        # du 22/07 (--sat-sensitivity 0.4, masque plus permissif au tissu pâle).


def regions_to_geojson(regions: list[dict], mpp: float, params: dict | None = None) -> dict:
    um_per_mm = 1000.0
    px_to_mm = mpp / um_per_mm

    features = []
    for i, region in enumerate(regions):
        area_mm2 = region["area_px2"] * (px_to_mm ** 2)
        features.append({
            "type": "Feature",
            "id": f"tissue_{i}",
            "geometry": {
                "type": "Polygon",
                "coordinates": [region["coords"]],
            },
            "properties": {
                "objectType": "annotation",
                "classification": {"name": "Tissue", "color": [0, 128, 0]},
                "isLocked": False,
                "measurements": {"area_mm2": round(area_mm2, 4)},
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "maskVersion": MASK_VERSION,          # hors spec GeoJSON mais toléré : QuPath ignore les
        "maskParams": params or {},           # clés inconnues au niveau FeatureCollection
        "maskGeneratedAt": datetime.datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
#  Traitement d'une lame
# ---------------------------------------------------------------------------

def process_one_slide(
    slide_path: Path,
    output_dir: Path,
    min_size_mm: float,
    downsample: int,
    bridge_mm: float = 0.0,
    sat_sensitivity: float = 1.0,
) -> dict:
    row: dict = {col: "" for col in COLUMNS}
    errors: list[str] = []
    row["slide_path"] = str(slide_path)
    row["slide_name"] = slide_path.stem

    t0 = time.perf_counter()

    try:
        slide = open_slide(slide_path)
    except Exception as e:
        row["status"] = "FAIL"
        row["compute_time_s"] = f"{time.perf_counter() - t0:.2f}"
        row["errors"] = f"slide_open:{type(e).__name__}:{e}"
        return row

    try:
        w, h = slide.dimensions
        row["dimensions"] = f"{w}x{h}"

        mpp = get_slide_mpp(slide)
        row["mpp"] = f"{mpp:.4f}"

        min_side_px = min_size_mm * 1000.0 / mpp
        min_area_px2 = min_side_px ** 2

        bridge_px = 0
        if bridge_mm > 0:
            bridge_um = bridge_mm * 1000.0
            bridge_px = max(1, int(round(bridge_um / (mpp * downsample))))

        mask, thumb_size = generate_tissue_mask(slide, downsample, bridge_px, sat_sensitivity)
        regions = extract_tissue_contours(mask, thumb_size, (w, h), min_area_px2)

        row["tissue_regions"] = str(len(regions))

        um_per_mm = 1000.0
        px_to_mm = mpp / um_per_mm

        if regions:
            areas_mm2 = [r["area_px2"] * (px_to_mm ** 2) for r in regions]
            row["total_tissue_area_mm2"] = f"{sum(areas_mm2):.2f}"
            row["min_region_area_mm2"] = f"{min(areas_mm2):.2f}"
            row["max_region_area_mm2"] = f"{max(areas_mm2):.2f}"
        else:
            row["total_tissue_area_mm2"] = "0.00"
            errors.append("no_tissue_detected")

        geojson = regions_to_geojson(regions, mpp, {
            "sat_sensitivity": sat_sensitivity, "min_size_mm": min_size_mm,
            "bridge_mm": bridge_mm, "downsample": downsample, "mpp": round(mpp, 4)})
        geojson_path = output_dir / f"{slide_path.stem}.geojson"
        geojson_path.parent.mkdir(parents=True, exist_ok=True)
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)
        row["geojson_path"] = str(geojson_path)

        row["status"] = "WARN" if not regions else "OK"

    except Exception as e:
        errors.append(f"processing:{type(e).__name__}:{e}")
        row["status"] = "FAIL"
    finally:
        slide.close()

    row["compute_time_s"] = f"{time.perf_counter() - t0:.2f}"
    row["errors"] = "|".join(errors)
    return row


# ---------------------------------------------------------------------------
#  TSV
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Détection et détourage de tissu sur lame entière — export annotation GeoJSON."
    )
    ap.add_argument("input_path", type=Path,
                    help="Dossier racine (récursif) ou lame unique.")
    ap.add_argument("output_dir", type=Path,
                    help="Dossier de sortie pour les GeoJSON et le TSV récapitulatif.")
    ap.add_argument("--min-size-mm", type=float, default=1.0,
                    help="Taille minimale d'un côté de tissu en mm (défaut : 1.0 → aire min ≈ 1 mm²).")
    ap.add_argument("--sat-sensitivity", type=float, default=0.4,
                    help="Facteur de sensibilité du seuil Otsu saturation (défaut : 0.4). "
                         "Valeurs < 1.0 rendent le masque plus permissif "
                         "pour attraper le tissu pâle (mésenchyme, cordon).")
    ap.add_argument("--bridge-mm", type=float, default=0.2,
                    help="Rayon de pontage en mm : fusionne les fragments distants de "
                         "moins de 2× cette valeur (défaut : 0.2).")
    ap.add_argument("--downsample", type=int, default=64,
                    help="Facteur de sous-échantillonnage pour la vignette (défaut : 64).")
    args = ap.parse_args()

    if not args.input_path.exists():
        print(f"[ERREUR] Chemin introuvable : {args.input_path}", file=sys.stderr)
        return 2

    slides = find_slides(args.input_path)
    if not slides:
        print(f"[INFO] Aucune lame trouvée sous {args.input_path}", file=sys.stderr)
        return 0

    bridge_str = f", bridge = {args.bridge_mm} mm" if args.bridge_mm > 0 else ""
    print(
        f"[INFO] {len(slides)} lame(s) à traiter "
        f"(min tissu = {args.min_size_mm} mm × {args.min_size_mm} mm{bridge_str})",
        file=sys.stderr,
    )

    rows: list[dict] = []
    counts: dict[str, int] = {"OK": 0, "WARN": 0, "FAIL": 0}
    for i, slide_path in enumerate(slides, 1):
        try:
            row = process_one_slide(slide_path, args.output_dir,
                                    args.min_size_mm, args.downsample,
                                    args.bridge_mm, args.sat_sensitivity)
        except Exception as e:
            row = {c: "" for c in COLUMNS}
            row["slide_path"] = str(slide_path)
            row["slide_name"] = slide_path.stem
            row["status"] = "FAIL"
            row["errors"] = f"unhandled:{type(e).__name__}:{e}"
        rows.append(row)
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        n = row.get("tissue_regions", "?")
        t = row.get("compute_time_s", "?")
        print(f"[{i}/{len(slides)}] {row['status']:4s}  {n} région(s)  {t}s  {slide_path.name}",
              file=sys.stderr)

    tsv_path = args.output_dir / "tissue_mask_summary.tsv"
    write_tsv(rows, tsv_path)
    print(
        f"[FAIT] OK={counts.get('OK', 0)}  WARN={counts.get('WARN', 0)}  "
        f"FAIL={counts.get('FAIL', 0)}  →  {tsv_path}",
        file=sys.stderr,
    )
    return 1 if counts.get("FAIL", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
