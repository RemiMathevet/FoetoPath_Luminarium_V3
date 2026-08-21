#!/usr/bin/env python3
"""
FoetoPath — Données de référence biométriques.

Sources :
  - Guihard-Costa 2002 : biométries macroscopiques + masses d'organes (classes bi-hebdomadaires)
  - Maroun 2017 : biométries + organes par SA (12–43 SA), stratifié par macération
  - Muller-Brochut 2018 : organes 12–20 SA

Format uniforme : {"moy": float, "sd": float}
Pour les organes stratifiés Maroun : {"moy": float, "sd": float} par grade de macération.

Mise à jour : ajouter/modifier les dicts ci-dessous, le moteur de calcul s'adapte.
"""

# ══════════════════════════════════════════════════════════════════════════
# GUIHARD-COSTA 2002 — Biométries macroscopiques
# Classes bi-hebdomadaires. Unités : masse(g), VT/VC/PC(mm), pied(mm)
# ══════════════════════════════════════════════════════════════════════════

GC_MACRO = {
    "13-14": {"masse": {"moy": 55.8, "sd": 14.4}, "VT": {"moy": 131.8, "sd": 15.4}, "VC": {"moy": 89.6, "sd": 11.7}, "PC": {"moy": 89.2, "sd": 11.8}, "pied": {"moy": 14, "sd": 2.9}},
    "15-16": {"masse": {"moy": 108.6, "sd": 24.7}, "VT": {"moy": 170.4, "sd": 16.2}, "VC": {"moy": 116.2, "sd": 12.2}, "PC": {"moy": 116.7, "sd": 12.2}, "pied": {"moy": 19, "sd": 3}},
    "17-18": {"masse": {"moy": 176.1, "sd": 39}, "VT": {"moy": 207.4, "sd": 17}, "VC": {"moy": 141.7, "sd": 12.7}, "PC": {"moy": 142.8, "sd": 12.6}, "pied": {"moy": 25, "sd": 3.2}},
    "19-20": {"masse": {"moy": 267.7, "sd": 57.1}, "VT": {"moy": 242.9, "sd": 17.8}, "VC": {"moy": 166.2, "sd": 13.1}, "PC": {"moy": 167.5, "sd": 12.9}, "pied": {"moy": 30, "sd": 3.3}},
    "21-22": {"masse": {"moy": 392.7, "sd": 79.2}, "VT": {"moy": 276.8, "sd": 18.6}, "VC": {"moy": 189.8, "sd": 13.6}, "PC": {"moy": 190.9, "sd": 13.3}, "pied": {"moy": 36, "sd": 3.5}},
    "23-24": {"masse": {"moy": 559.6, "sd": 105.1}, "VT": {"moy": 309.2, "sd": 19.4}, "VC": {"moy": 212.3, "sd": 14.1}, "PC": {"moy": 212.8, "sd": 13.7}, "pied": {"moy": 42, "sd": 3.6}},
    "25-26": {"masse": {"moy": 773.9, "sd": 134.9}, "VT": {"moy": 340, "sd": 20.2}, "VC": {"moy": 233.8, "sd": 14.6}, "PC": {"moy": 233.4, "sd": 14}, "pied": {"moy": 48, "sd": 3.8}},
    "27-28": {"masse": {"moy": 1038.2, "sd": 168.6}, "VT": {"moy": 369.3, "sd": 21}, "VC": {"moy": 254.4, "sd": 15.1}, "PC": {"moy": 252.7, "sd": 14.4}, "pied": {"moy": 53, "sd": 3.9}},
    "29-30": {"masse": {"moy": 1350.4, "sd": 206.1}, "VT": {"moy": 397, "sd": 21.8}, "VC": {"moy": 273.9, "sd": 15.5}, "PC": {"moy": 270.5, "sd": 14.8}, "pied": {"moy": 58, "sd": 4.1}},
    "31-32": {"masse": {"moy": 1702.5, "sd": 247.6}, "VT": {"moy": 432.2, "sd": 22.6}, "VC": {"moy": 292.4, "sd": 16}, "PC": {"moy": 287, "sd": 15.1}, "pied": {"moy": 63, "sd": 4.2}},
    "33-34": {"masse": {"moy": 2080.2, "sd": 292.9}, "VT": {"moy": 447.8, "sd": 23.4}, "VC": {"moy": 309.9, "sd": 16.5}, "PC": {"moy": 302.1, "sd": 15.5}, "pied": {"moy": 67, "sd": 4.4}},
    "35-36": {"masse": {"moy": 2460.8, "sd": 342.1}, "VT": {"moy": 470.9, "sd": 24.2}, "VC": {"moy": 326.5, "sd": 17}, "PC": {"moy": 315.8, "sd": 15.9}, "pied": {"moy": 71, "sd": 4.6}},
    "37-38": {"masse": {"moy": 2813.1, "sd": 395.3}, "VT": {"moy": 492.5, "sd": 24.9}, "VC": {"moy": 342, "sd": 17.5}, "PC": {"moy": 328.1, "sd": 16.2}, "pied": {"moy": 74, "sd": 4.7}},
    "39-40": {"masse": {"moy": 3095.1, "sd": 452.2}, "VT": {"moy": 512.5, "sd": 25.7}, "VC": {"moy": 356, "sd": 17.9}, "PC": {"moy": 339.1, "sd": 16.6}, "pied": {"moy": 76, "sd": 4.9}},
    "41-42": {"masse": {"moy": 3254.9, "sd": 531.1}, "VT": {"moy": 530.9, "sd": 26.5}, "VC": {"moy": 370, "sd": 18.4}, "PC": {"moy": 348.6, "sd": 17}, "pied": {"moy": 77, "sd": 5.1}},
}


# ══════════════════════════════════════════════════════════════════════════
# GUIHARD-COSTA 2002 — Masses d'organes COMBINÉS (g)
# Poumons = D+G, Reins = D+G, Surrénales = D+G
# ══════════════════════════════════════════════════════════════════════════

GC_ORGANES = {
    "13-14": {"thymus": {"moy": 0.09, "sd": 0.07}, "coeur": {"moy": 0.24, "sd": 0.13}, "poumons": {"moy": 1.26, "sd": 0.25}, "foie": {"moy": 3.09, "sd": 0.27}, "rate": {"moy": 0.06, "sd": 0.04}, "pancreas": {"moy": 0.09, "sd": 0.01}, "surrenales": {"moy": 0.29, "sd": 0.06}, "reins": {"moy": 0.41, "sd": 0.11}},
    "15-16": {"thymus": {"moy": 0.17, "sd": 0.12}, "coeur": {"moy": 0.82, "sd": 0.23}, "poumons": {"moy": 2.99, "sd": 0.54}, "foie": {"moy": 5.81, "sd": 1.71}, "rate": {"moy": 0.12, "sd": 0.08}, "pancreas": {"moy": 0.28, "sd": 0.08}, "surrenales": {"moy": 0.56, "sd": 0.10}, "reins": {"moy": 0.71, "sd": 0.18}},
    "17-18": {"thymus": {"moy": 0.31, "sd": 0.19}, "coeur": {"moy": 1.44, "sd": 0.37}, "poumons": {"moy": 5.09, "sd": 0.91}, "foie": {"moy": 9.39, "sd": 3.33}, "rate": {"moy": 0.23, "sd": 0.13}, "pancreas": {"moy": 0.42, "sd": 0.16}, "surrenales": {"moy": 0.91, "sd": 0.16}, "reins": {"moy": 1.38, "sd": 0.27}},
    "19-20": {"thymus": {"moy": 0.53, "sd": 0.3}, "coeur": {"moy": 2.21, "sd": 0.56}, "poumons": {"moy": 7.68, "sd": 1.34}, "foie": {"moy": 14.33, "sd": 5.15}, "rate": {"moy": 0.38, "sd": 0.2}, "pancreas": {"moy": 0.57, "sd": 0.24}, "surrenales": {"moy": 1.32, "sd": 0.23}, "reins": {"moy": 2.41, "sd": 0.38}},
    "21-22": {"thymus": {"moy": 0.87, "sd": 0.45}, "coeur": {"moy": 3.23, "sd": 0.79}, "poumons": {"moy": 10.84, "sd": 1.84}, "foie": {"moy": 21, "sd": 7.15}, "rate": {"moy": 0.62, "sd": 0.29}, "pancreas": {"moy": 0.78, "sd": 0.34}, "surrenales": {"moy": 1.79, "sd": 0.32}, "reins": {"moy": 3.84, "sd": 0.53}},
    "23-24": {"thymus": {"moy": 1.35, "sd": 0.64}, "coeur": {"moy": 4.55, "sd": 1.07}, "poumons": {"moy": 14.65, "sd": 2.39}, "foie": {"moy": 29.63, "sd": 9.35}, "rate": {"moy": 0.96, "sd": 0.42}, "pancreas": {"moy": 1.08, "sd": 0.45}, "surrenales": {"moy": 2.33, "sd": 0.41}, "reins": {"moy": 5.64, "sd": 0.70}},
    "25-26": {"thymus": {"moy": 2.01, "sd": 0.89}, "coeur": {"moy": 6.21, "sd": 1.39}, "poumons": {"moy": 19.09, "sd": 2.98}, "foie": {"moy": 40.27, "sd": 11.75}, "rate": {"moy": 1.44, "sd": 0.59}, "pancreas": {"moy": 1.47, "sd": 0.57}, "surrenales": {"moy": 2.92, "sd": 0.51}, "reins": {"moy": 7.78, "sd": 0.90}},
    "27-28": {"thymus": {"moy": 2.92, "sd": 1.21}, "coeur": {"moy": 8.2, "sd": 1.76}, "poumons": {"moy": 24.15, "sd": 3.61}, "foie": {"moy": 52.89, "sd": 14.33}, "rate": {"moy": 2.09, "sd": 0.8}, "pancreas": {"moy": 1.98, "sd": 0.7}, "surrenales": {"moy": 3.57, "sd": 0.61}, "reins": {"moy": 10.22, "sd": 1.12}},
    "29-30": {"thymus": {"moy": 4.14, "sd": 1.61}, "coeur": {"moy": 10.48, "sd": 2.17}, "poumons": {"moy": 29.79, "sd": 4.27}, "foie": {"moy": 67.29, "sd": 17.1}, "rate": {"moy": 2.95, "sd": 1.06}, "pancreas": {"moy": 2.58, "sd": 0.84}, "surrenales": {"moy": 4.3, "sd": 0.72}, "reins": {"moy": 12.9, "sd": 1.37}},
    "31-32": {"thymus": {"moy": 5.72, "sd": 2.1}, "coeur": {"moy": 12.98, "sd": 2.63}, "poumons": {"moy": 35.9, "sd": 4.94}, "foie": {"moy": 83.1, "sd": 20.07}, "rate": {"moy": 4.08, "sd": 1.39}, "pancreas": {"moy": 3.26, "sd": 0.98}, "surrenales": {"moy": 5.08, "sd": 0.82}, "reins": {"moy": 15.73, "sd": 1.65}},
    "33-34": {"thymus": {"moy": 7.75, "sd": 2.7}, "coeur": {"moy": 15.6, "sd": 3.14}, "poumons": {"moy": 42.36, "sd": 5.62}, "foie": {"moy": 99.87, "sd": 23.23}, "rate": {"moy": 5.53, "sd": 1.78}, "pancreas": {"moy": 3.97, "sd": 1.14}, "surrenales": {"moy": 5.93, "sd": 0.92}, "reins": {"moy": 18.62, "sd": 1.96}},
    "35-36": {"thymus": {"moy": 10.33, "sd": 3.42}, "coeur": {"moy": 18.21, "sd": 3.69}, "poumons": {"moy": 48.98, "sd": 6.30}, "foie": {"moy": 116.97, "sd": 26.58}, "rate": {"moy": 7.35, "sd": 2.25}, "pancreas": {"moy": 4.66, "sd": 1.31}, "surrenales": {"moy": 6.83, "sd": 1.01}, "reins": {"moy": 21.46, "sd": 2.29}},
    "37-38": {"thymus": {"moy": 13.54, "sd": 4.27}, "coeur": {"moy": 20.63, "sd": 4.28}, "poumons": {"moy": 55.59, "sd": 6.98}, "foie": {"moy": 133.64, "sd": 30.12}, "rate": {"moy": 9.63, "sd": 2.82}, "pancreas": {"moy": 5.26, "sd": 1.49}, "surrenales": {"moy": 7.79, "sd": 1.09}, "reins": {"moy": 24.12, "sd": 2.65}},
    "39-40": {"thymus": {"moy": 17.5, "sd": 5.27}, "coeur": {"moy": 22.68, "sd": 4.92}, "poumons": {"moy": 61.94, "sd": 7.64}, "foie": {"moy": 148.97, "sd": 33.85}, "rate": {"moy": 12.43, "sd": 3.48}, "pancreas": {"moy": 5.71, "sd": 1.67}, "surrenales": {"moy": 8.83, "sd": 1.17}, "reins": {"moy": 26.45, "sd": 3.04}},
    "41-42": {"thymus": {"moy": 22.34, "sd": 6.44}, "coeur": {"moy": 24.49, "sd": 5.58}, "poumons": {"moy": 67.6, "sd": 8.28}, "foie": {"moy": 161.94, "sd": 37.78}, "rate": {"moy": 15.85, "sd": 4.25}, "pancreas": {"moy": 5.9, "sd": 1.87}, "surrenales": {"moy": 9.92, "sd": 1.22}, "reins": {"moy": 28.28, "sd": 3.45}},
}


