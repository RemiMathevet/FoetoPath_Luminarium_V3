"""Alertes, sémiologie littéraire et détection de contradictions."""

from ._utils import _get, _f


def _build_alertes(biometries: dict, organes: dict, radiologie: dict,
                   examen_externe: dict, ouverture: dict,
                   examen_in_situ: dict = None,
                   ratios_diagnostiques: list = None) -> list:
    """Section alertes enrichies (R9)."""
    alertes = []
    examen_in_situ = examen_in_situ or {}
    ratios_diagnostiques = ratios_diagnostiques or []

    for m in biometries.get("mesures", []):
        if m.get("zscore") is not None and abs(m["zscore"]) > 2:
            param = m["parametre"]
            ds = m["zscore"]
            alertes.append(f"{param.capitalize()} : {ds:+.1f} DS ({m['interpretation']})")

    for org in organes.get("organes", []):
        if org.get("zscore") is not None and abs(org["zscore"]) > 2:
            alertes.append(
                f"{org['label']} : {org['zscore']:+.1f} DS ({org['interpretation']})")
        if org.get("lbwr_alerte"):
            alertes.append(org["lbwr_alerte"])

    # CHAOS : LBWR élevé + atrésie laryngée
    has_lbwr_elevated = any(
        org.get("lbwr") and org["lbwr"] > 0.035
        for org in organes.get("organes", [])
    )
    has_laryngeal_atresia = False
    va = examen_in_situ.get("voies_aeriennes", [])
    if isinstance(va, list):
        for f in va:
            if isinstance(f, dict) and f.get("hpo") == "HP:0008750":
                has_laryngeal_atresia = True
                break
    if not has_laryngeal_atresia and isinstance(va, list):
        for f in va:
            if isinstance(f, dict) and f.get("hpo") == "HP:0008668":
                has_laryngeal_atresia = True
                break
    if has_lbwr_elevated and has_laryngeal_atresia:
        alertes.append(
            "Séquence CHAOS probable : LBWR très élevé + atrésie laryngée"
        )

    disc = _get(radiologie, "scores_staturaux", "discordance")
    if disc:
        alertes.append(f"Discordance staturale : {disc}")

    cotes = _get(radiologie, "squelette_axial", "cotes")
    if isinstance(cotes, dict) and cotes.get("asymetrie"):
        alertes.append(f"Asymétrie costale : {cotes.get('droite', '?')}D / {cotes.get('gauche', '?')}G")

    for r in ratios_diagnostiques:
        interp = r.get("interpretation", "")
        if interp.startswith("anormal") or interp.startswith("critique"):
            sig = r.get("signification_clinique", "")
            ratio_name = r.get("ratio", "")
            val = r.get("resultat", "?")
            if "LBWR" in ratio_name:
                continue
            alertes.append(f"{ratio_name} = {val} — {sig}" if sig else f"{ratio_name} = {val} (anormal)")

    return alertes


