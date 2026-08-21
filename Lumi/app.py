#!/usr/bin/env python3
"""
FoetoPath MRXS Slide Viewer
Flask server for browsing and viewing Mirax (.mrxs) whole-slide images.
Uses OpenSlide + OpenSeadragon for deep-zoom tile-based viewing.

Usage:
    python app.py                        # Start on port 5000, pick folder in GUI
    python app.py --port 8080            # Custom port
    python app.py --root /path/to/slides # Pre-set root folder
"""

import argparse
import csv
import io
import json
import os
import sqlite3
import sys
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
from flask import Flask, Response, abort, jsonify, render_template, request, send_file
from openslide import OpenSlide, OpenSlideError
from openslide.deepzoom import DeepZoomGenerator
from PIL import Image


import database as db

app = Flask(__name__)


# ── Optional HTTP Basic Auth against hub auth.db (no 2FA) ────────────────────
@lru_cache(maxsize=256)
def _check_credentials(db_path: str, username: str, password: str) -> bool:
    """Verify against hub auth.db (Argon2id, legacy sha256 fallback).
    Cached: a WSI viewer fires many tile requests/s, argon2 must run once per credential."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    row = con.execute("SELECT password, salt FROM users WHERE username=? AND active=1",
                      (username,)).fetchone()
    con.close()
    if not row:
        return False
    stored, salt = row
    if salt == "argon2" or stored.startswith("$argon2"):
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
        try:
            return PasswordHasher().verify(stored, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    import hashlib
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == stored


@app.before_request
def _require_auth():
    db_path = app.config.get("AUTH_DB")
    if not db_path:
        return None
    auth = request.authorization
    if auth and _check_credentials(db_path, auth.username, auth.password or ""):
        return None
    return Response("Authentification requise", 401,
                    {"WWW-Authenticate": 'Basic realm="FoetoPath Lames"'})


# ── Configuration ──────────────────────────────────────────────────────────
TILE_SIZE = 254
TILE_OVERLAP = 1
TILE_FORMAT = "jpeg"
TILE_QUALITY = 80
THUMBNAIL_SIZE = (300, 300)
SP_GRID_MAX = 9          # tuiles de superpixels servies en affichage seul (~1 Mo de geojson pièce)
SLIDE_EXTENSIONS = {".mrxs", ".svs", ".ndpi", ".tiff", ".tif", ".scn", ".bif", ".vms", ".vmu"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tga"}


# ── Tile LRU Cache (in-RAM) ───────────────────────────────────────────────
class TileCache:
    """Thread-safe LRU cache for encoded JPEG tile bytes."""

    def __init__(self, maxsize: int = 400):
        self._cache: OrderedDict[tuple, bytes] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: tuple) -> bytes | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: tuple, data: bytes) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = data
            else:
                if len(self._cache) >= self._maxsize:
                    self._cache.popitem(last=False)
                self._cache[key] = data

    @property
    def size(self) -> int:
        return len(self._cache)


tile_cache = TileCache(maxsize=4000)

_prefetch_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tile-prefetch")


# ── Slide Cache ────────────────────────────────────────────────────────────
@lru_cache(maxsize=10)
def get_slide(slide_path: str) -> OpenSlide:
    """Open and cache an OpenSlide object."""
    return OpenSlide(slide_path)


@lru_cache(maxsize=10)
def get_dz(slide_path: str) -> DeepZoomGenerator:
    """Create and cache a DeepZoomGenerator."""
    slide = get_slide(slide_path)
    return DeepZoomGenerator(slide, tile_size=TILE_SIZE, overlap=TILE_OVERLAP, limit_bounds=True)


# ── CHROMA (normalisation colorimétrique HES optionnelle, ?chroma=1) ────────
_CHROMA_SRC_DIR = Path("/media/SSDsamsung/db/chroma_src")
try:
    sys.path.insert(0, "/home/mathevet/Bureau/FoetoPath_Luminarium/Lumi/embeddings")
    import chroma as _chroma
    _chroma_norm = _chroma.CHROMA(
        json.loads(Path("/home/mathevet/Bureau/chroma/calib_target.json").read_text()))
except Exception:
    _chroma_norm = None


@lru_cache(maxsize=64)
def _chroma_src(path: str) -> dict:
    """Calib source d'une lame : JSON pré-calculé si dispo, sinon NMF à la volée (~6s)."""
    j = _CHROMA_SRC_DIR / f"{Path(path).stem}.json"
    if j.exists():
        return json.loads(j.read_text())
    src = _chroma.auto_calibrate(
        [np.asarray(get_slide(path).get_thumbnail((3000, 3000)).convert("RGB"))])
    _CHROMA_SRC_DIR.mkdir(parents=True, exist_ok=True)
    j.write_text(json.dumps(src))
    return src


def _apply_chroma(tile, path: str, gains=None):
    src = _chroma_src(path)
    sv = src["stain_vectors"]
    arr = _chroma_norm.normalize(
        np.asarray(tile.convert("RGB")),
        np.asarray(src["I0"], float),
        np.column_stack([np.asarray(sv[k], float) for k in ("H", "E", "S")]),
        np.asarray(src["stats"]["mu"], float),
        np.asarray(src["stats"]["sigma"], float),
        gains=gains)
    return Image.fromarray(arr)


def _prefetch_neighbors(path: str, level: int, col: int, row: int) -> None:
    """Pré-charge les 8 tuiles adjacentes en arrière-plan."""
    _prefetch_pool.submit(_do_prefetch, path, level, col, row)