# ══════════════════════════════════════════════════════════════════════════
# GUIHARD-COSTA 2002 — Organes PAIRS individuels
# TODO: à compléter avec les données publiées si disponibles.
# En attendant, on dérive depuis les données combinées :
#   moy_individuel = moy_combiné / 2
#   sd_individuel  = sd_combiné / sqrt(2)   (indépendance supposée)
# Ce fichier sera le seul à modifier quand les vraies données seront ajoutées.
# ══════════════════════════════════════════════════════════════════════════

import math as _math

def _derive_individual(combined_table: dict, organ_key: str) -> dict:
    """Dérive les références individuelles depuis les combinées (moy/2, sd/√2)."""
    result = {}
    for classe, organs in combined_table.items():
        if organ_key in organs:
            ref = organs[organ_key]
            result[classe] = {
                "moy": round(ref["moy"] / 2, 4),
                "sd": round(ref["sd"] / _math.sqrt(2), 4),
            }
    return result

# Organes pairs dérivés — remplacer par les vraies données quand disponibles
GC_POUMON_INDIVIDUEL = _derive_individual(GC_ORGANES, "poumons")
GC_REIN_INDIVIDUEL = _derive_individual(GC_ORGANES, "reins")
GC_SURRENALE_INDIVIDUELLE = _derive_individual(GC_ORGANES, "surrenales")


# ══════════════════════════════════════════════════════════════════════════
# MAROUN 2017 — par SA, stratifié par macération (0-1, 2, 3)
# Données complètes 12–43 SA. Format: {SA: {"Mean": {...}, "SD": {...}}}
# ══════════════════════════════════════════════════════════════════════════

