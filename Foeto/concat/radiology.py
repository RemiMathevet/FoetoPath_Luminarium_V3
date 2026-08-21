"""Builder de la section radiologie pour l'export LLM."""

from biometrics import interpret_ds

from ._utils import _get, _f
from .hpo import _items_to_findings


def _build_radiologie(radio: dict, terme_sa: int) -> dict:
    """Section radiologie avec discordances staturales (R4)."""
    if not radio:
        return {}

    result = {"terme_reference_sa": terme_sa}

    axial = {}
    vertebres = radio.get("vertebres", {})
    if isinstance(vertebres, dict):
        aspects = vertebres.get("aspects", [])
        if aspects:
            radio_hpo = radio.get("hpo_codes", [])
            axial["rachis"] = _items_to_findings(aspects, radio_hpo)
        if vertebres.get("remarques"):
            axial["rachis_remarques"] = vertebres["remarques"]

    cotes = radio.get("cotes", {})
    if isinstance(cotes, dict) and (cotes.get("droite") or cotes.get("gauche")):
        cotes_obj = {}
        if cotes.get("droite") is not None:
            cotes_obj["droite"] = cotes["droite"]
        if cotes.get("gauche") is not None:
            cotes_obj["gauche"] = cotes["gauche"]
        if cotes.get("droite") and cotes.get("gauche") and cotes["droite"] != cotes["gauche"]:
            cotes_obj["asymetrie"] = True
        axial["cotes"] = cotes_obj

    if radio.get("thorax_forme"):
        axial["thorax_forme"] = radio["thorax_forme"]

    if axial:
        result["squelette_axial"] = axial

    appendiculaire = {}
    aspect_os = radio.get("aspect_os", {})
    if isinstance(aspect_os, dict):
        aspects = aspect_os.get("aspects", [])
        if aspects:
            radio_hpo = radio.get("hpo_codes", [])
            appendiculaire["aspect_os"] = _items_to_findings(aspects, radio_hpo)
        if aspect_os.get("remarques"):
            appendiculaire["aspect_os_remarques"] = aspect_os["remarques"]

    os_longs = _get(radio, "biometries", "os_longs") or {}
    os_list = []
    for os_name, data in os_longs.items():
        if not isinstance(data, dict):
            continue
        for cote in ("droite", "gauche"):
            val = _f(data.get(cote))
            if val is not None:
                entry = {
                    "os": os_name,
                    "cote": cote if data.get("droite") != data.get("gauche") else "bilateral",
                    "longueur_mm": val,
                }
                zs = _f(data.get("zscore_chitty"))
                if zs is not None:
                    entry["zscore_chitty"] = zs
                    entry["interpretation"] = interpret_ds(zs)
                os_list.append(entry)
                break

    if os_list:
        appendiculaire["os_longs"] = os_list
    if appendiculaire:
        result["squelette_appendiculaire"] = appendiculaire

    scores = radio.get("scores_staturaux", {})
    if isinstance(scores, dict) and scores:
        scores_obj = {}
        discordances = []

        hadlock = _f(scores.get("hadlock_sa"))
        adalian = _f(scores.get("adalian_sa"))

        if hadlock is not None:
            scores_obj["hadlock_sa"] = hadlock
            if abs(hadlock - terme_sa) > 3:
                discordances.append(
                    f"Hadlock {'très inférieur' if hadlock < terme_sa else 'supérieur'} "
                    f"au terme ({hadlock} vs {terme_sa} SA)"
                    + (" — RCIU sévère probable" if hadlock < terme_sa - 5 else "")
                )

        if adalian is not None:
            scores_obj["adalian_sa"] = adalian
            if abs(adalian - terme_sa) > 3:
                discordances.append(
                    f"Adalian {'inférieur' if adalian < terme_sa else 'supérieur'} "
                    f"au terme ({adalian} vs {terme_sa} SA)"
                )
            elif hadlock and abs(hadlock - terme_sa) > 3:
                discordances.append(f"Adalian concordant ({adalian} SA)")

        scores_obj["terme_clinique_sa"] = terme_sa
        if discordances:
            scores_obj["discordance"] = " ; ".join(discordances)

        result["scores_staturaux"] = scores_obj

    bio_radio = {}
    bip = _f(_get(radio, "biometries", "bip_osseux_mm"))
    pc = _f(_get(radio, "biometries", "pc_radio_mm"))
    if bip is not None:
        bio_radio["bip_osseux_mm"] = bip
    if pc is not None:
        bio_radio["pc_radio_mm"] = pc
    if bio_radio:
        result["biometries_radio"] = bio_radio

    mat = radio.get("maturation_osseuse", [])
    if mat:
        result["maturation_osseuse"] = mat

    return result
