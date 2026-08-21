"""Builders examen in situ, organes fixés et neuropathologie."""

from biometrics import (
    OrganExtractor,
    sa_to_gc_class, calc_ds, interpret_ds,
)
from reference_data import (
    GC_ORGANES,
    GC_POUMON_INDIVIDUEL, GC_REIN_INDIVIDUEL, GC_SURRENALE_INDIVIDUELLE,
)

from ._utils import _prune, _f, _finding
from .hpo import _lookup_hpo, _parse_comma_list, _items_to_findings


def _build_examen_in_situ(macro_autopsie: dict, all_hpo_findings: list) -> dict:
    """Section examen_in_situ : voies aériennes, thorax, cœur, abdomen."""
    result = {}

    va = macro_autopsie.get("voies_aeriennes", {})
    if isinstance(va, dict) and va.get("detail"):
        items = _parse_comma_list(va["detail"])
        result["voies_aeriennes"] = _items_to_findings(items, all_hpo_findings)

    thorax_data = macro_autopsie.get("thorax", {})
    coeur_data = macro_autopsie.get("coeur", {})
    thorax = {}

    if isinstance(thorax_data, dict):
        thymus = thorax_data.get("thymus", {})
        if isinstance(thymus, dict) and thymus.get("aspect"):
            thorax["thymus_aspect"] = thymus["aspect"]
        pericarde = thorax_data.get("pericarde", [])
        if isinstance(pericarde, list) and pericarde:
            thorax["pericarde"] = pericarde[0] if len(pericarde) == 1 else pericarde

        tsa = thorax_data.get("tsa", {})
        if isinstance(tsa, dict):
            gv_findings = []
            if tsa.get("etat"):
                gv_findings.extend(_items_to_findings(
                    _parse_comma_list(tsa["etat"]), all_hpo_findings))
            if tsa.get("detail"):
                gv_findings.extend(_items_to_findings(
                    _parse_comma_list(tsa["detail"]), all_hpo_findings))
            if gv_findings:
                thorax["gros_vaisseaux"] = gv_findings

    _NORMAL_VALUES = {"normal", "perméable", "permeable", "présent", "present",
                      "ok", "ras", "solitus", "intègre", "integre"}
    gv_extra = []

    if isinstance(coeur_data, dict):
        coeur_in_situ = {}
        for key in ("gros_vx", "crosse", "isthme", "quatre_cav", "foramen_ovale",
                     "sinus_cor"):
            val = coeur_data.get(key)
            if not val:
                continue
            if isinstance(val, str) and val.strip().lower() not in _NORMAL_VALUES:
                desc = f"{key} {val}".strip()
                code, label = _lookup_hpo(desc)
                if not code:
                    code, label = _lookup_hpo(val)
                if code:
                    gv_extra.append(_finding(desc, code, label))
                else:
                    gv_extra.append(_finding(desc, None, None))
            else:
                coeur_in_situ[key] = val

        if coeur_data.get("og_retours"):
            coeur_in_situ["og_retours"] = coeur_data["og_retours"]

        for section_key in ("vd_ej", "vg_ej", "vd_av", "vg_av"):
            section = coeur_data.get(section_key, {})
            if isinstance(section, dict):
                for k, v in section.items():
                    if v:
                        coeur_in_situ[f"{section_key}_{k}"] = v

        if coeur_in_situ:
            thorax["coeur_in_situ"] = coeur_in_situ

    if gv_extra:
        existing_gv = thorax.get("gros_vaisseaux", [])
        thorax["gros_vaisseaux"] = existing_gv + gv_extra

    if thorax:
        result["thorax"] = thorax

    poumons = macro_autopsie.get("poumons", {})
    if isinstance(poumons, dict):
        poumons_is = {}
        morpho = poumons.get("morpho", [])
        if morpho:
            poumons_is["morphologie"] = morpho
        if poumons.get("docimasie") is not None:
            poumons_is["docimasie"] = poumons["docimasie"]
        if poumons_is:
            result["poumons_in_situ"] = poumons_is

    digestif = macro_autopsie.get("digestif", {})
    if isinstance(digestif, dict):
        dig_is = {}
        for sub in ("estomac", "tube_dig"):
            sub_data = digestif.get(sub, {})
            if isinstance(sub_data, dict):
                sub_clean = _prune(sub_data)
                if sub_clean:
                    dig_is[sub] = sub_clean
        if digestif.get("meconium"):
            dig_is["meconium"] = digestif["meconium"]
        if digestif.get("anus"):
            dig_is["anus"] = digestif["anus"]
        if dig_is:
            result["abdomen"] = dig_is

    retro = macro_autopsie.get("retroperitoine", {})
    if isinstance(retro, dict):
        retro_is = {}
        if retro.get("voies_urin"):
            retro_is["voies_urinaires"] = retro["voies_urin"]
        if retro.get("vessie"):
            retro_is["vessie"] = retro["vessie"]
        if retro.get("gonades_pos"):
            retro_is["gonades_position"] = retro["gonades_pos"]
        if retro_is:
            result["retroperitoine"] = retro_is

    neuro = macro_autopsie.get("neuro", {})
    if isinstance(neuro, dict) and neuro.get("detail"):
        result["neuro_in_situ"] = _items_to_findings(
            _parse_comma_list(neuro["detail"]), all_hpo_findings)

    if macro_autopsie.get("commentaire"):
        result["commentaire"] = macro_autopsie["commentaire"]

    return result