MAROUN = {
    12: {"Mean": {"FL": 9, "CR": 7.4, "CH": 9.8, "HDC": 7.1, "Body": 29.6, "brain": 4.8, "heart": 0.1, "lungs 0 1": 0.6, "lungs 2 3": 0.9, "liver 0 1": 1.5, "liver 2": 1.4, "liver 3": 1.3, "thymus 0 1": 0.03, "thymus 2": 0.01, "thymus 3": 0.25, "spleen 0 1": 0.19, "spleen 2 3": 0.04, "kidneys 0 1": 0.11, "kidneys 2 3": None, "adrenals 0 1": None, "adrenals 2 3": None}, "SD": {"FL": 3, "CR": 1.1, "CH": 1.7, "HDC": 1.1, "Body": 14.9, "brain": 1.4, "heart": 0.14, "lungs 0 1": 0.9, "lungs 2 3": 0.9, "liver 0 1": 1.2, "liver 2": 1.2, "liver 3": 1.2, "thymus 0 1": 0.06, "thymus 2": 0.02, "thymus 3": 0.15, "spleen 0 1": 0.15, "spleen 2 3": 0.18, "kidneys 0 1": 0.18, "kidneys 2 3": None, "adrenals 0 1": None, "adrenals 2 3": None}},
    13: {"Mean": {"FL": 12, "CR": 8.7, "CH": 11.8, "HDC": 8.5, "Body": 37.4, "brain": 6.5, "heart": 0.2, "lungs 0 1": 1.2, "lungs 2 3": 1.2, "liver 0 1": 2, "liver 2": 1.7, "liver 3": 1.7, "thymus 0 1": 0.04, "thymus 2": 0.02, "thymus 3": 0.08, "spleen 0 1": 0.3, "spleen 2 3": 0.2, "kidneys 0 1": 0.17, "kidneys 2 3": 0.17, "adrenals 0 1": None, "adrenals 2 3": None}, "SD": {"FL": 3, "CR": 1.2, "CH": 1.8, "HDC": 1.2, "Body": 14.9, "brain": 1.4, "heart": 0.14, "lungs 0 1": 0.9, "lungs 2 3": 0.9, "liver 0 1": 1.2, "liver 2": 1.2, "liver 3": 1.2, "thymus 0 1": 0.06, "thymus 2": 0.03, "thymus 3": 0.03, "spleen 0 1": 0.1, "spleen 2 3": 0.1, "kidneys 0 1": 0.18, "kidneys 2 3": 0.18, "adrenals 0 1": None, "adrenals 2 3": None}},
    14: {"Mean": {"FL": 15, "CR": 9.9, "CH": 13.7, "HDC": 9.8, "Body": 53, "brain": 9.1, "heart": 0.3, "lungs 0 1": 2, "lungs 2 3": 1.5, "liver 0 1": 2.9, "liver 2": 2.4, "liver 3": 2.3, "thymus 0 1": 0.05, "thymus 2": 0.07, "thymus 3": 0.05, "spleen 0 1": 0.04, "spleen 2 3": 0.14, "kidneys 0 1": 0.4, "kidneys 2 3": 0.3, "adrenals 0 1": 0.3, "adrenals 2 3": 0.2}, "SD": {"FL": 3, "CR": 1.2, "CH": 1.8, "HDC": 1.2, "Body": 14.9, "brain": 2.5, "heart": 0.1, "lungs 0 1": 0.9, "lungs 2 3": 0.9, "liver 0 1": 1.2, "liver 2": 1.2, "liver 3": 1.2, "thymus 0 1": 0.06, "thymus 2": 0.06, "thymus 3": 0.06, "spleen 0 1": 0.04, "spleen 2 3": 0.04, "kidneys 0 1": 0.1, "kidneys 2 3": 0.1, "adrenals 0 1": 0.2, "adrenals 2 3": 0.2}},
    15: {"Mean": {"FL": 18, "CR": 11.1, "CH": 15.6, "HDC": 11.1, "Body": 76.5, "brain": 12.7, "heart": 0.5, "lungs 0 1": 2.9, "lungs 2 3": 2.1, "liver 0 1": 4.2, "liver 2": 3.3, "liver 3": 3.2, "thymus 0 1": 0.07, "thymus 2": 0.08, "thymus 3": 0.06, "spleen 0 1": 0.06, "spleen 2 3": 0.17, "kidneys 0 1": 0.6, "kidneys 2 3": 0.5, "adrenals 0 1": 0.5, "adrenals 2 3": 0.3}, "SD": {"FL": 3, "CR": 1.2, "CH": 1.8, "HDC": 1.2, "Body": 18.5, "brain": 3.9, "heart": 0.1, "lungs 0 1": 0.9, "lungs 2 3": 0.9, "liver 0 1": 1.2, "liver 2": 1.2, "liver 3": 1.2, "thymus 0 1": 0.06, "thymus 2": 0.06, "thymus 3": 0.06, "spleen 0 1": 0.06, "spleen 2 3": 0.06, "kidneys 0 1": 0.3, "kidneys 2 3": 0.3, "adrenals 0 1": 0.2, "adrenals 2 3": 0.2}},
    16: {"Mean": {"FL": 21, "CR": 12.4, "CH": 17.5, "HDC": 12.4, "Body": 108, "brain": 17.3, "heart": 0.8, "lungs 0 1": 3.9, "lungs 2 3": 2.7, "liver 0 1": 5.9, "liver 2": 4.5, "liver 3": 4.2, "thymus 0 1": 0.11, "thymus 2": 0.12, "thymus 3": 0.09, "spleen 0 1": 0.09, "spleen 2 3": 0.17, "kidneys 0 1": 0.9, "kidneys 2 3": 0.8, "adrenals 0 1": 0.6, "adrenals 2 3": 0.4}, "SD": {"FL": 3, "CR": 1.3, "CH": 1.8, "HDC": 1.3, "Body": 41, "brain": 5.4, "heart": 0.2, "lungs 0 1": 1.2, "lungs 2 3": 1.2, "liver 0 1": 1.5, "liver 2": 1.5, "liver 3": 1.5, "thymus 0 1": 0.06, "thymus 2": 0.06, "thymus 3": 0.06, "spleen 0 1": 0.08, "spleen 2 3": 0.08, "kidneys 0 1": 0.4, "kidneys 2 3": 0.4, "adrenals 0 1": 0.3, "adrenals 2 3": 0.3}},
    17: {"Mean": {"FL": 24, "CR": 13.5, "CH": 19.3, "HDC": 13.6, "Body": 147, "brain": 22.9, "heart": 1, "lungs 0 1": 5.1, "lungs 2 3": 3.5, "liver 0 1": 8.1, "liver 2": 6.1, "liver 3": 5.4, "thymus 0 1": 0.18, "thymus 2": 0.18, "thymus 3": 0.12, "spleen 0 1": 0.13, "spleen 2 3": 0.16, "kidneys 0 1": 1.3, "kidneys 2 3": 1.1, "adrenals 0 1": 0.8, "adrenals 2 3": 0.5}, "SD": {"FL": 3, "CR": 1.3, "CH": 1.9, "HDC": 1.3, "Body": 53, "brain": 6.9, "heart": 0.4, "lungs 0 1": 1.7, "lungs 2 3": 1.7, "liver 0 1": 3, "liver 2": 3, "liver 3": 3, "thymus 0 1": 0.06, "thymus 2": 0.06, "thymus 3": 0.06, "spleen 0 1": 0.12, "spleen 2 3": 0.12, "kidneys 0 1": 0.6, "kidneys 2 3": 0.6, "adrenals 0 1": 0.4, "adrenals 2 3": 0.4}},
    18: {"Mean": {"FL": 27, "CR": 14.7, "CH": 21.1, "HDC": 14.8, "Body": 194, "brain": 29.4, "heart": 1.4, "lungs 0 1": 6.4, "lungs 2 3": 4.4, "liver 0 1": 10.7, "liver 2": 7.9, "liver 3": 6.8, "thymus 0 1": 0.3, "thymus 2": 0.3, "thymus 3": 0.2, "spleen 0 1": 0.19, "spleen 2 3": 0.15, "kidneys 0 1": 1.8, "kidneys 2 3": 1.5, "adrenals 0 1": 1, "adrenals 2 3": 0.7}, "SD": {"FL": 3, "CR": 1.3, "CH": 1.9, "HDC": 1.3, "Body": 65, "brain": 8.4, "heart": 0.5, "lungs 0 1": 2.3, "lungs 2 3": 2.3, "liver 0 1": 4.5, "liver 2": 4.5, "liver 3": 4.5, "thymus 0 1": 0.2, "thymus 2": 0.2, "thymus 3": 0.2, "spleen 0 1": 0.17, "spleen 2 3": 0.17, "kidneys 0 1": 0.8, "kidneys 2 3": 0.8, "adrenals 0 1": 0.4, "adrenals 2 3": 0.4}},
    19: {"Mean": {"FL": 30, "CR": 15.9, "CH": 22.9, "HDC": 16, "Body": 249, "brain": 37, "heart": 1.7, "lungs 0 1": 7.9, "lungs 2 3": 5.4, "liver 0 1": 13.8, "liver 2": 10.1, "liver 3": 8.4, "thymus 0 1": 0.4, "thymus 2": 0.4, "thymus 3": 0.3, "spleen 0 1": 0.3, "spleen 2 3": 0.15, "kidneys 0 1": 2.4, "kidneys 2 3": 2, "adrenals 0 1": 1.2, "adrenals 2 3": 0.8}, "SD": {"FL": 3, "CR": 1.3, "CH": 1.9, "HDC": 1.3, "Body": 78, "brain": 9.8, "heart": 0.7, "lungs 0 1": 2.8, "lungs 2 3": 2.8, "liver 0 1": 6, "liver 2": 6, "liver 3": 6, "thymus 0 1": 0.3, "thymus 2": 0.3, "thymus 3": 0.3, "spleen 0 1": 0.2, "spleen 2 3": 0.22, "kidneys 0 1": 1, "kidneys 2 3": 1, "adrenals 0 1": 0.5, "adrenals 2 3": 0.5}},
    20: {"Mean": {"FL": 33, "CR": 17, "CH": 24.6, "HDC": 17.2, "Body": 312, "brain": 45.5, "heart": 2.1, "lungs 0 1": 9.5, "lungs 2 3": 6.5, "liver 0 1": 17.2, "liver 2": 12.5, "liver 3": 10.2, "thymus 0 1": 0.6, "thymus 2": 0.5, "thymus 3": 0.3, "spleen 0 1": 0.4, "spleen 2 3": 0.17, "kidneys 0 1": 3, "kidneys 2 3": 2.5, "adrenals 0 1": 1.4, "adrenals 2 3": 1}, "SD": {"FL": 3, "CR": 1.4, "CH": 1.9, "HDC": 1.4, "Body": 92, "brain": 11.3, "heart": 0.8, "lungs 0 1": 3.4, "lungs 2 3": 3.4, "liver 0 1": 7.5, "liver 2": 7.5, "liver 3": 7.5, "thymus 0 1": 0.4, "thymus 2": 0.4, "thymus 3": 0.4, "spleen 0 1": 0.3, "spleen 2 3": 0.29, "kidneys 0 1": 1.2, "kidneys 2 3": 1.2, "adrenals 0 1": 0.6, "adrenals 2 3": 0.6}},
    21: {"Mean": {"FL": 36, "CR": 18.2, "CH": 26.3, "HDC": 18.3, "Body": 382, "brain": 55, "heart": 2.6, "lungs 0 1": 11.2, "lungs 2 3": 7.8, "liver 0 1": 21.1, "liver 2": 15.2, "liver 3": 12.3, "thymus 0 1": 0.8, "thymus 2": 0.7, "thymus 3": 0.4, "spleen 0 1": 0.5, "spleen 2 3": 0.22, "kidneys 0 1": 3.8, "kidneys 2 3": 3.1, "adrenals 0 1": 1.7, "adrenals 2 3": 1.2}, "SD": {"FL": 3, "CR": 1.4, "CH": 2, "HDC": 1.4, "Body": 107, "brain": 12.8, "heart": 1, "lungs 0 1": 4, "lungs 2 3": 4, "liver 0 1": 9, "liver 2": 9, "liver 3": 9, "thymus 0 1": 0.5, "thymus 2": 0.5, "thymus 3": 0.5, "spleen 0 1": 0.4, "spleen 2 3": 0.36, "kidneys 0 1": 1.4, "kidneys 2 3": 1.4, "adrenals 0 1": 0.7, "adrenals 2 3": 0.7}},
    22: {"Mean": {"FL": 39, "CR": 19.3, "CH": 28, "HDC": 19.4, "Body": 461, "brain": 65.4, "heart": 3.1, "lungs 0 1": 13.1, "lungs 2 3": 9.2, "liver 0 1": 25.5, "liver 2": 18.2, "liver 3": 14.5, "thymus 0 1": 1, "thymus 2": 0.9, "thymus 3": 0.6, "spleen 0 1": 0.7, "spleen 2 3": 0.3, "kidneys 0 1": 4.6, "kidneys 2 3": 3.8, "adrenals 0 1": 1.9, "adrenals 2 3": 1.4}, "SD": {"FL": 3, "CR": 1.4, "CH": 2, "HDC": 1.4, "Body": 122, "brain": 14.3, "heart": 1.1, "lungs 0 1": 4.6, "lungs 2 3": 4.6, "liver 0 1": 10.4, "liver 2": 10.4, "liver 3": 10.4, "thymus 0 1": 0.6, "thymus 2": 0.6, "thymus 3": 0.6, "spleen 0 1": 0.4, "spleen 2 3": 0.4, "kidneys 0 1": 1.6, "kidneys 2 3": 1.6, "adrenals 0 1": 0.8, "adrenals 2 3": 0.8}},
    23: {"Mean": {"FL": 41, "CR": 20.4, "CH": 29.6, "HDC": 20.5, "Body": 547, "brain": 76.9, "heart": 3.6, "lungs 0 1": 15.1, "lungs 2 3": 10.7, "liver 0 1": 30.2, "liver 2": 21.6, "liver 3": 16.9, "thymus 0 1": 1.3, "thymus 2": 1.1, "thymus 3": 0.7, "spleen 0 1": 0.9, "spleen 2 3": 0.4, "kidneys 0 1": 5.5, "kidneys 2 3": 4.6, "adrenals 0 1": 2.2, "adrenals 2 3": 1.6}, "SD": {"FL": 4, "CR": 1.5, "CH": 2, "HDC": 1.4, "Body": 122, "brain": 15.8, "heart": 1.3, "lungs 0 1": 5.3, "lungs 2 3": 5.3, "liver 0 1": 11.9, "liver 2": 11.9, "liver 3": 11.9, "thymus 0 1": 0.8, "thymus 2": 0.8, "thymus 3": 0.8, "spleen 0 1": 0.5, "spleen 2 3": 0.5, "kidneys 0 1": 1.9, "kidneys 2 3": 1.9, "adrenals 0 1": 0.8, "adrenals 2 3": 0.8}},
    24: {"Mean": {"FL": 44, "CR": 21.5, "CH": 31.2, "HDC": 21.6, "Body": 641, "brain": 89.3, "heart": 4.2, "lungs 0 1": 17.3, "lungs 2 3": 12.4, "liver 0 1": 35.4, "liver 2": 25.2, "liver 3": 19.5, "thymus 0 1": 1.6, "thymus 2": 1.3, "thymus 3": 0.8, "spleen 0 1": 1.1, "spleen 2 3": 0.6, "kidneys 0 1": 6.5, "kidneys 2 3": 5.5, "adrenals 0 1": 2.5, "adrenals 2 3": 1.8}, "SD": {"FL": 4, "CR": 1.5, "CH": 2, "HDC": 1.5, "Body": 137, "brain": 17.2, "heart": 1.4, "lungs 0 1": 5.9, "lungs 2 3": 5.9, "liver 0 1": 13.4, "liver 2": 13.4, "liver 3": 13.4, "thymus 0 1": 0.9, "thymus 2": 0.9, "thymus 3": 0.9, "spleen 0 1": 0.6, "spleen 2 3": 0.6, "kidneys 0 1": 2.1, "kidneys 2 3": 2.1, "adrenals 0 1": 0.9, "adrenals 2 3": 0.9}},
    25: {"Mean": {"FL": 47, "CR": 22.6, "CH": 32.8, "HDC": 22.6, "Body": 743, "brain": 103, "heart": 4.9, "lungs 0 1": 19.6, "lungs 2 3": 14.1, "liver 0 1": 41.1, "liver 2": 29.1, "liver 3": 22.3, "thymus 0 1": 1.9, "thymus 2": 1.6, "thymus 3": 1, "spleen 0 1": 1.4, "spleen 2 3": 0.8, "kidneys 0 1": 7.6, "kidneys 2 3": 6.4, "adrenals 0 1": 2.8, "adrenals 2 3": 2}, "SD": {"FL": 4, "CR": 1.5, "CH": 2.1, "HDC": 1.5, "Body": 154, "brain": 19, "heart": 1.6, "lungs 0 1": 6.6, "lungs 2 3": 6.6, "liver 0 1": 14.9, "liver 2": 14.9, "liver 3": 14.9, "thymus 0 1": 1.1, "thymus 2": 1.1, "thymus 3": 1.1, "spleen 0 1": 0.7, "spleen 2 3": 0.7, "kidneys 0 1": 2.4, "kidneys 2 3": 2.4, "adrenals 0 1": 1, "adrenals 2 3": 1}},
    26: {"Mean": {"FL": 50, "CR": 23.6, "CH": 34.3, "HDC": 23.6, "Body": 853, "brain": 117, "heart": 5.6, "lungs 0 1": 22, "lungs 2 3": 16, "liver 0 1": 47.1, "liver 2": 33.4, "liver 3": 25.3, "thymus 0 1": 2.3, "thymus 2": 1.9, "thymus 3": 1.2, "spleen 0 1": 1.7, "spleen 2 3": 1.1, "kidneys 0 1": 8.8, "kidneys 2 3": 7.4, "adrenals 0 1": 3.1, "adrenals 2 3": 2.3}, "SD": {"FL": 4, "CR": 1.5, "CH": 2.1, "HDC": 1.5, "Body": 171, "brain": 20, "heart": 1.7, "lungs 0 1": 7.3, "lungs 2 3": 7.3, "liver 0 1": 16.4, "liver 2": 16.4, "liver 3": 16.4, "thymus 0 1": 1.2, "thymus 2": 1.2, "thymus 3": 1.2, "spleen 0 1": 0.9, "spleen 2 3": 0.9, "kidneys 0 1": 2.7, "kidneys 2 3": 2.7, "adrenals 0 1": 1.1, "adrenals 2 3": 1.1}},
    27: {"Mean": {"FL": 52, "CR": 24.7, "CH": 35.8, "HDC": 24.5, "Body": 971, "brain": 133, "heart": 6.3, "lungs 0 1": 24.6, "lungs 2 3": 18, "liver 0 1": 53.6, "liver 2": 37.9, "liver 3": 28.6, "thymus 0 1": 2.6, "thymus 2": 2.2, "thymus 3": 1.4, "spleen 0 1": 2.1, "spleen 2 3": 1.4, "kidneys 0 1": 10.1, "kidneys 2 3": 8.4, "adrenals 0 1": 3.4, "adrenals 2 3": 2.5}, "SD": {"FL": 4, "CR": 1.6, "CH": 2.1, "HDC": 1.5, "Body": 188, "brain": 22, "heart": 1.8, "lungs 0 1": 8, "lungs 2 3": 8, "liver 0 1": 17.9, "liver 2": 17.9, "liver 3": 17.9, "thymus 0 1": 1.4, "thymus 2": 1.4, "thymus 3": 1.4, "spleen 0 1": 1, "spleen 2 3": 1, "kidneys 0 1": 3, "kidneys 2 3": 3, "adrenals 0 1": 1.2, "adrenals 2 3": 1.2}},
    28: {"Mean": {"FL": 55, "CR": 25.7, "CH": 37.3, "HDC": 25.5, "Body": 1096, "brain": 149, "heart": 7.1, "lungs 0 1": 27.4, "lungs 2 3": 20.2, "liver 0 1": 60.6, "liver 2": 42.7, "liver 3": 32, "thymus 0 1": 3.1, "thymus 2": 2.5, "thymus 3": 1.6, "spleen 0 1": 2.5, "spleen 2 3": 1.8, "kidneys 0 1": 11.4, "kidneys 2 3": 9.6, "adrenals 0 1": 3.7, "adrenals 2 3": 2.8}, "SD": {"FL": 4, "CR": 1.6, "CH": 2.2, "HDC": 1.6, "Body": 206, "brain": 23, "heart": 2, "lungs 0 1": 8.7, "lungs 2 3": 8.7, "liver 0 1": 19.3, "liver 2": 19.3, "liver 3": 19.3, "thymus 0 1": 1.6, "thymus 2": 1.6, "thymus 3": 1.6, "spleen 0 1": 1.1, "spleen 2 3": 1.1, "kidneys 0 1": 3.3, "kidneys 2 3": 3.3, "adrenals 0 1": 1.3, "adrenals 2 3": 1.3}},
    29: {"Mean": {"FL": 57, "CR": 26.7, "CH": 38.7, "HDC": 26.4, "Body": 1230, "brain": 166, "heart": 7.9, "lungs 0 1": 30.2, "lungs 2 3": 22.5, "liver 0 1": 67.9, "liver 2": 47.8, "liver 3": 35.6, "thymus 0 1": 3.5, "thymus 2": 2.9, "thymus 3": 1.8, "spleen 0 1": 3, "spleen 2 3": 2.2, "kidneys 0 1": 12.9, "kidneys 2 3": 10.8, "adrenals 0 1": 4.1, "adrenals 2 3": 3.1}, "SD": {"FL": 4, "CR": 1.6, "CH": 2.2, "HDC": 1.6, "Body": 225, "brain": 25, "heart": 2.1, "lungs 0 1": 9.5, "lungs 2 3": 9.5, "liver 0 1": 20.8, "liver 2": 20.8, "liver 3": 20.8, "thymus 0 1": 1.8, "thymus 2": 1.8, "thymus 3": 1.8, "spleen 0 1": 1.3, "spleen 2 3": 1.3, "kidneys 0 1": 3.6, "kidneys 2 3": 3.6, "adrenals 0 1": 1.4, "adrenals 2 3": 1.4}},
    30: {"Mean": {"FL": 60, "CR": 27.7, "CH": 40.1, "HDC": 27.2, "Body": 1371, "brain": 185, "heart": 8.7, "lungs 0 1": 33.2, "lungs 2 3": 24.9, "liver 0 1": 75.7, "liver 2": 53.3, "liver 3": 39.4, "thymus 0 1": 4, "thymus 2": 3.3, "thymus 3": 2.1, "spleen 0 1": 3.6, "spleen 2 3": 2.7, "kidneys 0 1": 14.4, "kidneys 2 3": 12.1, "adrenals 0 1": 4.5, "adrenals 2 3": 3.4}, "SD": {"FL": 4, "CR": 1.6, "CH": 2.2, "HDC": 1.6, "Body": 244, "brain": 26, "heart": 2.3, "lungs 0 1": 10.2, "lungs 2 3": 10.2, "liver 0 1": 22.3, "liver 2": 22.3, "liver 3": 22.3, "thymus 0 1": 2.1, "thymus 2": 2.1, "thymus 3": 2.1, "spleen 0 1": 1.4, "spleen 2 3": 1.4, "kidneys 0 1": 3.9, "kidneys 2 3": 3.9, "adrenals 0 1": 1.4, "adrenals 2 3": 1.4}},
    31: {"Mean": {"FL": 62, "CR": 28.7, "CH": 41.4, "HDC": 28.1, "Body": 1520, "brain": 204, "heart": 9.6, "lungs 0 1": 36.3, "lungs 2 3": 27.4, "liver 0 1": 83.9, "liver 2": 59, "liver 3": 43.4, "thymus 0 1": 4.5, "thymus 2": 3.7, "thymus 3": 2.3, "spleen 0 1": 4.2, "spleen 2 3": 3.3, "kidneys 0 1": 16, "kidneys 2 3": 13.4, "adrenals 0 1": 4.8, "adrenals 2 3": 3.8}, "SD": {"FL": 4, "CR": 1.7, "CH": 2.2, "HDC": 1.7, "Body": 264, "brain": 28, "heart": 2.4, "lungs 0 1": 11, "lungs 2 3": 11, "liver 0 1": 23.8, "liver 2": 23.8, "liver 3": 23.8, "thymus 0 1": 2.3, "thymus 2": 2.3, "thymus 3": 2.3, "spleen 0 1": 1.6, "spleen 2 3": 1.6, "kidneys 0 1": 4.3, "kidneys 2 3": 4.3, "adrenals 0 1": 1.5, "adrenals 2 3": 1.5}},
    32: {"Mean": {"FL": 64, "CR": 29.7, "CH": 42.8, "HDC": 28.9, "Body": 1677, "brain": 224, "heart": 10.6, "lungs 0 1": 39.6, "lungs 2 3": 30, "liver 0 1": 92.6, "liver 2": 65, "liver 3": 47.6, "thymus 0 1": 5, "thymus 2": 4.2, "thymus 3": 2.6, "spleen 0 1": 4.8, "spleen 2 3": 3.9, "kidneys 0 1": 17.7, "kidneys 2 3": 14.9, "adrenals 0 1": 5.2, "adrenals 2 3": 4.1}, "SD": {"FL": 4, "CR": 1.7, "CH": 2.3, "HDC": 1.7, "Body": 285, "brain": 29, "heart": 2.6, "lungs 0 1": 11.8, "lungs 2 3": 11.8, "liver 0 1": 25.3, "liver 2": 25.3, "liver 3": 25.3, "thymus 0 1": 2.5, "thymus 2": 2.5, "thymus 3": 2.5, "spleen 0 1": 1.8, "spleen 2 3": 1.8, "kidneys 0 1": 4.6, "kidneys 2 3": 4.6, "adrenals 0 1": 1.6, "adrenals 2 3": 1.6}},
    33: {"Mean": {"FL": 67, "CR": 30.6, "CH": 44, "HDC": 29.7, "Body": 1842, "brain": 245, "heart": 11.6, "lungs 0 1": 43, "lungs 2 3": 32.8, "liver 0 1": 102, "liver 2": 71.3, "liver 3": 52.1, "thymus 0 1": 5.6, "thymus 2": 4.6, "thymus 3": 2.9, "spleen 0 1": 5.5, "spleen 2 3": 4.5, "kidneys 0 1": 19.5, "kidneys 2 3": 16.4, "adrenals 0 1": 5.6, "adrenals 2 3": 4.5}, "SD": {"FL": 4, "CR": 1.7, "CH": 2.3, "HDC": 1.7, "Body": 306, "brain": 31, "heart": 2.7, "lungs 0 1": 12.6, "lungs 2 3": 12.6, "liver 0 1": 27, "liver 2": 26.7, "liver 3": 26.7, "thymus 0 1": 2.8, "thymus 2": 2.8, "thymus 3": 2.8, "spleen 0 1": 1.9, "spleen 2 3": 1.9, "kidneys 0 1": 5, "kidneys 2 3": 5, "adrenals 0 1": 1.7, "adrenals 2 3": 1.7}},
    34: {"Mean": {"FL": 69, "CR": 31.6, "CH": 45.3, "HDC": 30.5, "Body": 2015, "brain": 268, "heart": 12.6, "lungs 0 1": 46.6, "lungs 2 3": 35.7, "liver 0 1": 111, "liver 2": 77.9, "liver 3": 56.7, "thymus 0 1": 6.2, "thymus 2": 5.1, "thymus 3": 3.2, "spleen 0 1": 6.3, "spleen 2 3": 5.2, "kidneys 0 1": 21.4, "kidneys 2 3": 18, "adrenals 0 1": 6, "adrenals 2 3": 4.8}, "SD": {"FL": 4, "CR": 1.8, "CH": 2.3, "HDC": 1.7, "Body": 328, "brain": 32, "heart": 2.9, "lungs 0 1": 13.5, "lungs 2 3": 13.5, "liver 0 1": 28, "liver 2": 28.2, "liver 3": 28.2, "thymus 0 1": 3.1, "thymus 2": 3.1, "thymus 3": 3.1, "spleen 0 1": 2.1, "spleen 2 3": 2.1, "kidneys 0 1": 5.4, "kidneys 2 3": 5.4, "adrenals 0 1": 1.8, "adrenals 2 3": 1.8}},
    35: {"Mean": {"FL": 71, "CR": 32.5, "CH": 46.5, "HDC": 31.2, "Body": 2195, "brain": 291, "heart": 13.7, "lungs 0 1": 50.3, "lungs 2 3": 38.7, "liver 0 1": 121, "liver 2": 84.8, "liver 3": 61.5, "thymus 0 1": 6.9, "thymus 2": 5.7, "thymus 3": 3.5, "spleen 0 1": 7.2, "spleen 2 3": 6, "kidneys 0 1": 23.3, "kidneys 2 3": 19.6, "adrenals 0 1": 6.5, "adrenals 2 3": 5.2}, "SD": {"FL": 5, "CR": 1.8, "CH": 2.3, "HDC": 1.8, "Body": 350, "brain": 33, "heart": 3, "lungs 0 1": 14.3, "lungs 2 3": 14.3, "liver 0 1": 30, "liver 2": 29.7, "liver 3": 29.7, "thymus 0 1": 3.3, "thymus 2": 3.3, "thymus 3": 3.3, "spleen 0 1": 2.3, "spleen 2 3": 2.3, "kidneys 0 1": 5.8, "kidneys 2 3": 5.8, "adrenals 0 1": 1.9, "adrenals 2 3": 1.9}},
    36: {"Mean": {"FL": 73, "CR": 33.4, "CH": 47.7, "HDC": 31.9, "Body": 2383, "brain": 315, "heart": 14.8, "lungs 0 1": 54.1, "lungs 2 3": 41.9, "liver 0 1": 132, "liver 2": 92.1, "liver 3": 66.5, "thymus 0 1": 7.5, "thymus 2": 6.2, "thymus 3": 3.8, "spleen 0 1": 8.1, "spleen 2 3": 6.7, "kidneys 0 1": 25.4, "kidneys 2 3": 21.4, "adrenals 0 1": 6.9, "adrenals 2 3": 5.6}, "SD": {"FL": 5, "CR": 1.8, "CH": 2.4, "HDC": 1.8, "Body": 373, "brain": 35, "heart": 3.2, "lungs 0 1": 15.2, "lungs 2 3": 15.2, "liver 0 1": 31, "liver 2": 31.2, "liver 3": 31.2, "thymus 0 1": 3.6, "thymus 2": 3.6, "thymus 3": 3.6, "spleen 0 1": 2.5, "spleen 2 3": 2.5, "kidneys 0 1": 6.2, "kidneys 2 3": 6.2, "adrenals 0 1": 2, "adrenals 2 3": 2}},
    37: {"Mean": {"FL": 76, "CR": 34.3, "CH": 48.9, "HDC": 32.6, "Body": 2580, "brain": 340, "heart": 16, "lungs 0 1": 58.1, "lungs 2 3": 45.1, "liver 0 1": 142, "liver 2": 100, "liver 3": 71.7, "thymus 0 1": 8.2, "thymus 2": 6.8, "thymus 3": 4.2, "spleen 0 1": 9.1, "spleen 2 3": 7.5, "kidneys 0 1": 27.5, "kidneys 2 3": 23.2, "adrenals 0 1": 7.4, "adrenals 2 3": 6}, "SD": {"FL": 5, "CR": 1.8, "CH": 2.4, "HDC": 1.8, "Body": 397, "brain": 36, "heart": 3.3, "lungs 0 1": 16.1, "lungs 2 3": 16.1, "liver 0 1": 33, "liver 2": 33, "liver 3": 32.7, "thymus 0 1": 3.9, "thymus 2": 3.9, "thymus 3": 3.9, "spleen 0 1": 2.7, "spleen 2 3": 2.7, "kidneys 0 1": 6.6, "kidneys 2 3": 6.6, "adrenals 0 1": 2.1, "adrenals 2 3": 2.1}},
    38: {"Mean": {"FL": 78, "CR": 35.2, "CH": 50, "HDC": 33.2, "Body": 2784, "brain": 366, "heart": 17.2, "lungs 0 1": 62.2, "lungs 2 3": 48.5, "liver 0 1": 154, "liver 2": 107, "liver 3": 77.2, "thymus 0 1": 8.9, "thymus 2": 7.4, "thymus 3": 3.9, "spleen 0 1": 10.1, "spleen 2 3": 8.3, "kidneys 0 1": 29.8, "kidneys 2 3": 25, "adrenals 0 1": 7.8, "adrenals 2 3": 6.5}, "SD": {"FL": 5, "CR": 1.9, "CH": 2.4, "HDC": 1.8, "Body": 421, "brain": 38, "heart": 3.4, "lungs 0 1": 17, "lungs 2 3": 17, "liver 0 1": 34, "liver 2": 34, "liver 3": 34.2, "thymus 0 1": 4.2, "thymus 2": 4.2, "thymus 3": 4.2, "spleen 0 1": 3, "spleen 2 3": 3, "kidneys 0 1": 7.1, "kidneys 2 3": 7.1, "adrenals 0 1": 2.2, "adrenals 2 3": 2.2}},
    39: {"Mean": {"FL": 80, "CR": 36.1, "CH": 51.1, "HDC": 33.8, "Body": 2996, "brain": 394, "heart": 18.5, "lungs 0 1": 66.5, "lungs 2 3": 52.1, "liver 0 1": 165, "liver 2": 116, "liver 3": 82.8, "thymus 0 1": 9.7, "thymus 2": 8, "thymus 3": 5, "spleen 0 1": 11.2, "spleen 2 3": 9.1, "kidneys 0 1": 32.1, "kidneys 2 3": 27, "adrenals 0 1": 8.3, "adrenals 2 3": 6.9}, "SD": {"FL": 5, "CR": 1.9, "CH": 2.4, "HDC": 1.9, "Body": 446, "brain": 39, "heart": 3.6, "lungs 0 1": 18, "lungs 2 3": 18, "liver 0 1": 36, "liver 2": 36, "liver 3": 35.6, "thymus 0 1": 4.6, "thymus 2": 4.6, "thymus 3": 4.6, "spleen 0 1": 3.2, "spleen 2 3": 3.2, "kidneys 0 1": 7.5, "kidneys 2 3": 7.5, "adrenals 0 1": 2.3, "adrenals 2 3": 2.3}},
    40: {"Mean": {"FL": 82, "CR": 37, "CH": 52.1, "HDC": 34.4, "Body": 3215, "brain": 422, "heart": 19.8, "lungs 0 1": 70.9, "lungs 2 3": 55.7, "liver 0 1": 177, "liver 2": 124, "liver 3": 88.6, "thymus 0 1": 10.5, "thymus 2": 8.6, "thymus 3": 5.4, "spleen 0 1": 12.4, "spleen 2 3": 9.9, "kidneys 0 1": 34.5, "kidneys 2 3": 29, "adrenals 0 1": 8.8, "adrenals 2 3": 7.4}, "SD": {"FL": 5, "CR": 1.9, "CH": 2.5, "HDC": 1.9, "Body": 471, "brain": 41, "heart": 3.7, "lungs 0 1": 18.9, "lungs 2 3": 18.9, "liver 0 1": 37, "liver 2": 37, "liver 3": 37.1, "thymus 0 1": 4.9, "thymus 2": 4.9, "thymus 3": 4.9, "spleen 0 1": 3.4, "spleen 2 3": 3.4, "kidneys 0 1": 8, "kidneys 2 3": 8, "adrenals 0 1": 2.4, "adrenals 2 3": 2.4}},
    41: {"Mean": {"FL": 84, "CR": 37.8, "CH": 53.1, "HDC": 35, "Body": 3443, "brain": 451, "heart": 21.2, "lungs 0 1": 75.4, "lungs 2 3": 59.5, "liver 0 1": 190, "liver 2": 133, "liver 3": 94.6, "thymus 0 1": 11.3, "thymus 2": 9.3, "thymus 3": 5.8, "spleen 0 1": 13.7, "spleen 2 3": 10.7, "kidneys 0 1": 37, "kidneys 2 3": 31.1, "adrenals 0 1": 9.3, "adrenals 2 3": 7.9}, "SD": {"FL": 5, "CR": 1.9, "CH": 2.5, "HDC": 1.9, "Body": 497, "brain": 42, "heart": 3.9, "lungs 0 1": 19.9, "lungs 2 3": 19.9, "liver 0 1": 39, "liver 2": 39, "liver 3": 38.6, "thymus 0 1": 5.3, "thymus 2": 5.3, "thymus 3": 5.3, "spleen 0 1": 3.7, "spleen 2 3": 3.7, "kidneys 0 1": 8.4, "kidneys 2 3": 8.4, "adrenals 0 1": 2.5, "adrenals 2 3": 2.5}},
    42: {"Mean": {"FL": 86, "CR": 38.6, "CH": 54.1, "HDC": 35.5, "Body": 3678, "brain": 481, "heart": 22.5, "lungs 0 1": 80.1, "lungs 2 3": 63.4, "liver 0 1": 203, "liver 2": 142, "liver 3": 101, "thymus 0 1": 12.2, "thymus 2": 10, "thymus 3": 6.2, "spleen 0 1": 15, "spleen 2 3": 11.5, "kidneys 0 1": 39.6, "kidneys 2 3": 33.3, "adrenals 0 1": 9.9, "adrenals 2 3": 8.4}, "SD": {"FL": 5, "CR": 2, "CH": 2.5, "HDC": 2, "Body": 524, "brain": 44, "heart": 4, "lungs 0 1": 20.9, "lungs 2 3": 20.9, "liver 0 1": 40, "liver 2": 40, "liver 3": 40, "thymus 0 1": 5.6, "thymus 2": 5.6, "thymus 3": 5.6, "spleen 0 1": 4, "spleen 2 3": 4, "kidneys 0 1": 8.9, "kidneys 2 3": 8.9, "adrenals 0 1": 2.6, "adrenals 2 3": 2.6}},
    43: {"Mean": {"FL": 88, "CR": 39.4, "CH": 55, "HDC": 36, "Body": 3922, "brain": 512, "heart": 24, "lungs 0 1": 84.9, "lungs 2 3": 67.4, "liver 0 1": 216, "liver 2": 151, "liver 3": 107, "thymus 0 1": 13.1, "thymus 2": 10.7, "thymus 3": 6.6, "spleen 0 1": 16.4, "spleen 2 3": 12.2, "kidneys 0 1": 42.2, "kidneys 2 3": 35.5, "adrenals 0 1": 10.4, "adrenals 2 3": 8.9}, "SD": {"FL": 5, "CR": 2, "CH": 2.5, "HDC": 2, "Body": 551, "brain": 45, "heart": 4.2, "lungs 0 1": 21.9, "lungs 2 3": 21.9, "liver 0 1": 42, "liver 2": 42, "liver 3": 42, "thymus 0 1": 6, "thymus 2": 6, "thymus 3": 6, "spleen 0 1": 4.2, "spleen 2 3": 4.2, "kidneys 0 1": 9.4, "kidneys 2 3": 9.4, "adrenals 0 1": 2.7, "adrenals 2 3": 2.7}},
}


