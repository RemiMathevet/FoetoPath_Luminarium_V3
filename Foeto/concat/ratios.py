"""Ratios diagnostiques pré-calculés pour l'export LLM."""

from typing import Optional

from ._utils import _get, _f


RATIO_SEUILS = {
    # ── Tier 1 : Cranio-faciaux ──
    "index_cephalique": {
        "ratio": "Index céphalique (BIP / FO)",
        "bas": 0.74, "haut": 0.83,
        "signification_bas": "Dolichocéphalie",
        "signification_haut": "Brachycéphalie",
        "hpo_bas": ("HP:0000268", "Dolichocephaly"),
        "hpo_haut": ("HP:0000248", "Brachycephaly"),
        "note": "Seuils valables > 28 SA ; tête plus dolichocéphale en début de grossesse",
    },
    "telecanthus": {
        "ratio": "DICI / FP moyenne",
        "bas": 0.85, "haut": 1.15,
        "signification_bas": "Hypotélorisme",
        "signification_haut": "Télécanthus",
        "hpo_bas": ("HP:0000601", "Hypotelorism"),
        "hpo_haut": ("HP:0000506", "Telecanthus"),
    },
    "femur_pied": {
        "ratio": "Fémur / Pied",
        "bas": 0.85, "haut": 1.10,
        "signification_bas": "Rhizomélie",
        "signification_haut": "Acromélie ou pied court",
        "hpo_bas": ("HP:0000272", "Rhizomelia"),
        "hpo_haut": None,
    },
    # ── Tier 1 : Tronc ──
    "pt_pa": {
        "ratio": "Périmètre thoracique / Périmètre abdominal",
        "bas": 0.85, "haut": 1.05,
        "signification_bas": "Thorax étroit relatif",
        "signification_haut": "Distension abdominale réduite ou thorax globuleux",
        "hpo_bas": ("HP:0000774", "Narrow chest"),
        "hpo_haut": None,
    },
    # ── Tier 1 : Pulmonaires ──
    "lbwr": {
        "ratio": "LBWR (Poumons / Masse corporelle)",
        "bas": 0.018, "haut": 0.035,
        "seuil_critique_bas": 0.012,
        "signification_bas": "Hypoplasie pulmonaire",
        "signification_haut": "Hyperplasie pulmonaire",
        "hpo_bas": ("HP:0002089", "Pulmonary hypoplasia"),
        "hpo_haut": None,
        "note": "Seuil 0.012 = hypoplasie létale (De Paepe 2005). Corréler au RAC.",
    },
    "poumon_d_g": {
        "ratio": "Poumon D / Poumon G",
        "bas": 1.0, "haut": 1.8,
        "signification_bas": "Asymétrie pulmonaire (poumon D plus petit)",
        "signification_haut": "Asymétrie pulmonaire (poumon G plus petit)",
        "hpo_bas": None,
        "hpo_haut": None,
    },
    # ── Tier 1 : Cardiaques ──
    "coeur_masse": {
        "ratio": "Cœur / Masse corporelle",
        "bas": 0.005, "haut": 0.015,
        "signification_bas": "Hypoplasie cardiaque",
        "signification_haut": "Cardiomégalie",
        "hpo_bas": None,
        "hpo_haut": ("HP:0001640", "Cardiomegaly"),
    },
    # ── Tier 1 : Encéphaliques ──
    "cerveau_foie": {
        "ratio": "Cerveau / Foie (Brain-Liver Weight Ratio)",
        "bas": 2.5, "haut": 4.0,
        "signification_bas": "Ratio cerveau/foie diminué",
        "signification_haut": "Ratio cerveau/foie augmenté (brain sparing)",
        "hpo_bas": None,
        "hpo_haut": None,
        "note": "Gruenwald 1963, Shepard 2004. Ratio pour distinguer RCIU vasculaire (augmenté) vs infectieux (diminué).",
    },
    "cerveau_masse": {
        "ratio": "Cerveau / Masse corporelle",
        "bas": None, "haut": None,
        "note": "Interpréter via z-scores individuels. Ratio informatif contextuellement.",
    },
    # ── Tier 1 : Placentaire ──
    "placenta_foetus": {
        "ratio": "Placenta / Masse fœtale",
        "bas": 0.10, "haut": 0.25,
        "signification_bas": "Placenta petit pour le terme",
        "signification_haut": "Placenta gros pour le terme",
        "hpo_bas": None,
        "hpo_haut": None,
    },
    # ── Tier 2 : Rénaux ──
    "reins_masse": {
        "ratio": "Reins (D+G) / Masse corporelle",
        "bas": 0.005, "haut": 0.015,
        "signification_bas": "Hypoplasie rénale",
        "signification_haut": "Néphromégalie",
        "hpo_bas": None,
        "hpo_haut": ("HP:0000105", "Enlarged kidney"),
    },
    "rein_d_g": {
        "ratio": "Rein D / Rein G",
        "bas": 0.7, "haut": 1.4,
        "signification_bas": "Asymétrie rénale (rein D plus petit)",
        "signification_haut": "Asymétrie rénale (rein G plus petit)",
        "hpo_bas": None,
        "hpo_haut": None,
    },
    "rein_surrenale_d": {
        "ratio": "Rein D / Surrénale D",
        "bas": 2.0, "haut": 6.0,
        "signification_bas": "Surrénale D volumineuse ou rein D hypoplasique",
        "signification_haut": "Surrénale D hypoplasique ou rein D augmenté",
        "hpo_bas": None,
        "hpo_haut": None,
    },
    "rein_surrenale_g": {
        "ratio": "Rein G / Surrénale G",
        "bas": 2.0, "haut": 6.0,
        "signification_bas": "Surrénale G volumineuse ou rein G hypoplasique",
        "signification_haut": "Surrénale G hypoplasique ou rein G augmenté",
        "hpo_bas": None,
        "hpo_haut": None,
    },
    # ── Tier 2 : Hépatiques / spléniques ──
    "foie_masse": {
        "ratio": "Foie / Masse corporelle",
        "bas": 0.03, "haut": 0.06,
        "signification_bas": "Atrophie hépatique",
        "signification_haut": "Hépatomégalie",
        "hpo_bas": None,
        "hpo_haut": ("HP:0002240", "Hepatomegaly"),
    },
    "rate_masse": {
        "ratio": "Rate / Masse corporelle",
        "bas": None, "haut": 0.005,
        "signification_haut": "Splénomégalie",
        "hpo_haut": ("HP:0001744", "Splenomegaly"),
    },
    "foie_rate": {
        "ratio": "Foie / Rate",
        "bas": 5.0, "haut": 20.0,
        "signification_bas": "Splénomégalie relative",
        "signification_haut": "Rate atrophique ou asplénie",
        "hpo_bas": None,
        "hpo_haut": None,
    },
    # ── Tier 2 : Surrénaliens ──
    "surrenales_masse": {
        "ratio": "Surrénales (D+G) / Masse corporelle",
        "bas": 0.002, "haut": 0.008,
        "signification_bas": "Hypoplasie surrénalienne",
        "signification_haut": "Hyperplasie surrénalienne",
        "hpo_bas": None,
        "hpo_haut": ("HP:0010475", "Adrenal hyperplasia"),
    },
    # ── Tier 2 : Thymus ──
    "thymus_masse": {
        "ratio": "Thymus / Masse corporelle",
        "bas": 0.001, "haut": 0.010,
        "signification_bas": "Involution thymique",
        "signification_haut": "Thymomégalie",
        "hpo_bas": ("HP:0000778", "Thymic hypoplasia"),
        "hpo_haut": None,
    },
    # ── Tier 3 : Squelettiques radio ──
    "cotes_d_g": {
        "ratio": "Côtes D / Côtes G",
        "bas": None, "haut": None,
        "note": "Différence ≥ 2 → anomalie de segmentation (hémivertèbres, dysostose spondylo-costale).",
    },
}