def _build_semiologie_litteraire(hpo_codes: set, ratios: list,
                                  organes: dict, radiologie: dict,
                                  biometries: dict) -> list:
    """
    Génère des phrases sémiologiques synthétiques croisant HPO et ratios.
    Règles codées en dur — chaque règle teste des conditions et produit
    une phrase de raisonnement clinique si les conditions sont réunies.
    """
    phrases = []

    ratio_idx = {}
    for r in ratios:
        name = r.get("ratio", "")
        ratio_idx[name] = r

    org_zscores = {}
    for o in organes.get("organes", []):
        if o.get("zscore") is not None:
            org_zscores[o["organe"]] = o["zscore"]

    # ── Règle : CHAOS ──
    lbwr_r = ratio_idx.get("LBWR (Poumons / Masse corporelle)")
    has_laryngeal = "HP:0008668" in hpo_codes or "HP:0008750" in hpo_codes
    if has_laryngeal and lbwr_r and lbwr_r.get("resultat", 0) > 0.035:
        lv = lbwr_r["resultat"]
        phrases.append(
            f"Atrésie laryngée + LBWR {lv:.3f} + cardiomégalie "
            "→ séquence CHAOS"
        )

    # ── Règle : Fractures sans dysplasie squelettique classique ──
    has_fractures = "HP:0002757" in hpo_codes
    has_bowed = "HP:0006487" in hpo_codes
    femur_r = ratio_idx.get("Fémur / Pied")
    thorax_forme = _get(radiologie, "squelette_axial", "thorax_forme")
    if has_fractures and femur_r:
        femur_normal = femur_r.get("interpretation") == "normal"
        thorax_ok = thorax_forme in ("Normal", None)
        if femur_normal and thorax_ok:
            extra = " + os incurvés" if has_bowed else ""
            phrases.append(
                f"Fractures{extra} MAIS fémur de longueur normale et "
                "thorax normal → pas d'OI classique, pas de dysplasie "
                "à thorax étroit"
            )

    # ── Règle : Axe génito-surrénalien ──
    has_ambiguous = "HP:0000062" in hpo_codes
    has_crypto = "HP:0000028" in hpo_codes
    surr_z = org_zscores.get("surrenales")
    surr_r = ratio_idx.get("Surrénales (D+G) / Masse corporelle")
    surr_anormal = (surr_r and surr_r.get("interpretation", "").startswith("anormal"))
    if has_ambiguous and (has_crypto or surr_anormal):
        parts = ["Ambiguïté génitale"]
        if has_crypto:
            parts.append("cryptorchidie")
        if surr_anormal:
            parts.append("surrénales augmentées")
        phrases.append(" + ".join(parts) + " → axe génito-surrénalien")

    # ── Règle : Trouble de migration neuronale ──
    has_heterotopia = "HP:0007165" in hpo_codes
    has_gyration = "HP:0002536" in hpo_codes
    has_ventricul = "HP:0002119" in hpo_codes
    if has_heterotopia or has_gyration:
        neuro_signs = []
        if has_heterotopia:
            neuro_signs.append("Hétérotopie nodulaire")
        if has_gyration:
            neuro_signs.append("gyration anormale")
        if has_ventricul:
            neuro_signs.append("ventriculomégalie")
        if len(neuro_signs) >= 2:
            phrases.append(
                " + ".join(neuro_signs) + " → trouble de migration neuronale"
            )

    # ── Règle : Trouble de segmentation vertébrale ──
    has_hemivert = "HP:0002937" in hpo_codes
    cotes = _get(radiologie, "squelette_axial", "cotes")
    has_cotes_asym = isinstance(cotes, dict) and cotes.get("asymetrie")
    if has_hemivert and has_cotes_asym:
        phrases.append(
            "Hémivertèbres + asymétrie costale → trouble de segmentation "
            "vertébrale"
        )

    # ── Règle : RCIU disharmonieux ──
    masse_z = org_zscores.get("masse") or 0
    mesures = biometries.get("mesures", [])
    vt_normal = False
    pied_normal = False
    for m in mesures:
        param = m.get("parametre", "")
        interp = m.get("interpretation", "")
        if "vertex" in param.lower() or "vt" in param.lower():
            if interp == "normal":
                vt_normal = True
        if "pied" in param.lower():
            if interp == "normal":
                pied_normal = True
    if masse_z < -3 and (vt_normal or pied_normal):
        concordants = []
        if vt_normal:
            concordants.append("VT")
        if pied_normal:
            concordants.append("pied")
        phrases.append(
            f"RCIU sévère en masse ({masse_z:+.1f} DS) mais "
            f"{' et '.join(concordants)} concordant(s) au terme "
            "→ RCIU disharmonieux"
        )

    # ── Règle : Hernie diaphragmatique ──
    has_hernia = "HP:0000776" in hpo_codes
    pd_r = ratio_idx.get("Poumon D / Poumon G")
    if has_hernia and pd_r:
        val = pd_r.get("resultat", 0)
        if val < 1.0:
            phrases.append(
                f"Hernie diaphragmatique + ratio poumon D/G {val:.2f} "
                "(inversé) → hernie droite probable"
            )
        elif val > 1.8:
            phrases.append(
                f"Hernie diaphragmatique + ratio poumon D/G {val:.2f} "
                "(très asymétrique) → hernie gauche avec hypoplasie G"
            )

    # ── Règle : Brain sparing ──
    bl_r = ratio_idx.get("Cerveau / Foie (Brain-Liver Weight Ratio)")
    if bl_r and bl_r.get("interpretation") == "anormal_haut":
        phrases.append(
            f"Ratio cerveau/foie {bl_r['resultat']:.2f} (élevé) "
            "→ brain sparing, RCIU d'origine vasculaire/placentaire"
        )

    # ── Règle : DiGeorge ──
    has_thymic_hypo = "HP:0000778" in hpo_codes
    has_coarctation = "HP:0001680" in hpo_codes
    has_cardio = "HP:0001640" in hpo_codes
    if has_thymic_hypo and (has_coarctation or has_cardio):
        phrases.append(
            "Hypoplasie thymique + cardiopathie conotroncale "
            "→ spectre DiGeorge (del 22q11) à vérifier"
        )

    return phrases