# ══════════════════════════════════════════════════════════════════════════
# Labels lisibles pour l'affichage
# ══════════════════════════════════════════════════════════════════════════

ORGAN_LABELS = {
    "coeur": "Cœur", "thymus": "Thymus",
    "poumons": "Poumons (D+G)", "poumon_d": "Poumon droit", "poumon_g": "Poumon gauche",
    "foie": "Foie", "rate": "Rate", "pancreas": "Pancréas",
    "surrenales": "Surrénales (D+G)", "surrenale_d": "Surrénale droite", "surrenale_g": "Surrénale gauche",
    "reins": "Reins (D+G)", "rein_d": "Rein droit", "rein_g": "Rein gauche",
    "cerveau": "Cerveau",
}

BIO_LABELS = {
    "masse": "Masse (g)", "VT": "VT (mm)", "VC": "VC (mm)", "PC": "PC (mm)", "pied": "Pied (mm)",
}

import math as _math

# ══════════════════════════════════════════════════════════════════════════
# MOLINA 2019 — Masses d'organes pédiatriques (1 mois – 12 ans)
# Source : Molina DK et al. Am J Forensic Med Pathol 2019;40:318-328
# 1759 décès traumatiques, 0–12 ans, 4 centres USA
# ══════════════════════════════════════════════════════════════════════════