def _build_one_ratio(name: str, num_param: str, num_val: float,
                     den_param: str, den_val: float) -> Optional[dict]:
    """Construit un objet ratio structuré à partir du nom de config et des valeurs."""
    cfg = RATIO_SEUILS.get(name)
    if cfg is None or num_val is None or den_val is None or den_val == 0:
        return None

    resultat = round(num_val / den_val, 4)

    obj = {
        "ratio": cfg["ratio"],
        "numerateur": {"parametre": num_param, "valeur": num_val},
        "denominateur": {"parametre": den_param, "valeur": den_val},
        "resultat": resultat,
    }

    bas = cfg.get("bas")
    haut = cfg.get("haut")

    if bas is not None and haut is not None:
        obj["seuils"] = {"bas": bas, "haut": haut}
    elif bas is not None:
        obj["seuils"] = {"bas": bas}
    elif haut is not None:
        obj["seuils"] = {"haut": haut}

    if bas is not None and resultat < bas:
        obj["interpretation"] = "anormal_bas"
        sig = cfg.get("signification_bas", "")
        if sig:
            obj["signification_clinique"] = sig
        hpo_info = cfg.get("hpo_bas")
        if hpo_info:
            obj["hpo"] = hpo_info[0]
            obj["hpo_label"] = hpo_info[1]
    elif haut is not None and resultat > haut:
        obj["interpretation"] = "anormal_haut"
        sig = cfg.get("signification_haut", "")
        if sig:
            obj["signification_clinique"] = sig
        hpo_info = cfg.get("hpo_haut")
        if hpo_info:
            obj["hpo"] = hpo_info[0]
            obj["hpo_label"] = hpo_info[1]
    else:
        obj["interpretation"] = "normal"

    if cfg.get("note"):
        obj["note"] = cfg["note"]

    if "seuil_critique_bas" in cfg and resultat < cfg["seuil_critique_bas"]:
        obj["interpretation"] = "critique_bas"
        obj["signification_clinique"] = (
            f"LBWR critique ({resultat:.4f} < {cfg['seuil_critique_bas']})"
        )

    return obj


