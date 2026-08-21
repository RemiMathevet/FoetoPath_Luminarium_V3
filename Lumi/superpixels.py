"""Superpixels SLIC servant de géométrie pour peindre des annotations.

Grille de tuiles FIXE. Le superpixel sous le curseur ne doit pas changer quand on zoome ou qu'on
se déplace : la tuile, pas le viewport, est donc l'unité de calcul, et son résultat est mis en
cache en GeoJSON à côté de la lame. Deux visites de la même région rendent les mêmes polygones
avec les mêmes identifiants.

Entrée : une lame + une tuile (col, row). Sortie : un FeatureCollection GeoJSON dont les
coordonnées sont à l'échelle du NIVEAU 0 mais dans le repère du VIEWER (DeepZoom monté avec
limit_bounds=True), donc décalées de (bounds-x, bounds-y) par rapport au niveau 0 de la lame —
même repère que toutes les autres annotations de Lumi.

Usage direct : python superpixels.py <lame.mrxs> [--sp-um 90]  → précalcule toute la lame.
"""

import json
import os
import threading
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage
from skimage.segmentation import slic

from ingest.Preanalytique_integrite_mask import tissue_mask_from_array

# Le masque tissu de prod est calculé à downsample 64 (~11 µm/px) : il dit OÙ est le tissu, il ne
# peut pas porter un superpixel de 90 µm (8 px). On resegmente donc à SP_MPP dans son enveloppe.
SP_MPP = 2.0        # x5 — une villosité de 90 µm y fait 45 px, assez pour un contour propre
SP_TILE = 2048      # côté de la tuile de calcul, en px à SP_MPP (~4 mm)
SP_MARGIN = 96      # marge de lecture : un superpixel à cheval sur la couture est calculé entier
SP_VERSION = 3      # à INCRÉMENTER dès que la géométrie change (SLIC, masque, marge, approxPolyDP,
                    # bounds) : sans ça un cache périmé est resservi en silence sous les mêmes ids
SP_OPEN = 1         # ouverture morphologique du masque. À 2 (recette d'intégrité) elle efface tout
                    # ce qui est plus fin que ~26 µm : 19 158 îlots rayés sur une seule lame.
SP_MASK_DS = 64     # downsample de la vignette où se prend le seuil, comme la recette de prod
SP_SAT_SENS = 0.4   # Otsu est tiré par le parenchyme villeux, très saturé. Sur 26P7161_5_1 il
                    # tombe à 31 alors que la plaque basale est à 21 de médiane : à 1.0 elle est
                    # hors masque (4 % dedans) et donc SANS AUCUN superpixel. À 0.4 elle y entre à
                    # 87 %, pour +1.7 point de masque seulement sur la lame entière.

_THRESH: dict[str, int] = {}


