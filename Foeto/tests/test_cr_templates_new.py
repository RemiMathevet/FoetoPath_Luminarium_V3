"""Rendu des templates CR proposés (integral / dicte / staff / placenta integral).

Contexte minimal en dur : on vérifie que le template se rend, qu'il ne fuit pas
de repr Python (listes, dicts, lambdas) et que _is_normal trie correctement le
vocabulaire d'autopsie.
"""

import cr_templates
import placenta_cr_templates as pct


def test_is_normal_vocabulaire_autopsie():
    assert cr_templates._is_normal("Solitus")
    assert cr_templates._is_normal("intègre")
    assert cr_templates._is_normal(["Normal"])       # liste homogène
    assert cr_templates._is_normal(["Normales"])
    assert not cr_templates._is_normal(["Kystiques"])
    assert not cr_templates._is_normal(["Normal", "Kystiques"])  # une seule suffit


def _ctx_foetus():
    case = {"numero_dossier": "TEST01", "sexe": "M", "type_issue": "IMG",
            "terme": {"sa": 34, "jours": 1}, "indication_examen": "RCIU"}
    modules = {
        "macro_frais": {"etat": "Frais", "maceration": {"maroun_score": 0},
                        "morphologie": {"crane": {"status": "normal"},
                                   "mains": {"status": "anormal",
                                             "details": ["Hockey stick"]}}},
        "macro_autopsie": {"ouverture": {"situs": "Solitus"},
                           "retroperitoine": {"reins": {"aspects": ["Kystiques"]}},
                           "thorax": {"pericarde": ["Normal"]}},
        "radio": {"terme": {"sa": 34}, "vertebres": {"aspects": ["Normales"]},
                  "hpo_codes": [{"code": "HP:0002983", "term_fr": "Micromelie"}]},
        "computed_biometrics": {"biometries": {}},
    }
    modules["macro_frais"]["biometries"] = {"masse": 1442, "vt": 415, "pied": 60}
    return cr_templates.build_cr_context(case, modules,
                                         modules["computed_biometrics"])


LEAKS = ("<function", "<lambda", "{'", "['")


def test_render_templates_foetus():
    ctx = _ctx_foetus()
    for tid in ("service", "integral", "dicte", "staff"):
        out = cr_templates.render_cr(tid, ctx)
        assert not out.startswith("Erreur"), out[:200]
        assert "TEST01" in out
        assert "Hockey stick" in out            # anomalie externe remontée
        if tid != "staff":                      # la fiche staff ne détaille pas les viscères
            assert "ystiques" in out            # anomalie viscérale remontée
        for leak in LEAKS:
            assert leak not in out, f"{tid} fuit {leak!r}"


def test_split_autopsie_valeurs_cardiaques_attendues():
    """Crosse gauche / FO perméable décrivent le normal, pas une anomalie."""
    ctx = {"coeur": {"crosse": "Gauche", "foramen_ovale": "FO perméable",
                     "quatre_cav": "Équilibrées"}}
    res = cr_templates._split_autopsie(ctx)
    assert "Cœur" in res["normales"]
    assert not any("Cœur" in a for a in res["anomalies"])
    ctx["coeur"]["vg_ej"] = {"civ_diam": "1mm"}          # unité déjà dans la valeur
    res = cr_templates._split_autopsie(ctx)
    assert "Cœur : CIV 1mm" in res["anomalies"]


def test_render_placenta():
    case = {"numero_dossier": "TEST02", "statut": "actif"}
    modules = {"macro_frais": {"forme": "Ovale", "completude": ["Complète"],
                               "grand_axe_cm": 16, "petit_axe_cm": 13,
                               "cordon": {"insertion": "Paracentrale"}}}
    ctx = pct.build_cr_context(case, modules)
    for tid in ("service", "integral"):
        out = pct.render_cr(tid, ctx)
        assert not out.startswith("Erreur"), out[:200]
        assert "TEST02" in out and "paracentrale" in out.lower()
        for leak in LEAKS:
            assert leak not in out, f"placenta/{tid} fuit {leak!r}"
    assert "Redline" in pct.render_cr("integral", ctx)   # référentiels nommés


# ── Mise en page « collable dans Word » ──────────────────────────────────────

def test_word_html_mise_en_page():
    from cr_shared_bp import _cr_text_to_word_html
    txt = ("COMPTE-RENDU\n"
           "============\n"
           "\n"
           "CONCLUSION\n"
           "----------\n"
           "Fœtus présentant :\n"
           "      Une CIV\n"
           "<table border='1'><tr><td>1</td></tr></table>\n"
           "---\n"
           "[Template service v1.0.0]")
    out = _cr_text_to_word_html(txt)
    assert "<br>" not in out                       # Word ferait un seul paragraphe
    assert "var(--" not in out                      # Word ne résout pas les variables CSS
    assert "text-align:center" in out               # titre
    assert "text-transform:uppercase" in out        # en-tête de section
    assert "margin-left:24pt" in out                # retrait des 6 espaces conservé
    assert "<table border='1'>" in out              # tableau des helpers laissé tel quel
    assert out.count("<p") >= 5