def _build_ratios_diagnostiques(macro_frais: dict, macro_autopsie: dict,
                                 macro_fixe: dict, neuropath: dict,
                                 radio: dict, masse_corporelle: float,
                                 terme_sa: int) -> list:
    """
    Calcule tous les ratios diagnostiques à partir des données brutes.
    Retourne une liste d'objets ratio (normaux et anormaux).
    """
    ratios = []
    bio = macro_frais.get("biometries", {})

    # ── Tier 1 : Cranio-faciaux ──
    bip = _f(bio.get("bip"))
    fo = _f(bio.get("fo"))
    r = _build_one_ratio("index_cephalique", "BIP (mm)", bip, "FO (mm)", fo)
    if r:
        ratios.append(r)

    dici = _f(bio.get("dici"))
    fpd = _f(bio.get("fpd"))
    fpg = _f(bio.get("fpg"))
    if dici is not None and fpd is not None and fpg is not None:
        fp_moy = round((fpd + fpg) / 2, 2)
        if fp_moy > 0:
            r = _build_one_ratio("telecanthus", "DICI (mm)", dici,
                                 "FP moyenne (mm)", fp_moy)
            if r:
                ratios.append(r)

    pied = _f(bio.get("pied"))
    femur_val = None
    os_longs = _get(radio, "biometries", "os_longs") or {}
    femur_data = os_longs.get("Femur", {})
    if isinstance(femur_data, dict):
        femur_val = _f(femur_data.get("moyenne") or femur_data.get("droite")
                       or femur_data.get("gauche"))
    r = _build_one_ratio("femur_pied", "Fémur (mm)", femur_val, "Pied (mm)", pied)
    if r:
        ratios.append(r)

    # ── Tier 1 : Tronc ──
    pt = _f(bio.get("pt"))
    pa = _f(bio.get("pa"))
    r = _build_one_ratio("pt_pa", "PT (mm)", pt, "PA (mm)", pa)
    if r:
        ratios.append(r)

    # ── Tier 1 : Pulmonaires ──
    poumon_d = _f(_get(macro_autopsie, "poumons", "masse_d"))
    poumon_g = _f(_get(macro_autopsie, "poumons", "masse_g"))
    poumons_total = None
    if poumon_d is not None and poumon_g is not None:
        poumons_total = poumon_d + poumon_g
    elif poumon_d is not None:
        poumons_total = poumon_d
    elif poumon_g is not None:
        poumons_total = poumon_g

    if poumons_total and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("lbwr", "Poumons D+G (g)", poumons_total,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    if poumon_d and poumon_g:
        r = _build_one_ratio("poumon_d_g", "Poumon D (g)", poumon_d,
                             "Poumon G (g)", poumon_g)
        if r:
            ratios.append(r)

    # ── Tier 1 : Cardiaques ──
    coeur_masse = _f(_get(macro_autopsie, "coeur", "masse"))
    if coeur_masse and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("coeur_masse", "Cœur (g)", coeur_masse,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    # ── Tier 1 : Encéphaliques ──
    cerveau = _f(_get(macro_autopsie, "neuro", "masse_cerveau"))
    if cerveau is None:
        cerveau = _f(_get(neuropath, "biometries", "masse_encephale"))
    foie_masse = _f(_get(macro_autopsie, "digestif", "foie", "masse"))

    if cerveau and foie_masse:
        r = _build_one_ratio("cerveau_foie", "Cerveau (g)", cerveau,
                             "Foie (g)", foie_masse)
        if r:
            ratios.append(r)

    if cerveau and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("cerveau_masse", "Cerveau (g)", cerveau,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    # ── Tier 1 : Placentaire ──
    placenta = _f(bio.get("placenta_masse"))
    if not placenta:
        placenta = _f(macro_frais.get("placenta", {}).get("masse"))
    if placenta and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("placenta_foetus", "Placenta (g)", placenta,
                             "Masse fœtale (g)", masse_corporelle)
        if r:
            ratios.append(r)

    # ── Tier 2 : Rénaux ──
    rein_d = _f(_get(macro_autopsie, "retroperitoine", "reins", "masse_d"))
    rein_g = _f(_get(macro_autopsie, "retroperitoine", "reins", "masse_g"))
    surr_d = _f(_get(macro_autopsie, "retroperitoine", "surrenales", "masse_d"))
    surr_g = _f(_get(macro_autopsie, "retroperitoine", "surrenales", "masse_g"))

    reins_total = None
    if rein_d is not None and rein_g is not None:
        reins_total = rein_d + rein_g
    if reins_total and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("reins_masse", "Reins D+G (g)", reins_total,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    if rein_d and rein_g:
        r = _build_one_ratio("rein_d_g", "Rein D (g)", rein_d, "Rein G (g)", rein_g)
        if r:
            ratios.append(r)

    if rein_d and surr_d:
        r = _build_one_ratio("rein_surrenale_d", "Rein D (g)", rein_d,
                             "Surrénale D (g)", surr_d)
        if r:
            ratios.append(r)
    if rein_g and surr_g:
        r = _build_one_ratio("rein_surrenale_g", "Rein G (g)", rein_g,
                             "Surrénale G (g)", surr_g)
        if r:
            ratios.append(r)

    # ── Tier 2 : Hépatiques / spléniques ──
    rate_masse = _f(_get(macro_autopsie, "digestif", "rate", "masse"))

    if foie_masse and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("foie_masse", "Foie (g)", foie_masse,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    if rate_masse and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("rate_masse", "Rate (g)", rate_masse,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    if foie_masse and rate_masse:
        r = _build_one_ratio("foie_rate", "Foie (g)", foie_masse,
                             "Rate (g)", rate_masse)
        if r:
            ratios.append(r)

    # ── Tier 2 : Surrénaliens ──
    surr_total = None
    if surr_d is not None and surr_g is not None:
        surr_total = surr_d + surr_g
    if surr_total and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("surrenales_masse", "Surrénales D+G (g)", surr_total,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    # ── Tier 2 : Thymus ──
    thymus_masse = _f(_get(macro_autopsie, "thorax", "thymus", "masse"))
    if thymus_masse is None:
        fixe_organes = macro_fixe.get("organes", {})
        thymus_fixe = fixe_organes.get("thymus", {})
        if isinstance(thymus_fixe, dict):
            thymus_masse = _f(thymus_fixe.get("masse_fixee"))
    if thymus_masse and masse_corporelle and masse_corporelle > 0:
        r = _build_one_ratio("thymus_masse", "Thymus (g)", thymus_masse,
                             "Masse corporelle (g)", masse_corporelle)
        if r:
            ratios.append(r)

    # ── Tier 3 : Côtes D / G ──
    cotes = radio.get("cotes", {})
    if isinstance(cotes, dict):
        cd = _f(cotes.get("droite"))
        cg = _f(cotes.get("gauche"))
        if cd is not None and cg is not None and cd != cg:
            diff = abs(cd - cg)
            obj = {
                "ratio": "Côtes D - G (différence)",
                "numerateur": {"parametre": "Côtes D", "valeur": cd},
                "denominateur": {"parametre": "Côtes G", "valeur": cg},
                "resultat": diff,
                "seuils": {"anomalie": 2},
            }
            if diff >= 2:
                obj["interpretation"] = "anormal"
                obj["signification_clinique"] = (
                    "Anomalie de segmentation — hémivertèbres homolatérales, "
                    "dysostose spondylo-costale"
                )
            else:
                obj["interpretation"] = "variante_mineure"
            ratios.append(obj)

    return ratios