def slide_sat_thresh(slide, slide_path: str) -> int:
    """Seuil de saturation de la LAME, celui de la recette d'intégrité de prod (vignette ds64).

    Mesuré transposable au x5 de SLIC : Otsu de la vignette = 30, Otsu recalculé sur toute la
    lame à 2 µm/px = 34. Le sous-échantillonnage ne déplace pas la statistique de saturation.
    """
    cached = _THRESH.get(slide_path)
    if cached is not None:
        return cached
    w, h = slide.dimensions
    thumb = np.asarray(slide.get_thumbnail((max(1, w // SP_MASK_DS), max(1, h // SP_MASK_DS))).convert("RGB"))
    sat = cv2.cvtColor(thumb, cv2.COLOR_RGB2HSV)[:, :, 1]
    t, _ = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _THRESH[slide_path] = int(t)
    return int(t)


def tile_size_level0(mpp0: float) -> float:
    """Côté d'une tuile en px niveau 0."""
    return SP_TILE * (SP_MPP / mpp0)


def tiles_for_bbox(bbox, mpp0: float):
    """Tuiles de la grille fixe couvrant une bbox (repère viewer, échelle niveau 0)."""
    t0 = tile_size_level0(mpp0)
    x, y, w, h = bbox
    c0, c1 = int(max(0.0, x) // t0), int(max(0.0, x + w) // t0)
    r0, r1 = int(max(0.0, y) // t0), int(max(0.0, y + h) // t0)
    return [(c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def tile_key(sp_um: float, col: int, row: int) -> str:
    return f"{sp_um:g}_{col}_{row}"


def cache_path(slide_path: str, sp_um: float, col: int, row: int) -> Path:
    p = Path(slide_path)
    d = p.parent / "superpixels"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{p.stem}_sp{sp_um:g}v{SP_VERSION}_{col}_{row}.geojson"


def tile_geojson(slide, mpp0, bounds, slide_path, sp_um=90.0, col=0, row=0, use_cache=True):
    """FeatureCollection d'une tuile, depuis le cache disque ou calculé puis mis en cache."""
    cache = cache_path(slide_path, sp_um, col, row)
    if use_cache and cache.exists():
        return json.loads(cache.read_text())

    ds = SP_MPP / mpp0
    t0 = SP_TILE * ds
    m0 = SP_MARGIN * ds
    vx, vy = col * t0, row * t0
    bw = bounds.get("width") or slide.dimensions[0]
    bh = bounds.get("height") or slide.dimensions[1]

    rx, ry = max(0.0, vx - m0), max(0.0, vy - m0)
    rw = min(vx + t0 + m0, float(bw)) - rx
    rh = min(vy + t0 + m0, float(bh)) - ry

    feats = []
    if rw > 0 and rh > 0:
        lvl = slide.get_best_level_for_downsample(ds)
        lds = slide.level_downsamples[lvl]
        n_read = (max(8, int(round(rw / lds))), max(8, int(round(rh / lds))))
        origin = (int(rx) + bounds.get("x", 0), int(ry) + bounds.get("y", 0))
        rgb = np.asarray(slide.read_region(origin, lvl, n_read).convert("RGB"))
        out = (max(8, int(round(rw / ds))), max(8, int(round(rh / ds))))
        if (rgb.shape[1], rgb.shape[0]) != out:
            rgb = cv2.resize(rgb, out, interpolation=cv2.INTER_AREA)

        # fill=False : sinon la chambre intervilleuse est rendue au tissu et SLIC s'y dépense
        mask = tissue_mask_from_array(rgb, fill=False, open_iters=SP_OPEN,
                                      thresh=slide_sat_thresh(slide, slide_path),
                                      sat_sensitivity=SP_SAT_SENS) > 0
        if mask.sum() >= 16:
            n_seg = max(4, int(mask.sum() / (sp_um / SP_MPP) ** 2))
            lab = slic(rgb, n_segments=n_seg, compactness=10.0, sigma=5.0 / SP_MPP,
                       max_num_iter=10, mask=mask, start_label=1, channel_axis=-1)

            # La marge sert à donner du CONTEXTE à SLIC près du bord (sans elle il agglomère
            # contre une frontière arbitraire), mais elle n'ÉMET rien : on recadre sur la tuile
            # propre. Deux tuiles voisines segmentent la même bande de recouvrement chacune de
            # son côté ; sans ce recadrage elles couvrent deux fois les mêmes pixels — mesuré
            # à 16 % des points de couture couverts en double.
            x0, y0 = int(round((vx - rx) / ds)), int(round((vy - ry) / ds))
            x1, y1 = min(lab.shape[1], x0 + SP_TILE), min(lab.shape[0], y0 + SP_TILE)
            lab = lab[y0:y1, x0:x1]
            min_px = 0.1 * (sp_um / SP_MPP) ** 2   # les éclats de bord ne sont pas des objets

            # Contours label par label mais restreints à la boîte de chacun : findContours sur
            # l'image entière pour chaque superpixel coûterait n_labels x toute l'image.
            for i, sl in enumerate(ndimage.find_objects(lab), start=1):
                if sl is None:
                    continue
                sub = (lab[sl] == i).astype(np.uint8)
                if sub.sum() < min_px:
                    continue
                cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cnts:
                    continue
                c = cv2.approxPolyDP(max(cnts, key=cv2.contourArea), 1.5, True).reshape(-1, 2)
                if len(c) < 3:
                    continue
                pts = c + (sl[1].start + x0, sl[0].start + y0)
                ring = [[int(round(rx + px * ds)), int(round(ry + py * ds))] for px, py in pts]
                ring.append(ring[0])
                feats.append({
                    "type": "Feature",
                    "id": f"{sp_um:g}_{col}_{row}_{i}",
                    "properties": {"sp_um": sp_um, "tile": [col, row]},
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                })

    fc = {"type": "FeatureCollection", "features": feats,
          "properties": {"tile": [col, row], "sp_um": sp_um, "frame": "viewer_level0",
                         "sp_mpp": SP_MPP}}
    # Écriture atomique : Flask est threadé et l'utilisateur ouvre plusieurs onglets. Deux
    # requêtes sur la même tuile recalculent la même chose (bénin, SLIC est déterministe) mais
    # sans os.replace un lecteur tomberait sur un JSON à moitié écrit.
    tmp = cache.with_name(f".{cache.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(fc))
    os.replace(tmp, cache)
    return fc


def precompute(slide_path: str, sp_um: float = 90.0, verbose: bool = True) -> int:
    """Remplit le cache pour toute la lame. Retourne le nombre de superpixels écrits."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "embeddings"))
    import embed_multimag as em

    slide = em.open_slide(Path(slide_path))
    props = slide.properties
    mpp0 = float(props.get("openslide.mpp-x", 0)) or 0.25
    bounds = {
        "x": int(props.get("openslide.bounds-x", 0)),
        "y": int(props.get("openslide.bounds-y", 0)),
        "width": int(props.get("openslide.bounds-width", slide.dimensions[0])),
        "height": int(props.get("openslide.bounds-height", slide.dimensions[1])),
    }
    t0 = tile_size_level0(mpp0)
    ncol = int(bounds["width"] // t0) + 1
    nrow = int(bounds["height"] // t0) + 1
    total = 0
    for row in range(nrow):
        for col in range(ncol):
            fc = tile_geojson(slide, mpp0, bounds, slide_path, sp_um, col, row)
            n = len(fc["features"])
            total += n
            if verbose and n:
                print(f"  tuile {col},{row} : {n} superpixels", flush=True)
    if verbose:
        print(f"{Path(slide_path).name} : {total} superpixels sur {ncol}x{nrow} tuiles")
    return total


def _check():
    """Le contrat qui casse tout s'il est faux : la grille ne bouge pas avec le viewport."""
    mpp0 = 0.25
    t0 = tile_size_level0(mpp0)
    assert t0 == SP_TILE * 8.0
    # deux vues différentes qui contiennent le même point tombent sur la même tuile
    inner = [t0 * 3 + 10, t0 * 2 + 10, 50, 50]
    wide = [t0 * 3 - 100, t0 * 2 - 100, 300, 300]
    assert (3, 2) in tiles_for_bbox(inner, mpp0)
    assert (3, 2) in tiles_for_bbox(wide, mpp0)
    assert tiles_for_bbox(inner, mpp0) == [(3, 2)]
    assert set(tiles_for_bbox(wide, mpp0)) == {(2, 1), (3, 1), (2, 2), (3, 2)}
    assert tiles_for_bbox([-500, -500, 10, 10], mpp0) == [(0, 0)]
    assert tile_key(90, 3, 2) == "90_3_2"
    # sans la version dans le nom, un cache périmé serait resservi sous les mêmes ids
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert f"v{SP_VERSION}_" in cache_path(f"{d}/x.mrxs", 90, 1, 2).name
    print("ok")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slide", nargs="?", help="chemin de la lame")
    ap.add_argument("--sp-um", type=float, default=90.0)
    ap.add_argument("--check", action="store_true", help="auto-test de la grille")
    a = ap.parse_args()
    if a.check or not a.slide:
        _check()
    else:
        precompute(a.slide, a.sp_um)