def _do_prefetch(path: str, level: int, col: int, row: int) -> None:
    """Charge les voisines manquantes du cache (batch si Omnissiah)."""
    try:
        dz = get_dz(path)
        max_col, max_row = dz.level_tiles[level]
        needed = []
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                nc, nr = col + dc, row + dr
                if 0 <= nc < max_col and 0 <= nr < max_row:
                    if tile_cache.get((path, level, nc, nr, False, None)) is None:
                        needed.append((nc, nr))
        if not needed:
            return
        for nc, nr in needed:
            try:
                tile = dz.get_tile(level, (nc, nr))
                buf = io.BytesIO()
                tile.save(buf, format=TILE_FORMAT, quality=TILE_QUALITY)
                tile_cache.put((path, level, nc, nr, False, None), buf.getvalue())  # ponytail: prefetch natif seulement
            except Exception:
                pass
    except Exception:
        pass


def find_slides(folder: str) -> list[dict]:
    """Find all supported slide files in a folder."""
    slides = []
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return slides
    for f in sorted(folder_path.iterdir()):
        if f.suffix.lower() in SLIDE_EXTENSIONS and f.is_file():
            slides.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f),
                "extension": f.suffix.lower(),
            })
    return slides


def find_photos(folder: str) -> list[dict]:
    """Find all photo/image files in a folder."""
    photos = []
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return photos
    for f in sorted(folder_path.iterdir()):
        if f.suffix.lower() in PHOTO_EXTENSIONS and f.is_file():
            # Skip very small files (thumbnails, icons)
            try:
                size = f.stat().st_size
                if size < 1024:  # < 1KB
                    continue
            except OSError:
                continue
            photos.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f),
                "extension": f.suffix.lower(),
                "size_kb": round(size / 1024, 1),
            })
    return photos