def _from_range(low, high):
    return {"moy": round((low + high) / 2, 1), "sd": round((high - low) / 3.92, 1)}

_r = _from_range

MOLINA_ORGANES_AGE = {
    "1m":  {"cerveau": _r(378, 628),  "coeur": _r(17, 37),   "poumon_d": _r(27, 85),   "poumon_g": _r(24, 72),   "foie": _r(106, 244),  "rate": _r(4, 24),   "rein_d": _r(9, 25),   "rein_g": _r(8, 28)},
    "2m":  {"cerveau": _r(411, 741),  "coeur": _r(17, 41),   "poumon_d": _r(35, 85),   "poumon_g": _r(27, 75),   "foie": _r(111, 271),  "rate": _r(2, 34),   "rein_d": _r(10, 30),  "rein_g": _r(10, 30)},
    "3m":  {"cerveau": _r(473, 833),  "coeur": _r(21, 45),   "poumon_d": _r(39, 109),  "poumon_g": _r(33, 95),   "foie": _r(148, 332),  "rate": _r(8, 36),   "rein_d": _r(12, 36),  "rein_g": _r(13, 37)},
    "4m":  {"cerveau": _r(464, 904),  "coeur": _r(24, 44),   "poumon_d": _r(35, 97),   "poumon_g": _r(19, 93),   "foie": _r(137, 333),  "rate": _r(6, 38),   "rein_d": _r(10, 34),  "rein_g": _r(13, 33)},
    "5m":  {"cerveau": _r(542, 1004), "coeur": _r(22, 50),   "poumon_d": _r(38, 124),  "poumon_g": _r(29, 107),  "foie": _r(138, 412),  "rate": _r(7, 43),   "rein_d": _r(11, 35),  "rein_g": _r(15, 35)},
    "6m":  {"cerveau": _r(711, 1037), "coeur": _r(24, 52),   "poumon_d": _r(43, 137),  "poumon_g": _r(35, 117),  "foie": _r(210, 386),  "rate": _r(11, 43),  "rein_d": _r(18, 34),  "rein_g": _r(20, 36)},
    "7m":  {"cerveau": _r(665, 1057), "coeur": _r(23, 55),   "poumon_d": _r(43, 145),  "poumon_g": _r(30, 132),  "foie": _r(182, 440),  "rate": _r(13, 49),  "rein_d": _r(12, 40),  "rein_g": _r(15, 39)},
    "8m":  {"cerveau": _r(712, 1120), "coeur": _r(29, 61),   "poumon_d": _r(42, 152),  "poumon_g": _r(19, 149),  "foie": _r(228, 490),  "rate": _r(17, 43),  "rein_d": _r(12, 47),  "rein_g": _r(16, 52)},
    "9m":  {"cerveau": _r(683, 1169), "coeur": _r(32, 60),   "poumon_d": _r(53, 151),  "poumon_g": _r(27, 153),  "foie": _r(238, 496),  "rate": _r(16, 52),  "rein_d": _r(15, 43),  "rein_g": _r(16, 64)},
    "10m": {"cerveau": _r(809, 1135), "coeur": _r(37, 61),   "poumon_d": _r(20, 212),  "poumon_g": _r(20, 170),  "foie": _r(233, 571),  "rate": _r(21, 53),  "rein_d": _r(22, 50),  "rein_g": _r(18, 54)},
    "11m": {"cerveau": _r(761, 1177), "coeur": _r(36, 60),   "poumon_d": _r(52, 138),  "poumon_g": _r(35, 129),  "foie": _r(213, 531),  "rate": _r(10, 60),  "rein_d": _r(16, 48),  "rein_g": _r(13, 53)},
    "12m": {"cerveau": _r(719, 1245), "coeur": _r(32, 64),   "poumon_d": _r(49, 159),  "poumon_g": _r(39, 133),  "foie": _r(246, 544),  "rate": _r(16, 60),  "rein_d": _r(18, 46),  "rein_g": _r(19, 47)},
    "13m": {"cerveau": _r(867, 1111), "coeur": _r(34, 62),   "poumon_d": _r(27, 175),  "poumon_g": _r(27, 145),  "foie": _r(293, 497),  "rate": _r(15, 63),  "rein_d": _r(19, 43),  "rein_g": _r(22, 46)},
    "14m": {"cerveau": _r(765, 1303), "coeur": _r(35, 71),   "poumon_d": _r(27, 199),  "poumon_g": _r(36, 158),  "foie": _r(262, 560),  "rate": _r(19, 59),  "rein_d": _r(16, 52),  "rein_g": _r(15, 55)},
    "15m": {"cerveau": _r(823, 1227), "coeur": _r(33, 73),   "poumon_d": _r(34, 180),  "poumon_g": _r(23, 165),  "foie": _r(243, 549),  "rate": _r(23, 55),  "rein_d": _r(16, 48),  "rein_g": _r(17, 53)},
    "16m": {"cerveau": _r(908, 1252), "coeur": _r(37, 77),   "poumon_d": _r(47, 207),  "poumon_g": _r(39, 177),  "foie": _r(273, 621),  "rate": _r(21, 71),  "rein_d": _r(17, 57),  "rein_g": _r(13, 61)},
    "17m": {"cerveau": _r(825, 1275), "coeur": _r(44, 68),   "poumon_d": _r(46, 180),  "poumon_g": _r(38, 156),  "foie": _r(320, 548),  "rate": _r(23, 71),  "rein_d": _r(23, 51),  "rein_g": _r(11, 65)},
    "18m": {"cerveau": _r(833, 1225), "coeur": _r(38, 70),   "poumon_d": _r(37, 163),  "poumon_g": _r(36, 138),  "foie": _r(320, 629),  "rate": _r(18, 72),  "rein_d": _r(10, 60),  "rein_g": _r(17, 57)},
    "19m": {"cerveau": _r(858, 1316), "coeur": _r(32, 80),   "poumon_d": _r(36, 174),  "poumon_g": _r(22, 168),  "foie": _r(233, 625),  "rate": _r(17, 71),  "rein_d": _r(15, 55),  "rein_g": _r(18, 54)},
    "20m": {"cerveau": _r(873, 1331), "coeur": _r(35, 85),   "poumon_d": _r(30, 194),  "poumon_g": _r(40, 166),  "foie": _r(263, 651),  "rate": _r(20, 78),  "rein_d": _r(18, 54),  "rein_g": _r(20, 56)},
    "21m": {"cerveau": _r(799, 1391), "coeur": _r(42, 74),   "poumon_d": _r(27, 203),  "poumon_g": _r(51, 149),  "foie": _r(318, 588),  "rate": _r(15, 73),  "rein_d": _r(22, 50),  "rein_g": _r(21, 53)},
    "22m": {"cerveau": _r(868, 1416), "coeur": _r(43, 83),   "poumon_d": _r(39, 215),  "poumon_g": _r(22, 190),  "foie": _r(319, 597),  "rate": _r(18, 88),  "rein_d": _r(21, 57),  "rein_g": _r(23, 59)},
    "23m": {"cerveau": _r(916, 1366), "coeur": _r(36, 90),   "poumon_d": _r(26, 262),  "poumon_g": _r(16, 220),  "foie": _r(303, 667),  "rate": _r(11, 89),  "rein_d": _r(16, 66),  "rein_g": _r(19, 67)},
    "2a":  {"cerveau": _r(935, 1425),  "coeur": _r(42, 96),   "poumon_d": _r(26, 262),  "poumon_g": _r(40, 208),  "foie": _r(289, 681),   "rate": _r(16, 86),   "rein_d": _r(18, 68),  "rein_g": _r(20, 70)},
    "3a":  {"cerveau": _r(971, 1509),  "coeur": _r(49, 111),  "poumon_d": _r(41, 277),  "poumon_g": _r(36, 244),  "foie": _r(336, 732),   "rate": _r(20, 90),   "rein_d": _r(24, 71),  "rein_g": _r(25, 75)},
    "4a":  {"cerveau": _r(970, 1546),  "coeur": _r(55, 121),  "poumon_d": _r(60, 306),  "poumon_g": _r(54, 270),  "foie": _r(363, 833),   "rate": _r(16, 98),   "rein_d": _r(22, 84),  "rein_g": _r(24, 82)},
    "5a":  {"cerveau": _r(1072, 1538), "coeur": _r(56, 142),  "poumon_d": _r(62, 316),  "poumon_g": _r(53, 277),  "foie": _r(359, 881),   "rate": _r(19, 105),  "rein_d": _r(30, 84),  "rein_g": _r(31, 85)},
    "6a":  {"cerveau": _r(1017, 1655), "coeur": _r(59, 185),  "poumon_d": _r(57, 387),  "poumon_g": _r(44, 358),  "foie": _r(380, 1110),  "rate": _r(20, 122),  "rein_d": _r(26, 100), "rein_g": _r(31, 105)},
    "7a":  {"cerveau": _r(1020, 1620), "coeur": _r(73, 195),  "poumon_d": _r(54, 446),  "poumon_g": _r(39, 419),  "foie": _r(437, 1099),  "rate": _r(16, 162),  "rein_d": _r(21, 115), "rein_g": _r(23, 121)},
    "8a":  {"cerveau": _r(1094, 1576), "coeur": _r(71, 223),  "poumon_d": _r(51, 497),  "poumon_g": _r(34, 422),  "foie": _r(462, 1206),  "rate": _r(18, 164),  "rein_d": _r(29, 115), "rein_g": _r(37, 111)},
    "9a":  {"cerveau": _r(1133, 1611), "coeur": _r(100, 230), "poumon_d": _r(79, 553),  "poumon_g": _r(71, 483),  "foie": _r(434, 1556),  "rate": _r(27, 179),  "rein_d": _r(42, 120), "rein_g": _r(41, 135)},
    "10a": {"cerveau": _r(1093, 1637), "coeur": _r(103, 267), "poumon_d": _r(49, 559),  "poumon_g": _r(52, 498),  "foie": _r(517, 1583),  "rate": _r(31, 161),  "rein_d": _r(43, 133), "rein_g": _r(39, 149)},
    "11a": {"cerveau": _r(1102, 1640), "coeur": _r(113, 289), "poumon_d": _r(74, 600),  "poumon_g": _r(66, 524),  "foie": _r(469, 1813),  "rate": _r(20, 208),  "rein_d": _r(45, 151), "rein_g": _r(48, 158)},
    "12a": {"cerveau": _r(1117, 1657), "coeur": _r(128, 336), "poumon_d": _r(100, 668), "poumon_g": _r(64, 624),  "foie": _r(638, 1782),  "rate": _r(32, 228),  "rein_d": _r(60, 150), "rein_g": _r(62, 152)},
}