def _build_organes_fixes(macro_autopsie: dict, macro_fixe: dict,
                         terme_sa: int, masse_corporelle: float,
                         all_hpo_findings: list) -> dict:
    """
    Section organes_fixes (R3, R6) :
    Un organe n'apparaît QUE s'il a une masse pesée OU une lésion macroscopique.
    Cassettes seules = exclues.
    """
    gc_class = sa_to_gc_class(terme_sa)

    extractor = OrganExtractor(macro_autopsie) if macro_autopsie else None
    masses = extractor.masses if extractor else {}
    combined = extractor.combined if extractor else {}
    individual = extractor.individual_pairs if extractor else {}

    gc_ref = GC_ORGANES.get(gc_class, {}) if gc_class else {}
    gc_indiv = {
        "poumon": GC_POUMON_INDIVIDUEL.get(gc_class, {}),
        "rein": GC_REIN_INDIVIDUEL.get(gc_class, {}),
        "surrenale": GC_SURRENALE_INDIVIDUELLE.get(gc_class, {}),
    }

    fixe_organes = macro_fixe.get("organes", {}) if macro_fixe else {}

    label_map = {
        "coeur": "Cœur", "thymus": "Thymus",
        "poumons": "Poumons (D+G)", "poumon_d": "Poumon droit", "poumon_g": "Poumon gauche",
        "foie": "Foie", "rate": "Rate", "pancreas": "Pancréas",
        "surrenales": "Surrénales (D+G)", "surrenale_d": "Surrénale droite", "surrenale_g": "Surrénale gauche",
        "reins": "Reins (D+G)", "rein_d": "Rein droit", "rein_g": "Rein gauche",
        "cerveau": "Cerveau",
    }

    fixe_to_organ = {
        "thymus": "thymus", "coeur": "coeur",
        "poumon_d": "poumon_d", "poumon_g": "poumon_g",
        "foie": "foie", "rate": "rate", "pancreas": "pancreas",
        "surr_d": "surrenale_d", "surr_g": "surrenale_g",
        "rein_d": "rein_d", "rein_g": "rein_g",
        "tube_dig": "tube_digestif", "annexes": "annexes",
    }

    organes_list = []
    seen_organs = set()

    for org_key in ("coeur", "thymus", "poumons", "foie", "rate", "pancreas",
                    "surrenales", "reins", "cerveau"):
        masse = combined.get(org_key)
        if masse is None:
            continue

        entry = {
            "organe": org_key,
            "label": label_map.get(org_key, org_key),
            "masse_g": masse,
        }

        if org_key in gc_ref:
            r = gc_ref[org_key]
            ds = calc_ds(masse, r["moy"], r["sd"])
            entry["zscore"] = ds
            entry["interpretation"] = interpret_ds(ds)
            entry["reference"] = "Guihard-Costa 2002"

            if ds is not None and abs(ds) > 2:
                direction = "augmenté" if ds > 0 else "diminué"
                if org_key == "coeur" and ds > 2:
                    entry["hpo"] = "HP:0001640"
                    entry["hpo_label"] = "Cardiomegaly"

        if masse_corporelle and masse_corporelle > 0:
            ratio = round(masse / masse_corporelle, 4)
            entry["ratio_masse_corporelle_pct"] = round(ratio * 100, 2)

        if org_key == "poumons" and masse_corporelle and masse_corporelle > 0:
            lbwr = round(masse / masse_corporelle, 4)
            threshold = 0.012 if terme_sa < 28 else 0.015
            entry["lbwr"] = lbwr
            if lbwr < threshold:
                entry["lbwr_alerte"] = f"Hypoplasie pulmonaire (LBWR {lbwr:.4f} < {threshold})"
                entry["hpo"] = "HP:0002089"
                entry["hpo_label"] = "Pulmonary hypoplasia"
            elif lbwr > 0.035:
                entry["lbwr_alerte"] = (
                    f"LBWR très élevé ({lbwr:.4f} > 0.035) — "
                    "compatible avec séquence CHAOS si atrésie laryngée associée"
                )

        seen_organs.add(org_key)
        organes_list.append(entry)

    for org_key in ("poumon_d", "poumon_g", "rein_d", "rein_g",
                    "surrenale_d", "surrenale_g"):
        masse = individual.get(org_key)
        if masse is None:
            continue

        entry = {
            "organe": org_key,
            "label": label_map.get(org_key, org_key),
            "masse_g": masse,
        }

        base = org_key.rsplit("_", 1)[0]
        indiv_ref = gc_indiv.get(base, {})
        if indiv_ref:
            ds = calc_ds(masse, indiv_ref["moy"], indiv_ref["sd"])
            entry["zscore"] = ds
            entry["interpretation"] = interpret_ds(ds)
            entry["reference"] = "Guihard-Costa 2002 (dérivé)"

        seen_organs.add(org_key)
        organes_list.append(entry)

    for fixe_id, fixe_data in fixe_organes.items():
        if not isinstance(fixe_data, dict):
            continue
        lesion_desc = fixe_data.get("lesion_desc")
        masse_fixee = _f(fixe_data.get("masse_fixee"))

        if not lesion_desc and masse_fixee is None:
            continue

        organ_id = fixe_to_organ.get(fixe_id, fixe_id)

        existing = None
        for e in organes_list:
            if e["organe"] == organ_id:
                existing = e
                break

        if existing is None:
            existing = {
                "organe": organ_id,
                "label": label_map.get(organ_id, fixe_id.replace("_", " ").capitalize()),
            }
            organes_list.append(existing)

        if masse_fixee is not None:
            existing["masse_fixee_g"] = masse_fixee
            if masse_corporelle and masse_corporelle > 0 and "ratio_masse_corporelle_pct" not in existing:
                ratio = round(masse_fixee / masse_corporelle, 4)
                existing["ratio_masse_corporelle_pct"] = round(ratio * 100, 2)

        if lesion_desc:
            items = _parse_comma_list(lesion_desc)
            lesions = _items_to_findings(items, all_hpo_findings)
            existing["lesions_macroscopiques"] = lesions

    return {"organes": organes_list} if organes_list else {}