def find_cases(root: str) -> list[dict]:
    """Find all subfolders (cases) that contain slides or photos."""
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    cases = []
    # Check root itself
    root_slides = find_slides(root)
    root_photos = find_photos(root)
    if root_slides or root_photos:
        cases.append({
            "name": root_path.name,
            "path": str(root_path),
            "slide_count": len(root_slides),
            "photo_count": len(root_photos),
            "is_root": True,
        })

    # Check subfolders
    for d in sorted(root_path.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            slides = find_slides(str(d))
            photos = find_photos(str(d))
            if slides or photos:
                cases.append({
                    "name": d.name,
                    "path": str(d),
                    "slide_count": len(slides),
                    "photo_count": len(photos),
                    "is_root": False,
                })
    return cases


# ── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Main page."""
    return render_template("index.html", default_root=app.config.get("DEFAULT_ROOT", ""))


def get_annotated_stems(root: str) -> set[str]:
    """Find slide stems that have annotation GeoJSON files."""
    ann_dir = Path(root) / "annotations"
    if not ann_dir.is_dir():
        return set()
    return {f.stem for f in ann_dir.iterdir() if f.suffix == ".geojson" and not f.stem.endswith("_macro")}


@app.route("/api/browse", methods=["POST"])
def browse():
    """List cases (subfolders with slides) in a root directory."""
    data = request.get_json()
    root = data.get("root", "")
    if not root or not os.path.isdir(root):
        return jsonify({"error": "Dossier invalide", "cases": []}), 400
    cases = find_cases(root)
    annotated = get_annotated_stems(root)
    for case in cases:
        case_slides = find_slides(case["path"])
        done = sum(1 for s in case_slides if s["name"] in annotated)
        case["annotated_count"] = done
    return jsonify({"cases": cases, "root": root})


@app.route("/api/slides", methods=["POST"])
def slides():
    """List slides and photos in a case folder."""
    data = request.get_json()
    folder = data.get("folder", "")
    root = data.get("root", "")
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Dossier invalide", "slides": [], "photos": []}), 400
    slide_list = find_slides(folder)
    photo_list = find_photos(folder)
    if root:
        annotated = get_annotated_stems(root)
        for s in slide_list:
            s["annotated"] = s["name"] in annotated
    return jsonify({"slides": slide_list, "photos": photo_list, "folder": folder})


@app.route("/api/slide/info", methods=["POST"])
def slide_info():
    """Get slide metadata."""
    data = request.get_json()
    path = data.get("path", "")
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        slide = get_slide(path)
        dz = get_dz(path)
        props = dict(slide.properties)
        mpp_x = float(props.get("openslide.mpp-x", 0))
        mpp_y = float(props.get("openslide.mpp-y", 0))
        return jsonify({
            "dimensions": slide.dimensions,
            "level_count": slide.level_count,
            "level_dimensions": list(slide.level_dimensions),
            "dz_level_count": dz.level_count,
            "tile_size": TILE_SIZE,
            "overlap": TILE_OVERLAP,
            "mpp_x": mpp_x,
            "mpp_y": mpp_y,
            "objective_power": float(props.get("openslide.objective-power", 0) or 0),
            "properties": {k: v for k, v in props.items() if len(v) < 500},
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/slide/dzi", methods=["POST"])
def slide_dzi():
    """Generate DZI XML descriptor for OpenSeadragon."""
    data = request.get_json()
    path = data.get("path", "")
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        dz = get_dz(path)
        resp = dz.get_dzi(TILE_FORMAT)
        return Response(resp, mimetype="application/xml")
    except Exception as e:
        return Response(f"<error>{e}</error>", status=500, mimetype="application/xml")


@app.route("/api/slide/tile/<int:level>/<int:col>_<int:row>.<fmt>")
def slide_tile(level: int, col: int, row: int, fmt: str):
    """Serve a single tile with LRU RAM cache + neighbor prefetch."""
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        abort(404)

    use_chroma = request.args.get("chroma") == "1" and _chroma_norm is not None
    gains = None
    if use_chroma:
        # arrondi 1 décimale : borne la cardinalité du cache sur le drag des sliders
        gains = tuple(round(float(request.args.get(k, 1.0)), 1)
                      for k in ("gh", "ge", "gs", "gk"))
    cache_key = (path, level, col, row, use_chroma, gains)
    cached = tile_cache.get(cache_key)
    if cached is not None:
        return Response(cached, mimetype=f"image/{TILE_FORMAT}",
                        headers={"Cache-Control": "public, max-age=86400"})

    try:
        dz = get_dz(path)
        tile = dz.get_tile(level, (col, row))
        if use_chroma:
            tile = _apply_chroma(tile, path, gains)
        buf = io.BytesIO()
        tile.save(buf, format=TILE_FORMAT, quality=TILE_QUALITY)
        data = buf.getvalue()
        tile_cache.put(cache_key, data)
        _prefetch_neighbors(path, level, col, row)
        return Response(data, mimetype=f"image/{TILE_FORMAT}",
                        headers={"Cache-Control": "public, max-age=86400"})
    except (ValueError, KeyError):
        abort(404)
    except OpenSlideError:
        # une lecture ratée VERROUILLE le handle : tout échoue ensuite, même valide (mesuré
        # sur une lame à pyramide tronquée, le niveau -3 rejoue l'erreur du niveau 0). Sans
        # ça, une seule tuile trop profonde fait tomber la lame entière en noir.
        # ponytail: cache_clear() vide les 10 lames, pas juste celle-ci — lru_cache n'évince
        # pas par clé. Rouvrir coûte quelques ms ; passer à un dict manuel si ça se voit.
        get_dz.cache_clear()
        get_slide.cache_clear()
        abort(404)          # 404 et pas 500 : OSD remonte au niveau parent au lieu d'échouer
    except Exception:
        abort(500)


@app.route("/api/slide/thumbnail")
def slide_thumbnail():
    """Generate a thumbnail for the carousel."""
    path = request.args.get("path", "")
    width = int(request.args.get("w", THUMBNAIL_SIZE[0]))
    height = int(request.args.get("h", THUMBNAIL_SIZE[1]))
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        slide = get_slide(path)
        thumb = slide.get_thumbnail((width, height))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        return Response(buf.read(), mimetype="image/jpeg")
    except Exception as e:
        # Return a placeholder
        img = Image.new("RGB", (width, height), (40, 40, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return Response(buf.read(), mimetype="image/jpeg")


@app.route("/api/slide/label")
def slide_label():
    """Get the label/macro image if available."""
    path = request.args.get("path", "")
    img_type = request.args.get("type", "label")  # label or macro
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        slide = get_slide(path)
        images = slide.associated_images
        if img_type in images:
            img = images[img_type]
            if img.mode == "RGBA":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            return Response(buf.read(), mimetype="image/jpeg")
        abort(404)
    except Exception:
        abort(404)


@app.route("/api/slide/macro/info")
def slide_macro_info():
    """Get macro image dimensions for annotation coordinate mapping."""
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        slide = get_slide(path)
        images = slide.associated_images
        # Try macro first, then label
        for img_type in ("macro", "label"):
            if img_type in images:
                img = images[img_type]
                w, h = img.size
                return jsonify({
                    "type": img_type,
                    "width": w,
                    "height": h,
                    "available_types": list(images.keys()),
                })
        return jsonify({"error": "Pas d'image macro disponible"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Photo Routes ───────────────────────────────────────────────────────────
MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".bmp": "image/bmp", ".webp": "image/webp",
    ".tga": "image/x-tga",
}


@app.route("/api/photo/serve")
def photo_serve():
    """Serve a full-resolution photo."""
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        abort(404)
    ext = Path(path).suffix.lower()
    if ext not in PHOTO_EXTENSIONS:
        abort(403)
    mime = MIME_MAP.get(ext, "image/jpeg")
    try:
        with open(path, "rb") as f:
            data = f.read()
        return Response(data, mimetype=mime)
    except Exception:
        abort(500)


@app.route("/api/photo/thumbnail")
def photo_thumbnail():
    """Generate a thumbnail for a photo."""
    path = request.args.get("path", "")
    width = int(request.args.get("w", 192))
    height = int(request.args.get("h", 192))
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        img = Image.open(path)
        img.thumbnail((width, height), Image.LANCZOS)
        # Convert to RGB if needed (for RGBA/palette images)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        buf_format = "JPEG"
        img.save(buf, format=buf_format, quality=85)
        buf.seek(0)
        return Response(buf.read(), mimetype="image/jpeg")
    except Exception:
        # Placeholder
        img = Image.new("RGB", (width, height), (40, 40, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return Response(buf.read(), mimetype="image/jpeg")


# ── Annotation Routes ──────────────────────────────────────────────────────

def get_annotation_path(root: str, slide_path: str) -> Path:
    """Get the GeoJSON annotation file path for a given slide.
    Stored next to the slide: {slide_dir}/annotations/{slide_stem}.geojson
    """
    slide = Path(slide_path)
    ann_dir = slide.parent / "annotations"
    ann_dir.mkdir(parents=True, exist_ok=True)
    return ann_dir / f"{slide.stem}.geojson"


def get_macro_annotation_path(root: str, slide_path: str) -> Path:
    """Get the GeoJSON annotation file path for a slide's macro image.
    Stored next to the slide: {slide_dir}/annotations/{slide_stem}_macro.geojson
    """
    slide = Path(slide_path)
    ann_dir = slide.parent / "annotations"
    ann_dir.mkdir(parents=True, exist_ok=True)
    return ann_dir / f"{slide.stem}_macro.geojson"


def get_slide_calibration(slide_path: str) -> dict:
    """Extract calibration metadata from a slide."""
    try:
        slide = get_slide(slide_path)
        props = slide.properties
        w, h = slide.dimensions

        # MPP (microns per pixel)
        mpp_x = float(props.get("openslide.mpp-x", 0))
        mpp_y = float(props.get("openslide.mpp-y", 0))

        # Bounds
        bounds_x = int(props.get("openslide.bounds-x", 0))
        bounds_y = int(props.get("openslide.bounds-y", 0))
        bounds_w = int(props.get("openslide.bounds-width", w))
        bounds_h = int(props.get("openslide.bounds-height", h))

        # Objective power
        objective = props.get("openslide.objective-power", "")

        return {
            "dimensions_px": [w, h],
            "mpp_x": mpp_x,
            "mpp_y": mpp_y,
            "bounds": {
                "x": bounds_x,
                "y": bounds_y,
                "width": bounds_w,
                "height": bounds_h,
            },
            "objective_power": objective,
            "vendor": props.get("openslide.vendor", ""),
        }
    except Exception:
        return {}


def update_diagnostics_csv(slide_path: str, tissue_type: str, slide_diagnosis: list):
    """Write/update diagnostics.csv next to the slide."""
    csv_path = Path(slide_path).parent / "diagnostics.csv"
    slide_id = Path(slide_path).stem
    rows = []
    if csv_path.is_file():
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if r.get("slide_id") != slide_id]
    rows.append({
        "slide_id": slide_id,
        "tissue_type": tissue_type,
        "diagnosis": ";".join(slide_diagnosis) if slide_diagnosis else "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    rows.sort(key=lambda r: r["slide_id"])
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["slide_id", "tissue_type", "diagnosis", "updated_at"])
        writer.writeheader()
        writer.writerows(rows)


@app.route("/api/annotations/save", methods=["POST"])
def annotations_save():
    """Save annotations as GeoJSON + SQLite + CSV."""
    data = request.get_json()
    root = data.get("root", "")
    slide_path = data.get("slide_path", "")
    features = data.get("features", [])
    tissue_type = data.get("tissue_type", "")
    slide_diagnosis = data.get("slide_diagnosis", [])

    if not root or not slide_path:
        return jsonify({"error": "Paramètres manquants"}), 400

    calibration = get_slide_calibration(slide_path)
    mpp_x = calibration.get("mpp_x", 0)
    mpp_y = calibration.get("mpp_y", 0)

    geojson_features = []
    for feat in features:
        coords_px = feat.get("coordinates", [])
        props = feat.get("properties", {})

        coords_um = []
        if mpp_x > 0 and mpp_y > 0:
            for ring in coords_px:
                coords_um.append([[pt[0] * mpp_x, pt[1] * mpp_y] for pt in ring])

        geojson_feat = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords_px,
            },
            "properties": {
                **props,
                "tissue_type": tissue_type,
                "coordinates_um": coords_um if coords_um else None,
                "unit_px": "pixels (absolute, level 0)",
                "unit_um": f"micrometers (mpp_x={mpp_x}, mpp_y={mpp_y})" if mpp_x > 0 else None,
            },
        }
        geojson_features.append(geojson_feat)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "slide_name": Path(slide_path).name,
            "slide_path": slide_path,
            "tissue_type": tissue_type,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "generator": "FoetoPath Slide Viewer",
            "slide_diagnosis": slide_diagnosis,
            "annotation_levels": {
                "0": "Label lame",
                "1": "Région (faible G)",
                "2": "Histo (moyen G)",
            },
            **calibration,
        },
        "features": geojson_features,
    }

    try:
        # 1. GeoJSON file
        ann_path = get_annotation_path(root, slide_path)
        with open(ann_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        # 2. CSV diagnostics
        if tissue_type or slide_diagnosis:
            update_diagnostics_csv(slide_path, tissue_type, slide_diagnosis)

        # 3. SQLite database
        conn = db.get_db()
        slide_id = Path(slide_path).stem
        db.upsert_slide(conn, slide_id, Path(slide_path).name,
                        str(Path(slide_path).parent), tissue_type, calibration)
        if slide_diagnosis:
            db.set_annotation_diagnoses(conn, slide_id, slide_diagnosis)
        db.save_annotations(conn, slide_id, tissue_type, features, mpp_x, mpp_y)

        return jsonify({
            "ok": True,
            "path": str(ann_path),
            "feature_count": len(geojson_features),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/annotations/load")
def annotations_load():
    """Load annotations GeoJSON for a slide."""
    root = request.args.get("root", "")
    slide_path = request.args.get("slide_path", "")

    if not root or not slide_path:
        return jsonify({"error": "Paramètres manquants"}), 400

    ann_path = get_annotation_path(root, slide_path)
    if not ann_path.is_file():
        return jsonify({"features": [], "exists": False})

    try:
        with open(ann_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)
        return jsonify({
            "exists": True,
            "path": str(ann_path),
            **geojson,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/heatmap/list")
def heatmap_list():
    """List available heatmap variants for a slide: {stem}__{enc}_x{mag}.json."""
    slide_path = request.args.get("slide_path", "")
    if not slide_path:
        return jsonify({"error": "Paramètres manquants"}), 400
    slide = Path(slide_path)
    hm_dir = slide.parent / "heatmaps"
    variants = sorted(p.name[len(slide.stem) + 2:-5] for p in hm_dir.glob(f"{slide.stem}__*.json"))
    return jsonify({"variants": variants})


@app.route("/api/heatmap/load")
def heatmap_load():
    """Load one heatmap variant for a slide (coords already in viewer frame)."""
    slide_path = request.args.get("slide_path", "")
    variant = request.args.get("variant", "")
    if not slide_path or not variant:
        return jsonify({"error": "Paramètres manquants"}), 400
    slide = Path(slide_path)
    hm_path = slide.parent / "heatmaps" / f"{slide.stem}__{variant}.json"
    if not hm_path.is_file():
        return jsonify({"exists": False, "patches": []})
    try:
        with open(hm_path, "r", encoding="utf-8") as f:
            return jsonify({"exists": True, **json.load(f)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _sp_to_viewer(fc, bx, by):
    """Polygones du cache (niveau 0 absolu) -> repère du viewer (relatif aux bounds)."""
    if not (bx or by):
        return fc
    return {**fc, "features": [
        {**f, "geometry": {**f["geometry"],
                           "coordinates": [[[p[0] - bx, p[1] - by] for p in ring]
                                           for ring in f["geometry"]["coordinates"]]}}
        for f in fc.get("features", [])]}


@app.route("/api/superpixels", methods=["POST"])
def superpixels():
    """Superpixels de la grille fixe couvrant la vue courante (voir superpixels.py).

    La tuile est l'unité de calcul et de cache : le superpixel sous le curseur ne change pas
    quand on zoome. Le client renvoie dans `have` les clés qu'il tient déjà, on ne lui repasse
    que les tuiles manquantes.
    """
    import superpixels as sp

    data = request.get_json() or {}
    slide_path = data.get("slide_path", "")
    bbox = data.get("bbox") or []
    # borné : n_seg varie en 1/sp_um², un POST à sp_um=5 demanderait des centaines de milliers
    # de segments et ferait exploser SLIC en temps comme en mémoire
    sp_um = min(500.0, max(30.0, float(data.get("sp_um", 90))))
    have = set(data.get("have") or [])
    # affichage seul : pas d'outil armé, donc pas de limite de champ ni de calcul à la volée,
    # on ne montre que ce que le cache contient déjà
    grid = bool(data.get("grid"))
    if not slide_path or len(bbox) != 4:
        return jsonify({"error": "Paramètres manquants"}), 400

    try:
        calib = get_slide_calibration(slide_path)
        mpp0 = calib.get("mpp_x", 0) or 0.25
        slide = get_slide(slide_path)
        bounds = calib.get("bounds", {})
        # Le cache est écrit par precompute() à travers OmnissiahSlide, dont .properties n'expose
        # pas openslide.bounds-* : ses coordonnées sont en niveau 0 ABSOLU malgré son étiquette
        # "viewer_level0". Le viewer, lui, est monté en limit_bounds=True et parle relatif aux
        # bounds. Sans cette translation la grille tombe 1,8 mm à droite et 11,8 mm plus bas.
        bx, by = int(bounds.get("x", 0)), int(bounds.get("y", 0))
        abox = [bbox[0] + bx, bbox[1] + by, bbox[2], bbox[3]]
        cand = list(sp.tiles_for_bbox(abox, mpp0))
        message = ""
        if len(cand) > SP_GRID_MAX:
            # Remplace la règle des 4 mm : ce qui coûte n'est pas le champ, c'est le nombre de
            # tuiles. Une tuile pèse ~1 Mo de geojson, et une non calculée ~5 s de SLIC. On garde
            # les plus proches du centre de vue, le reste vient en zoomant.
            cx, cy = abox[0] + abox[2] / 2, abox[1] + abox[3] / 2
            t0 = sp.tile_size_level0(mpp0)
            cand.sort(key=lambda cr: ((cr[0] + 0.5) * t0 - cx) ** 2 + ((cr[1] + 0.5) * t0 - cy) ** 2)
            message = f"{SP_GRID_MAX} tuiles de superpixels sur {len(cand)} — zoomer pour le reste"
            cand = cand[:SP_GRID_MAX]
        keys, tiles, pending, computed = [], [], 0, 0
        for col, row in cand:
            key = sp.tile_key(sp_um, col, row)
            keys.append(key)
            if key in have:
                continue
            if grid:
                p = sp.cache_path(slide_path, sp_um, col, row)
                if p.exists():
                    tiles.append({"key": key, "geojson": _sp_to_viewer(json.loads(p.read_text()),
                                                                      bx, by)})
                continue
            # SLIC coûte ~5 s la tuile. Une vue en couvre jusqu'à quatre : sur une lame non
            # précalculée la requête bloquait 20 s et le proxy rendait 502 avant la réponse.
            # On n'en calcule qu'une par requête, le client redemande tant que pending > 0.
            if not sp.cache_path(slide_path, sp_um, col, row).exists():
                if computed:
                    pending += 1
                    continue
                computed += 1
            fc = sp.tile_geojson(slide, mpp0, bounds, slide_path, sp_um, col, row)
            tiles.append({"key": key, "geojson": _sp_to_viewer(fc, bx, by)})
        return jsonify({"keys": keys, "tiles": tiles, "pending": pending, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/annotations/macro/save", methods=["POST"])
def annotations_macro_save():
    """Save macro image annotations as GeoJSON (coordinates in pixels)."""
    data = request.get_json()
    root = data.get("root", "")
    slide_path = data.get("slide_path", "")
    features = data.get("features", [])
    macro_dimensions = data.get("macro_dimensions", [0, 0])

    if not root or not slide_path:
        return jsonify({"error": "Paramètres manquants"}), 400

    # Build GeoJSON features (coordinates in macro image pixels)
    geojson_features = []
    for feat in features:
        coords_px = feat.get("coordinates", [])
        props = feat.get("properties", {})
        geojson_feat = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords_px,
            },
            "properties": {
                **props,
                "unit": "pixels (macro image)",
            },
        }
        geojson_features.append(geojson_feat)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "slide_name": Path(slide_path).name,
            "slide_path": slide_path,
            "image_type": "macro",
            "macro_dimensions_px": macro_dimensions,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "generator": "FoetoPath Slide Viewer",
        },
        "features": geojson_features,
    }

    try:
        ann_path = get_macro_annotation_path(root, slide_path)
        with open(ann_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)
        return jsonify({
            "ok": True,
            "path": str(ann_path),
            "feature_count": len(geojson_features),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/annotations/macro/load")
def annotations_macro_load():
    """Load macro image annotations GeoJSON."""
    root = request.args.get("root", "")
    slide_path = request.args.get("slide_path", "")

    if not root or not slide_path:
        return jsonify({"error": "Paramètres manquants"}), 400

    ann_path = get_macro_annotation_path(root, slide_path)
    if not ann_path.is_file():
        return jsonify({"features": [], "exists": False})

    try:
        with open(ann_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)
        return jsonify({
            "exists": True,
            "path": str(ann_path),
            **geojson,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/db/stats")
def db_stats():
    """Database statistics (slides, annotations, diagnoses, embeddings)."""
    root = request.args.get("root", "")
    if not root or not os.path.isdir(root):
        return jsonify({"error": "Root invalide"}), 400
    try:
        conn = db.get_db()
        return jsonify(db.stats(conn))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Annotation Report API (for hub CR generation) ────────────────────────

@app.route("/api/annotations/report")
def annotations_report():
    """Structured annotation report for all slides in a folder — used by hub for CR histo."""
    folder = request.args.get("folder", "")
    root = request.args.get("root", folder)
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Dossier invalide"}), 400

    # Resolve FOETO IDs to labels
    label_map = {}
    if os.path.exists(FOETO_DB):
        fconn = sqlite3.connect(FOETO_DB)
        label_map = {r[0]: r[1] for r in fconn.execute("SELECT id, label_fr FROM foeto_terms").fetchall()}
        axis_map = {r[0]: r[1] for r in fconn.execute("SELECT id, axis FROM foeto_terms").fetchall()}
        fconn.close()

    def _resolve(foeto_id):
        foeto_id = str(foeto_id)
        return {"id": foeto_id, "label": label_map.get(foeto_id, foeto_id)}

    def _axis_of(foeto_id):
        base = str(foeto_id).split(".G")[0]
        return axis_map.get(base, "")

    slides = find_slides(folder)
    report = []
    for slide in slides:
        ann_path = get_annotation_path(root, slide["path"])
        entry = {
            "slide": slide["name"],
            "filename": slide["filename"],
            "organs": [],
            "diagnosis": [],
            "retention": [],
            "maturation": [],
            "annotations": [],
        }
        if ann_path.is_file():
            try:
                with open(ann_path, "r", encoding="utf-8") as f:
                    geojson = json.load(f)
                meta = geojson.get("metadata", {})
                tissue = meta.get("tissue_type", "")
                if tissue:
                    entry["organs"] = [t.strip() for t in tissue.split(",") if t.strip()]
                for diag in meta.get("slide_diagnosis", []):
                    ax = _axis_of(diag)
                    if ax == "retention":
                        entry["retention"].append(_resolve(diag))
                    elif ax == "maturation":
                        entry["maturation"].append(_resolve(diag))
                    else:
                        entry["diagnosis"].append(_resolve(diag))
                for feat in geojson.get("features", []):
                    p = feat.get("properties", {})
                    cid = p.get("class_id", "")
                    if cid.startswith("STRUCT:"):
                        continue
                    entry["annotations"].append({
                        "class_id": cid,
                        "label": label_map.get(cid, p.get("label", "")),
                        "level": p.get("level", 0),
                        "tissue_type": p.get("tissue_type", ""),
                        "area_um2": p.get("area_um2"),
                    })
            except Exception:
                pass
        report.append(entry)

    return jsonify({"folder": folder, "slides": report})


# ── Config API (labels from foeto_terms) ─────────────────────────────────

FOETO_DB = os.environ.get("FOETO_DB_PATH", "/home/mathevet/Bureau/foeto_base/syndromes_foetaux.db")


def _load_labels_from_foeto():
    """Read viewer-enabled terms from foeto_terms → lda_classes + quick_picks."""
    if not os.path.exists(FOETO_DB):
        return {}, {}
    conn = sqlite3.connect(FOETO_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT viewer_level, viewer_id, label_fr, viewer_color, viewer_quick, organe "
        "FROM foeto_terms WHERE domain='placenta' AND viewer_level IS NOT NULL "
        "AND viewer_id IS NOT NULL ORDER BY viewer_level, viewer_id"
    ).fetchall()
    conn.close()
    lda = {}
    quick = {}
    for r in rows:
        lvl = str(r["viewer_level"])
        item = {"id": r["viewer_id"], "label": r["label_fr"], "color": r["viewer_color"] or "#999999"}
        lda.setdefault(lvl, []).append(item)
        if r["viewer_quick"]:
            quick.setdefault(r["organe"], []).append(item)
    return lda, quick


@app.route("/api/config/labels")
def api_config_labels():
    lda, quick = _load_labels_from_foeto()
    return jsonify({"lda_classes": lda, "quick_picks": quick})


# ── Foeto terms API (organ-based fetal labels) ────────────────────────────

# Sub-organs: (display_name, parent_organe, keyword_pattern)
_SUB_ORGANS = {
    "thymus":    ("hematolymphoide", "%thym%"),
    "rate":      ("hematolymphoide", "%splén%"),
    "surrenale": ("endocrine",       "%surrén%"),
    "thyroide":  ("endocrine",       "%thyroïd%"),
    "pancreas":  ("digestif",        "%pancré%"),
}


@app.route("/api/foeto/structures")
def api_foeto_structures():
    """Unified anatomical structure list: ?domain=&type= filters."""
    if not os.path.exists(FOETO_DB):
        return jsonify({"structures": []})
    conn = sqlite3.connect(FOETO_DB)
    sql = "SELECT name, domain, type, label_fr FROM foeto_structures"
    clauses, params = [], []
    domain = request.args.get("domain")
    stype = request.args.get("type")
    if domain:
        clauses.append("domain = ?"); params.append(domain)
    if stype:
        clauses.append("type = ?"); params.append(stype)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY sort_order, name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify({"structures": [{"name": r[0], "domain": r[1], "type": r[2], "label": r[3]} for r in rows]})


@app.route("/api/foeto/organs")
def api_foeto_organs():
    """Legacy — redirige vers structures."""
    if not os.path.exists(FOETO_DB):
        return jsonify({"organs": []})
    conn = sqlite3.connect(FOETO_DB)
    rows = conn.execute("SELECT name FROM foeto_structures WHERE domain='foetus' AND type='organe' ORDER BY sort_order, name").fetchall()
    conn.close()
    return jsonify({"organs": [r[0] for r in rows], "sub_organs": list(_SUB_ORGANS.keys())})


@app.route("/api/foeto/grades")
def api_foeto_grades():
    if not os.path.exists(FOETO_DB):
        return jsonify({"grades": {}})
    conn = sqlite3.connect(FOETO_DB)
    rows = conn.execute("SELECT term_id, grade, desc_fr FROM foeto_grades ORDER BY term_id, grade").fetchall()
    conn.close()
    grades = {}
    for term_id, grade, desc_fr in rows:
        grades.setdefault(term_id, []).append({"grade": grade, "desc": desc_fr})
    return jsonify({"grades": grades})


@app.route("/api/foeto/terms")
def api_foeto_terms():
    organs = request.args.get("organs", "")
    if not organs or not os.path.exists(FOETO_DB):
        return jsonify({"terms": {}, "quick": {}})
    organ_list = [o.strip() for o in organs.split(",") if o.strip()]

    conn = sqlite3.connect(FOETO_DB)
    conn.row_factory = sqlite3.Row

    all_rows = []
    real_organs = [o for o in organ_list if o not in _SUB_ORGANS]
    sub_organs = [o for o in organ_list if o in _SUB_ORGANS]

    if real_organs:
        ph = ",".join("?" * len(real_organs))
        all_rows += conn.execute(
            f"SELECT id, organe, label_fr, axis, viewer_quick, type_patho, viewer_level "
            f"FROM foeto_terms WHERE organe IN ({ph}) AND axis IN ('pathologie','retention','maturation') "
            f"ORDER BY organe, axis, label_fr", real_organs
        ).fetchall()

    for sub in sub_organs:
        parent, pattern = _SUB_ORGANS[sub]
        all_rows += [(dict(r), sub) for r in conn.execute(
            "SELECT id, organe, label_fr, axis, viewer_quick, type_patho, viewer_level "
            "FROM foeto_terms WHERE organe=? AND label_fr LIKE ? AND axis IN ('pathologie','retention','maturation') "
            "ORDER BY axis, label_fr", (parent, pattern)
        ).fetchall()]

    conn.close()

    terms = {}
    quick = {}
    retention = {}
    maturation = {}
    for item in all_rows:
        if isinstance(item, tuple):
            r, display_org = item
        else:
            r = dict(item)
            display_org = r["organe"]
        ax = r["axis"]
        tp = r["type_patho"] or ""
        entry = {"id": r["id"], "label": r["label_fr"], "group": tp, "level": r["viewer_level"]}
        if ax == "retention":
            retention.setdefault(display_org, []).append(entry)
        elif ax == "maturation":
            maturation.setdefault(display_org, []).append(entry)
        else:
            terms.setdefault(display_org, {}).setdefault(ax, []).append(entry)
        if r["viewer_quick"]:
            quick.setdefault(display_org, []).append(entry)
    return jsonify({"terms": terms, "quick": quick, "retention": retention, "maturation": maturation})


@app.route("/api/foeto/segments")
def api_foeto_segments():
    """Legacy — structures de type 'structure'."""
    if not os.path.exists(FOETO_DB):
        return jsonify({"segments": []})
    conn = sqlite3.connect(FOETO_DB)
    rows = conn.execute("SELECT name FROM foeto_structures WHERE type='structure' ORDER BY sort_order, name").fetchall()
    conn.close()
    return jsonify({"segments": [r[0] for r in rows]})


@app.route("/api/foeto/tissues")
def api_foeto_tissues():
    """Legacy — structures de type 'tissu'."""
    if not os.path.exists(FOETO_DB):
        return jsonify({"tissues": []})
    conn = sqlite3.connect(FOETO_DB)
    rows = conn.execute("SELECT name FROM foeto_structures WHERE type='tissu' ORDER BY sort_order, name").fetchall()
    conn.close()
    return jsonify({"tissues": [r[0] for r in rows]})


# ── Label API (organ status + notes) ───────────────────────────────────────

@app.route("/api/slide/label-status")
def slide_label_status():
    slide_id = request.args.get("slide_id", "")
    if not slide_id:
        return jsonify({"error": "slide_id requis"}), 400
    conn = db.get_db()
    organs = db.get_organ_statuses(conn, slide_id)
    diagnoses = db.get_diagnoses(conn, slide_id)
    note = db.get_slide_note(conn, slide_id)
    return jsonify({
        "organs": organs,
        "diagnoses": diagnoses,
        "note": note,
        "labeled": len(organs) > 0,
    })


@app.route("/api/slide/label-save", methods=["POST"])
def slide_label_save():
    data = request.get_json()
    slide_id = data.get("slide_id", "")
    slide_path = data.get("slide_path", "")
    organs = data.get("organs", [])
    diagnoses = data.get("diagnoses", [])
    note = data.get("note", "")
    if not slide_id:
        return jsonify({"error": "slide_id requis"}), 400
    conn = db.get_db()
    # Ensure slide exists in DB before FK writes
    if slide_path and os.path.isfile(slide_path):
        calibration = get_slide_calibration(slide_path)
        db.upsert_slide(conn, slide_id, Path(slide_path).name,
                        str(Path(slide_path).parent), "", calibration)
    elif not db.get_slide(conn, slide_id):
        db.upsert_slide(conn, slide_id, slide_id, "", "", {})
    conn.execute("DELETE FROM organ_status WHERE slide_id = ?", (slide_id,))
    for org in organs:
        db.upsert_organ_status(conn, slide_id, org["organ"], org["status"])
    db.set_diagnoses(conn, slide_id, diagnoses)
    if note.strip():
        db.upsert_slide_note(conn, slide_id, note.strip())
    else:
        db.delete_slide_note(conn, slide_id)
    return jsonify({"ok": True, "labeled": len(organs) > 0})


@lru_cache(maxsize=1)
def _foeto_label_map():
    """{foeto_id: (label_fr, organe)} — cached (terms rarely change; restart to refresh)."""
    m = {}
    if os.path.exists(FOETO_DB):
        fc = sqlite3.connect(FOETO_DB)
        for r in fc.execute("SELECT id, label_fr, organe FROM foeto_terms"):
            m[r[0]] = (r[1], r[2])
        fc.close()
    return m


def _split_grade(diag):
    base, sep, g = diag.rpartition(".G")
    return (base, int(g)) if sep and g.isdigit() else (diag, 0)


@app.route("/api/case/index")
def api_case_index():
    """Per-case index: labels (labellisation) + annotations for every slide of a folder."""
    folder = request.args.get("folder", "")
    if not folder:
        return jsonify({"slides": {}})
    conn = db.get_db()
    lm = _foeto_label_map()
    out = {}
    for r in conn.execute("SELECT slide_id FROM slides WHERE folder = ?", (folder,)).fetchall():
        sid = r["slide_id"]
        labels = []
        for d in db.get_diagnoses(conn, sid):
            base, grade = _split_grade(d)
            lbl, org = lm.get(base, (base, ""))
            labels.append({"id": base, "label": lbl, "organ": org, "grade": grade})
        anns = [{"label": a["label"] or a["ann_class"] or "annotation",
                 "color": a["color"], "class": a["ann_class"]}
                for a in db.load_slide_annotations(conn, sid)
                if not (a["ann_class"] or "").startswith("STRUCT:")]
        out[sid] = {"organs": db.get_organ_statuses(conn, sid),
                    "labels": labels, "annotations": anns}
    return jsonify({"slides": out})


@app.route("/api/slides/label-summary")
def slides_label_summary():
    folder = request.args.get("folder", "")
    if not folder:
        return jsonify({"error": "folder requis"}), 400
    conn = db.get_db()
    statuses = db.get_label_summary(conn, folder)
    return jsonify({"statuses": statuses})


@app.route("/api/slides/similar")
def slides_similar():
    diagnosis = request.args.get("diagnosis", "")
    if not diagnosis:
        return jsonify({"error": "diagnosis requis"}), 400
    conn = db.get_db()
    rows = conn.execute("""
        SELECT s.slide_id, s.folder, s.filename
        FROM diagnoses d JOIN slides s ON d.slide_id = s.slide_id
        WHERE d.diagnosis = ? ORDER BY s.folder, s.slide_id
    """, (diagnosis,)).fetchall()
    # Resolve label from foeto_terms
    label = diagnosis
    if os.path.exists(FOETO_DB):
        fconn = sqlite3.connect(FOETO_DB)
        row = fconn.execute("SELECT label_fr FROM foeto_terms WHERE id = ?", (diagnosis,)).fetchone()
        if row:
            label = row[0]
        fconn.close()
    slides = []
    for r in rows:
        organs = [o["organ"] for o in db.get_organ_statuses(conn, r["slide_id"])]
        slides.append({
            "slide_id": r["slide_id"],
            "folder": r["folder"],
            "filename": r["filename"],
            "organs": organs,
        })
    return jsonify({"diagnosis": diagnosis, "label": label, "slides": slides})


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FoetoPath MRXS Slide Viewer")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--root", default="", help="Default root folder for slides")
    parser.add_argument("--auth-db", default="", help="Hub auth.db to require HTTP Basic login (no 2FA)")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    app.config["DEFAULT_ROOT"] = args.root
    app.config["AUTH_DB"] = args.auth_db

    conn = db.get_db()
    db.seed_default_config(conn)

    lda, _qp = _load_labels_from_foeto()
    n = sum(len(v) for v in lda.values())
    # Version check
    local_v = None
    if os.path.exists(FOETO_DB):
        try:
            fc = sqlite3.connect(FOETO_DB)
            fc.row_factory = sqlite3.Row
            row = fc.execute("SELECT value FROM foeto_meta WHERE key='version'").fetchone()
            if row: local_v = row["value"]
            fc.close()
        except Exception: pass
    print(f"  FOETO DB v{local_v or '?'} — {n} classes from foeto_terms")

    print(f"\n{'='*60}")
    print(f"  FoetoPath MRXS Slide Viewer")
    print(f"  http://{args.host}:{args.port}")
    if args.root:
        print(f"  Root: {args.root}")
    print(f"{'='*60}\n")

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