MOLINA_META = {
    "1m": {"n": 71, "poids_kg": 4.3},   "2m": {"n": 73, "poids_kg": 4.9},
    "3m": {"n": 49, "poids_kg": 6.2},   "4m": {"n": 45, "poids_kg": 6.6},
    "5m": {"n": 29, "poids_kg": 7.0},   "6m": {"n": 24, "poids_kg": 7.6},
    "7m": {"n": 20, "poids_kg": 8.0},   "8m": {"n": 25, "poids_kg": 8.5},
    "9m": {"n": 22, "poids_kg": 9.4},   "10m": {"n": 16, "poids_kg": 10.0},
    "11m": {"n": 16, "poids_kg": 9.1},  "12m": {"n": 26, "poids_kg": 9.9},
    "13m": {"n": 23, "poids_kg": 10.1}, "14m": {"n": 38, "poids_kg": 11.0},
    "15m": {"n": 28, "poids_kg": 11.4}, "16m": {"n": 31, "poids_kg": 12.2},
    "17m": {"n": 25, "poids_kg": 11.4}, "18m": {"n": 21, "poids_kg": 12.5},
    "19m": {"n": 31, "poids_kg": 11.8}, "20m": {"n": 21, "poids_kg": 12.7},
    "21m": {"n": 16, "poids_kg": 13.9}, "22m": {"n": 34, "poids_kg": 12.7},
    "23m": {"n": 21, "poids_kg": 12.9},
    "2a": {"n": 269, "poids_kg": 14.6}, "3a": {"n": 173, "poids_kg": 16.5},
    "4a": {"n": 88, "poids_kg": 18.9},  "5a": {"n": 70, "poids_kg": 20.3},
    "6a": {"n": 59, "poids_kg": 26.0},  "7a": {"n": 56, "poids_kg": 28.9},
    "8a": {"n": 46, "poids_kg": 33.5},  "9a": {"n": 43, "poids_kg": 37.8},
    "10a": {"n": 54, "poids_kg": 42.2}, "11a": {"n": 76, "poids_kg": 49.9},
    "12a": {"n": 82, "poids_kg": 58.2},
}

