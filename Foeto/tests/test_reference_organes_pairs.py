"""Références Guihard-Costa des organes pairs.

L'article publie poumons, reins et surrénales côté par côté. La paire vaut
moy = G + D et sd = σG + σD. La dispersion d'UN organe (√((σG²+σD²)/2), ou
l'ancien sd/√2) appliquée à la somme double le z — c'est ce qui donnait
+5,41 DS sur des reins à +2,7.
"""

import pytest

from reference_data import (GC_ORGANES, GC_POUMON_INDIVIDUEL, GC_REIN_INDIVIDUEL,
                            GC_SURRENALE_INDIVIDUELLE, MAROUN)

PAIRS = [("poumons", GC_POUMON_INDIVIDUEL),
         ("reins", GC_REIN_INDIVIDUEL),
         ("surrenales", GC_SURRENALE_INDIVIDUELLE)]


@pytest.mark.parametrize("organe,table", PAIRS)
def test_paire_est_la_somme_des_deux_cotes(organe, table):
    for classe, side in table.items():
        pair = GC_ORGANES[classe][organe]
        assert pair["moy"] == pytest.approx(side["D"]["moy"] + side["G"]["moy"], abs=0.011)
        assert pair["sd"] == pytest.approx(side["D"]["sd"] + side["G"]["sd"], abs=0.011)


@pytest.mark.parametrize("organe,table", PAIRS)
def test_les_deux_cotes_sont_releves_et_non_derives(organe, table):
    """Une dérivation moy/2 donnerait D et G rigoureusement identiques."""
    assert any(s["D"] != s["G"] for s in table.values()), organe


def test_valeur_relevee_reins_29_30():
    """Ancrage sur l'article : Guihard-Costa 2002, table 2."""
    assert GC_ORGANES["29-30"]["reins"] == {"moy": 12.9, "sd": 2.74}
    assert GC_REIN_INDIVIDUEL["29-30"] == {"D": {"moy": 6.38, "sd": 1.4},
                                           "G": {"moy": 6.52, "sd": 1.34}}


def test_maroun_pas_de_colonne_decalee_aux_termes_precoces():
    """Le décalage de colonnes du parseur laissait reins/surrénales vides à 12-13 SA."""
    for sa in (12, 13):
        for k in ("kidneys 0 1", "kidneys 2 3", "adrenals 0 1", "adrenals 2 3"):
            assert MAROUN[sa]["Mean"][k] is not None, f"{sa} SA / {k}"
    assert MAROUN[13]["Mean"]["kidneys 0 1"] == 0.3
    assert MAROUN[13]["Mean"]["adrenals 0 1"] == 0.17


# ── Valeurs relevées dans les articles (anti-coquille de saisie) ─────────────
# Trois transpositions de chiffres ont été trouvées ainsi (VT 31-32 : 432,2 au
# lieu de 423,2 — 0,4 DS de biais sur tous les fœtus de 31-32 SA).

from reference_data import GC_MACRO


def test_biometries_corporelles_valeurs_relevees():
    assert GC_MACRO["31-32"]["VT"] == {"moy": 423.2, "sd": 22.6}
    assert GC_MACRO["39-40"]["VC"] == {"moy": 356.5, "sd": 17.9}
    assert GC_MACRO["41-42"]["masse"] == {"moy": 3254.9, "sd": 513.1}


def test_monotonie_des_courbes():
    """Une transposition de chiffres casse presque toujours la croissance."""
    classes = list(GC_MACRO)
    for mesure in ("masse", "VT", "VC", "PC", "pied"):
        vals = [GC_MACRO[c][mesure]["moy"] for c in classes if mesure in GC_MACRO[c]]
        assert vals == sorted(vals), f"{mesure} non monotone : {vals}"
    for organe in ("coeur", "foie", "rate", "pancreas", "thymus",
                   "reins", "poumons", "surrenales"):
        vals = [GC_ORGANES[c][organe]["moy"] for c in classes if organe in GC_ORGANES[c]]
        assert vals == sorted(vals), f"{organe} non monotone : {vals}"


# ── Muller-Brochut 2018 : 12-20 SA, comble le trou sous 13 SA ────────────────

import biometrics
from reference_data import MB_BIOMETRIE, MB_ORGANES


def test_mb_couvre_les_termes_precoces():
    assert set(MB_ORGANES) == set(range(12, 21))
    assert set(MB_BIOMETRIE) == set(range(12, 21))
    # les côtés sont publiés séparément, pas dérivés
    assert MB_ORGANES[16]["Left_Kidney"] != MB_ORGANES[16]["Right_Kidney"]


def test_mb_aucune_cellule_a_ecart_type_nul():
    """Cerebellum 20 SA a sd=0 dans l'article : la cellule doit être écartée,
    pas gardée avec une division par zéro."""
    for sa, tab in list(MB_ORGANES.items()) + list(MB_BIOMETRIE.items()):
        for k, v in tab.items():
            assert v["sd"], f"{sa} SA / {k}"
    assert "Cerebellum" not in MB_BIOMETRIE[20]


def _fetus_16sa():
    frais = {"biometries": {"masse": 98.6, "vc": 115.3, "pc": 120.1, "pied": 20.3,
                            "bip": 34.2, "pt": 102.9}}
    autopsie = {"coeur": {"masse": 0.64}, "thorax": {"thymus": {"masse": 0.12}},
                "digestif": {"foie": {"masse": 4.63}, "rate": {"masse": 0.09}},
                "poumons": {"masse_d": 1.69, "masse_g": 1.44},
                "retroperitoine": {"reins": {"masse_d": 0.35, "masse_g": 0.37},
                                   "surrenales": {"masse_d": 0.22, "masse_g": 0.22}}}
    return frais, autopsie


def test_mb_unites_mm_vers_cm():
    """Un fœtus pile sur la moyenne de l'article doit sortir à 0 DS partout.
    Un facteur 10 oublié sur les longueurs se verrait immédiatement."""
    frais, autopsie = _fetus_16sa()
    mb = biometrics.compute_all(16, frais, autopsie, 0)["muller_brochut"]
    for k, v in mb["mesures"].items():
        assert abs(v["ds"]) < 0.35, f"{k} : {v['ds']} DS"
    for k, v in mb["organes"].items():
        assert abs(v["ds"]) < 0.35, f"{k} : {v['ds']} DS"


def test_mb_seule_reference_sous_13_sa():
    frais, autopsie = _fetus_16sa()
    r12 = biometrics.compute_all(12, frais, autopsie, 0)
    assert not (r12["organes_gc"] or {}).get("organes")   # GC démarre à 13 SA
    assert r12["muller_brochut"]["organes"]               # MB prend le relais
    assert any("Muller-Brochut" in a for a in r12["alertes"])

    r24 = biometrics.compute_all(24, frais, autopsie, 0)
    assert r24["muller_brochut"] == {}                    # au-delà de 20 SA, rien
    assert not any("Muller-Brochut" in a for a in r24["alertes"])