def _build_neuropathologie(neuropath: dict, terme_sa: int,
                           all_hpo_findings: list) -> dict:
    """Section neuropathologie : tranches non vides uniquement."""
    if not neuropath:
        return {}

    result = {"terme_reference_sa": terme_sa}

    encephale = {}
    masse = _f(neuropath.get("biometries", {}).get("masse_encephale"))
    if masse is not None:
        encephale["masse_g"] = masse

    descs = neuropath.get("descriptions", {})
    if isinstance(descs, dict):
        for key, desc in descs.items():
            if not isinstance(desc, dict):
                continue
            status = desc.get("status")
            if status and status.lower() == "normal":
                encephale[key] = "Normal"
            elif status and status.lower() == "anormal":
                code, label = None, None
                key_lower = key.lower()
                for hf in all_hpo_findings:
                    match_fields = [
                        (hf.get("source_field") or "").lower(),
                        (hf.get("source_value") or "").lower(),
                        (hf.get("source") or "").lower(),
                    ]
                    if key_lower in match_fields or any(key_lower in mf for mf in match_fields if mf):
                        code, label = hf["code"], hf.get("term", "")
                        break
                if not code:
                    code, label = _lookup_hpo(key)
                entry = {"status": "Anormal"}
                if desc.get("detail"):
                    entry["detail"] = desc["detail"]
                if code:
                    entry["hpo"] = code
                    entry["hpo_label"] = label
                encephale[key] = entry

    if encephale:
        result["encephale"] = encephale

    bio = neuropath.get("biometries", {})
    if isinstance(bio, dict):
        bio_clean = {}
        for k, v in bio.items():
            if k == "masse_encephale":
                continue
            val = _f(v)
            if val is not None:
                bio_clean[k] = val
        if bio_clean:
            result["biometries_cerebrales"] = bio_clean

    zscores = neuropath.get("zscores", {})
    if isinstance(zscores, dict):
        zs_clean = _prune(zscores)
        if zs_clean:
            result["zscores_cerebraux"] = zs_clean

    cervelet = neuropath.get("cervelet", {})
    if isinstance(cervelet, dict):
        cerv_clean = _prune(cervelet)
        if cerv_clean:
            result["cervelet"] = cerv_clean

    aqueduc = neuropath.get("aqueduc", {})
    if isinstance(aqueduc, dict):
        aq_clean = _prune(aqueduc)
        if aq_clean:
            result["aqueduc"] = aq_clean

    cc = neuropath.get("corps_calleux", {})
    if isinstance(cc, dict):
        cc_clean = _prune(cc)
        if cc_clean:
            result["corps_calleux"] = cc_clean

    oculaire = neuropath.get("oculaire", {})
    if isinstance(oculaire, dict):
        oc_clean = _prune(oculaire)
        if oc_clean:
            result["oculaire"] = oc_clean

    def _filter_tranches(tranches: list) -> list:
        filtered = []
        for t in tranches:
            if not isinstance(t, dict):
                continue
            consts = t.get("constatations", [])
            if not consts:
                continue
            findings = []
            for c in consts:
                code, label = _lookup_hpo(c)
                for hf in all_hpo_findings:
                    if c.lower() in (hf.get("source_value", "").lower(), ""):
                        code = code or hf.get("code")
                        label = label or hf.get("term", "")
                findings.append(_finding(c, code, label))
            filtered.append({
                "tranche": t.get("numero"),
                "constatations": findings,
            })
        return filtered

    coupes = {}
    thd = neuropath.get("tranches_hd", [])
    if isinstance(thd, list):
        thd_filtered = _filter_tranches(thd)
        if thd_filtered:
            coupes["droit"] = thd_filtered

    thg = neuropath.get("tranches_hg", [])
    if isinstance(thg, list):
        thg_filtered = _filter_tranches(thg)
        if thg_filtered:
            coupes["gauche"] = thg_filtered

    if coupes:
        result["coupes_hemispheres"] = coupes

    moelle = neuropath.get("moelle")
    if moelle:
        result["moelle"] = moelle

    return result
