"""
Mesures automatiques des clichés macro du placenta, en LECTURE SEULE.

La source est la table mesures_auto de macro_annot.db, écrite par
serveur_recherche/mesures_auto.py : segmentation par superpixels DINOv2 et
calibration par la réglette en L. Elle donne la surface de la plaque basale
(face basale) et celle de la plaque choriale (face choriale), en cm².

Domaine de validité : la galette complète. La complétude vient de la PWA ;
ce module ne la juge pas.
"""

import io
import json
import re
import sqlite3
from pathlib import Path

import db

MACRO_DB_SETTING = "macro_annot_db"
DEFAULT_MACRO_DB = "/home/mathevet/Bureau/serveur_recherche/data/macro_annot.db"
MASQUES_SETTING = "macro_masques_dir"
DEFAULT_MASQUES = "/home/mathevet/Bureau/serveur_recherche/data/masques"

# ids de la peinture (serveur_recherche, CLASSES_SP) → couleur de l'overlay, celles de /macro/peindre ;
# fond (3) et membranes (4) restent transparents
COULEURS = {1: (79, 195, 255), 2: (95, 224, 138), 5: (190, 120, 255)}
_PHOTO_FACE = re.compile(r"^(.+)_photo_(basale|choriale)\.jpe?g$", re.I)


def _fr(x: float, nd: int) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def get_mesures(numero_dossier: str) -> dict | None:
    """Surfaces basale et choriale du cas et rapport choriale/basale ; None si absentes."""
    path = db.get_setting(MACRO_DB_SETTING, DEFAULT_MACRO_DB)
    if not numero_dossier or not Path(path).is_file():
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
            row = con.execute("SELECT data FROM mesures_auto WHERE cas = ?", (numero_dossier,)).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    d = json.loads(row[0])
    ch = d.get("choriale") or {}
    b, c = d.get("surface_cm2"), ch.get("surface_cm2")
    if b is None and c is None:
        return None
    r = {
        "surface_basale_cm2": round(b) if b is not None else None,
        "surface_choriale_cm2": round(c) if c is not None else None,
        "segmentation_basale": d.get("segmentation"),
        "segmentation_choriale": ch.get("segmentation"),
        "ratio_chorio_basal": round(c / b, 2) if b and c else None,
    }
    r["ratio_txt"] = _fr(r["ratio_chorio_basal"], 2) if r["ratio_chorio_basal"] is not None else ""
    return r


def masque_de(photo_path: str) -> Path | None:
    """Masque d'étiquettes (PNG uint8, ids de la peinture) du cliché basal ou choral, s'il existe."""
    m = _PHOTO_FACE.match(Path(photo_path).name)
    if not m:
        return None
    f = Path(db.get_setting(MASQUES_SETTING, DEFAULT_MASQUES)) / f"{m.group(1)}_{m.group(2).lower()}.png"
    return f if f.is_file() else None


def regle_de(photo_path: str) -> dict | None:
    """Réglette du cliché, dans le repère pleine résolution orienté EXIF : posée à la main (annot)
    sinon automatique (regle_auto) — même priorité que mesures_auto.py."""
    m = _PHOTO_FACE.match(Path(photo_path).name)
    path = db.get_setting(MACRO_DB_SETTING, DEFAULT_MACRO_DB)
    if not m or not Path(path).is_file():
        return None
    cas, face = m.group(1), m.group(2).lower()
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
            man = con.execute("SELECT data FROM annot WHERE cas=? AND face=?", (cas, face)).fetchone()
            aut = con.execute("SELECT data FROM regle_auto WHERE cas=? AND face=?", (cas, face)).fetchone()
    except sqlite3.Error:
        return None
    rg = json.loads(man[0]).get("regle") if man else None
    if rg and rg.get("C") and rg.get("A") and rg.get("B") and rg.get("source") != "auto":
        return {**rg, "confiance": "manuelle"}
    rg = json.loads(aut[0]) if aut else None
    return rg if rg and rg.get("C") else None


def _trace_regle(img, rg: dict, echelle: float):
    """Axes C→A et C→B, un trait par cm le long de chaque bras (long tous les 5 cm) : ils doivent
    tomber sur les cm imprimés et les bords des cases du damier si la calibration est juste."""
    import numpy as np
    from PIL import ImageDraw

    d = ImageDraw.Draw(img)
    lw = max(1, round(img.size[0] / 400))
    C = np.array(rg["C"], float) * echelle
    for k, lg in (("A", rg.get("la", 10)), ("B", rg.get("lb", 10))):
        u = (np.array(rg[k], float) * echelle - C) / lg            # px par cm le long du bras
        n = np.array([-u[1], u[0]]) / (np.hypot(*u) or 1)
        d.line([tuple(C), tuple(C + u * 16)], fill=(255, 40, 40), width=lw)
        for t in range(0, 17):
            demi = (0.45 if t % 5 == 0 else 0.22) * np.hypot(*u)
            P = C + u * t
            d.line([tuple(P - n * demi), tuple(P + n * demi)], fill=(255, 230, 0) if t % 5 else (255, 40, 40),
                   width=lw)
    r = 3 * lw
    d.ellipse([C[0] - r, C[1] - r, C[0] + r, C[1] + r], outline=(255, 40, 40), width=lw)
    from PIL import ImageFont
    try:                                          # la police par défaut n'a pas les accents
        police = ImageFont.truetype("DejaVuSans-Bold.ttf", max(10, 12 * lw))
    except OSError:
        police = ImageFont.load_default(size=max(10, 12 * lw))
    d.text((C[0] + 4 * lw, C[1] + 4 * lw), f"réglette {rg.get('confiance') or '?'} · traits = 1 cm",
           fill=(255, 40, 40), font=police, stroke_width=max(1, lw // 2), stroke_fill=(255, 255, 255))


def photo_avec_masque(photo_path: str, masque: Path | None, w: int | None = None, h: int | None = None,
                      alpha: float = 0.45, regle: dict | None = None) -> bytes:
    """JPEG du cliché (orienté EXIF, comme lors de la segmentation) fondu avec son masque, et la
    réglette tracée par-dessus. Affichage seulement : le cliché d'origine n'est pas touché."""
    import numpy as np
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
    W0 = img.size[0]
    if w and h:
        img.thumbnail((w, h), Image.LANCZOS)
    if masque:
        lab = np.asarray(Image.open(masque).resize(img.size, Image.NEAREST))
        a = np.asarray(img).astype(np.float32)
        for k, c in COULEURS.items():
            sel = lab == k
            a[sel] = (1 - alpha) * a[sel] + alpha * np.array(c, np.float32)
        img = Image.fromarray(a.astype(np.uint8))
    if regle:
        _trace_regle(img, regle, img.size[0] / W0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


if __name__ == "__main__":
    assert _PHOTO_FACE.match("26P1_photo_basale.jpg").groups() == ("26P1", "basale")
    assert not _PHOTO_FACE.match("26P1_tranches_vue_ensemble.jpg")
    assert _fr(0.976, 2) == "0,98"
    print("ok")