def _build_contradictions(hpo_codes: set, organes: dict, ratios: list,
                          macro_frais: dict, macro_fixe: dict) -> list:
    """
    Détecte les contradictions apparentes dans les données et propose
    des réconciliations.
    """
    contradictions = []

    org_zscores = {}
    for o in organes.get("organes", []):
        org_zscores[o.get("organe", "")] = o

    # ── Contradiction : HPO "Enlarged" + zscore < -2 ──
    enlarged_hpo = {
        "HP:0000105": "reins",
        "HP:0002240": "foie",
        "HP:0001744": "rate",
    }
    for code, organ_key in enlarged_hpo.items():
        if code in hpo_codes:
            org = org_zscores.get(organ_key, {})
            z = org.get("zscore")
            if z is not None and z < -2:
                contradictions.append({
                    "probleme": (
                        f"HPO '{code}' (augmentation) + z-score "
                        f"{organ_key} {z:+.1f} DS (diminué)"
                    ),
                    "reconciliation": (
                        f"Organe kystique/pathologique : volume "
                        f"augmenté (aspect gros) mais masse faible "
                        f"(parenchyme détruit remplacé par liquide)"
                    ),
                })

    # ── Contradiction : asymétrie FP > 30% ──
    bio = macro_frais.get("biometries", {})
    fpd = _f(bio.get("fpd"))
    fpg = _f(bio.get("fpg"))
    if fpd and fpg and fpd > 0 and fpg > 0:
        ratio_fp = max(fpd, fpg) / min(fpd, fpg)
        if ratio_fp > 1.3:
            contradictions.append({
                "probleme": (
                    f"FPD {fpd}mm vs FPG {fpg}mm — asymétrie "
                    f"majeure ({ratio_fp:.0%})"
                ),
                "reconciliation": (
                    "Le ratio DICI/FP moyenne est biaisé par "
                    "l'asymétrie. Le vrai signe est l'asymétrie "
                    "des fentes palpébrales (blépharophimosis "
                    "unilatérale ?). Calculer DICI/FPG et "
                    "DICI/FPD séparément."
                ),
            })

    # ── Contradiction : masse_fixee utilisée au lieu de masse_g ──
    fixe_organes = macro_fixe.get("organes", {}) if isinstance(macro_fixe, dict) else {}
    for fixe_id, fixe_data in fixe_organes.items():
        if not isinstance(fixe_data, dict):
            continue
        mf = _f(fixe_data.get("masse_fixee"))
        if mf is not None and mf > 10:
            org = org_zscores.get(fixe_id, {})
            if not org.get("masse_g") and mf > 0:
                contradictions.append({
                    "probleme": (
                        f"{fixe_id.capitalize()} : masse fixée "
                        f"{mf}g utilisée (pas de masse fraîche)"
                    ),
                    "reconciliation": (
                        "La fixation augmente la masse de ~10-20%. "
                        "Les ratios calculés sur cette masse sont "
                        "surestimés. Interpréter avec prudence."
                    ),
                })

    # ── Contradiction : cardiomégalie massive ──
    coeur = org_zscores.get("coeur", {})
    coeur_z = coeur.get("zscore")
    if coeur_z and coeur_z > 5:
        contradictions.append({
            "probleme": (
                f"Cardiomégalie extrême (z-score {coeur_z:+.1f} DS)"
            ),
            "reconciliation": (
                "Vérifier : artefact de pesée (péricarde inclus ?), "
                "rhabdomyome, épanchement péricardique non drainé. "
                "Si confirmé → cardiopathie majeure ou tumeur cardiaque."
            ),
        })

    return contradictions