MOLINA_POUMONS = {
    age: {
        "moy": round(org["poumon_d"]["moy"] + org["poumon_g"]["moy"], 1),
        "sd": round(_math.sqrt(org["poumon_d"]["sd"]**2 + org["poumon_g"]["sd"]**2), 1),
    }
    for age, org in MOLINA_ORGANES_AGE.items()
}

MOLINA_REINS = {
    age: {
        "moy": round(org["rein_d"]["moy"] + org["rein_g"]["moy"], 1),
        "sd": round(_math.sqrt(org["rein_d"]["sd"]**2 + org["rein_g"]["sd"]**2), 1),
    }
    for age, org in MOLINA_ORGANES_AGE.items()
}

MOLINA_ORGANES_TAILLE = {
    "<40":     {"cerveau": _r(140, 484), "coeur": _r(13, 45),                            "poumon_g": _r(8, 82),   "foie": _r(46, 360),   "rate": _r(2, 30),   "rein_d": _r(7, 31),  "rein_g": _r(4, 36)},
    "40-45":   {"cerveau": _r(306, 850), "coeur": _r(16, 48),  "poumon_d": _r(10, 116),                           "foie": _r(84, 398),                        "rein_d": _r(3, 39),  "rein_g": _r(3, 39)},
    "45-50":   {"cerveau": _r(246, 740), "coeur": _r(10, 42),                                                     "foie": _r(32, 334),                        "rein_d": _r(1, 33),  "rein_g": _r(2, 34)},
    "50-55":   {"cerveau": _r(255, 765), "coeur": _r(14, 38),  "poumon_d": _r(27, 81),  "poumon_g": _r(21, 71),   "foie": _r(90, 302),                        "rein_d": _r(8, 28),  "rein_g": _r(6, 30)},
    "55-60":   {"cerveau": _r(265, 719),  "coeur": _r(18, 42),  "poumon_d": _r(33, 91),   "poumon_g": _r(26, 80),   "foie": _r(110, 306),   "rate": _r(4, 32),    "rein_d": _r(9, 29),   "rein_g": _r(9, 29)},
    "60-65":   {"cerveau": _r(463, 969),  "coeur": _r(21, 49),  "poumon_d": _r(40, 110),  "poumon_g": _r(29, 95),   "foie": _r(137, 369),   "rate": _r(7, 39),    "rein_d": _r(11, 35),  "rein_g": _r(13, 37)},
    "65-70":   {"cerveau": _r(607, 1133), "coeur": _r(22, 58),  "poumon_d": _r(41, 139),  "poumon_g": _r(26, 128),  "foie": _r(158, 472),   "rate": _r(9, 49),    "rein_d": _r(13, 41),  "rein_g": _r(14, 42)},
    "70-75":   {"cerveau": _r(713, 1207), "coeur": _r(29, 65),  "poumon_d": _r(38, 164),  "poumon_g": _r(34, 140),  "foie": _r(219, 533),   "rate": _r(12, 60),   "rein_d": _r(18, 46),  "rein_g": _r(17, 49)},
    "75-80":   {"cerveau": _r(766, 1268), "coeur": _r(34, 70),  "poumon_d": _r(35, 187),  "poumon_g": _r(31, 161),  "foie": _r(274, 540),   "rate": _r(19, 59),   "rein_d": _r(16, 48),  "rein_g": _r(18, 50)},
    "80-85":   {"cerveau": _r(860, 1284), "coeur": _r(41, 73),  "poumon_d": _r(34, 194),  "poumon_g": _r(34, 164),  "foie": _r(288, 574),   "rate": _r(18, 72),   "rein_d": _r(15, 52),  "rein_g": _r(22, 54)},
    "85-90":   {"cerveau": _r(890, 1404), "coeur": _r(42, 86),  "poumon_d": _r(36, 228),  "poumon_g": _r(36, 192),  "foie": _r(299, 637),   "rate": _r(16, 82),   "rein_d": _r(18, 62),  "rein_g": _r(20, 64)},
    "90-95":   {"cerveau": _r(931, 1429), "coeur": _r(45, 95),  "poumon_d": _r(52, 236),  "poumon_g": _r(42, 210),  "foie": _r(308, 684),   "rate": _r(20, 86),   "rein_d": _r(19, 67),  "rein_g": _r(22, 66)},
    "95-100":  {"cerveau": _r(999, 1465), "coeur": _r(55, 105), "poumon_d": _r(49, 269),  "poumon_g": _r(48, 232),  "foie": _r(352, 720),   "rate": _r(20, 94),   "rein_d": _r(27, 75),  "rein_g": _r(27, 75)},
    "100-105": {"cerveau": _r(995, 1521),  "coeur": _r(56, 114),  "poumon_d": _r(46, 296),  "poumon_g": _r(43, 251),  "foie": _r(374, 754),   "rate": _r(21, 95),   "rein_d": _r(27, 75),  "rein_g": _r(25, 79)},
    "105-110": {"cerveau": _r(993, 1573),  "coeur": _r(64, 122),  "poumon_d": _r(56, 318),  "poumon_g": _r(45, 289),  "foie": _r(361, 847),   "rate": _r(19, 105),  "rein_d": _r(27, 85),  "rein_g": _r(32, 82)},
    "110-115": {"cerveau": _r(1071, 1499), "coeur": _r(55, 153),  "poumon_d": _r(51, 337),  "poumon_g": _r(41, 303),  "foie": _r(380, 890),   "rate": _r(13, 123),  "rein_d": _r(24, 94),  "rein_g": _r(33, 103)},
    "115-120": {"cerveau": _r(1053, 1633), "coeur": _r(71, 157),  "poumon_d": _r(76, 394),  "poumon_g": _r(55, 365),  "foie": _r(454, 916),   "rate": _r(16, 118),  "rein_d": _r(33, 91),  "rein_g": _r(32, 98)},
    "120-125": {"cerveau": _r(1043, 1685), "coeur": _r(65, 195),  "poumon_d": _r(64, 428),  "poumon_g": _r(56, 374),  "foie": _r(467, 1087),  "rate": _r(29, 127),  "rein_d": _r(32, 98),  "rein_g": _r(43, 97)},
    "125-130": {"cerveau": _r(1099, 1585), "coeur": _r(88, 182),  "poumon_d": _r(77, 425),  "poumon_g": _r(49, 379),  "foie": _r(490, 1180),  "rate": _r(19, 153),  "rein_d": _r(38, 100), "rein_g": _r(44, 102)},
    "130-135": {"cerveau": _r(1092, 1590), "coeur": _r(89, 215),  "poumon_d": _r(46, 520),  "poumon_g": _r(32, 472),  "foie": _r(521, 1187),  "rate": _r(16, 162),  "rein_d": _r(40, 114), "rein_g": _r(40, 122)},
    "135-140": {"cerveau": _r(1043, 1685), "coeur": _r(101, 239), "poumon_d": _r(34, 548),  "poumon_g": _r(54, 446),  "foie": _r(525, 1325),  "rate": _r(28, 166),  "rein_d": _r(42, 112), "rein_g": _r(41, 127)},
    "140-145": {"cerveau": _r(1099, 1609), "coeur": _r(112, 258), "poumon_d": _r(91, 565),  "poumon_g": _r(79, 519),  "foie": _r(453, 1641),  "rate": _r(26, 178),  "rein_d": _r(47, 125), "rein_g": _r(51, 141)},
    "145-150": {"cerveau": _r(1068, 1643), "coeur": _r(162, 216), "poumon_d": _r(78, 618),  "poumon_g": _r(59, 561),  "foie": _r(602, 1622),  "rate": _r(33, 185),  "rein_d": _r(54, 144), "rein_g": _r(59, 157)},
    "150-155": {"cerveau": _r(1068, 1652), "coeur": _r(127, 295), "poumon_d": _r(59, 663),  "poumon_g": _r(45, 589),  "foie": _r(588, 1792),  "rate": _r(28, 212),  "rein_d": _r(48, 150), "rein_g": _r(50, 152)},
    "155-160": {"cerveau": _r(1169, 1643), "coeur": _r(142, 310), "poumon_d": _r(20, 652),  "poumon_g": _r(51, 549),  "foie": _r(725, 1745),  "rate": _r(54, 226),  "rein_d": _r(69, 139), "rein_g": _r(68, 150)},
    "160-165": {"cerveau": _r(1100, 1602), "coeur": _r(160, 336), "poumon_d": _r(99, 711),  "poumon_g": _r(112, 598), "foie": _r(618, 1954),  "rate": _r(27, 223),  "rein_d": _r(58, 152), "rein_g": _r(49, 167)},
    ">=165":   {"cerveau": _r(1173, 1655), "coeur": _r(169, 353), "poumon_d": _r(137, 615), "poumon_g": _r(107, 585), "foie": _r(632, 2004),  "rate": _r(13, 263),  "rein_d": _r(71, 157), "rein_g": _r(71, 161)},
}

MOLINA_POUMONS_TAILLE = {
    h: {
        "moy": round(org["poumon_d"]["moy"] + org["poumon_g"]["moy"], 1),
        "sd": round(_math.sqrt(org["poumon_d"]["sd"]**2 + org["poumon_g"]["sd"]**2), 1),
    }
    for h, org in MOLINA_ORGANES_TAILLE.items()
    if "poumon_d" in org and "poumon_g" in org
}

MOLINA_REINS_TAILLE = {
    h: {
        "moy": round(org["rein_d"]["moy"] + org["rein_g"]["moy"], 1),
        "sd": round(_math.sqrt(org["rein_d"]["sd"]**2 + org["rein_g"]["sd"]**2), 1),
    }
    for h, org in MOLINA_ORGANES_TAILLE.items()
    if "rein_d" in org and "rein_g" in org
}
