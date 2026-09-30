from cr_helpers import render_user_template


def test_variable_vide_supprime_la_phrase_seulement():
    html, text = render_user_template(
        "<p>Le placenta est {{ forme }}. Le cordon est {{ absent }}. Fin.</p>",
        {"forme": "Ovale", "absent": None},
    )
    assert "placenta est ovale" in text          # pas de majuscule initiale
    assert "cordon" not in text                  # phrase entière retirée
    assert "None" not in text and "Non." not in text
    assert "Fin." in text


def test_une_valeur_manquante_ne_mange_pas_toute_la_phrase():
    _, text = render_user_template(
        "<p>Cordon {{ ins }}, long de {{ lg }}cm, {{ spir }}spiralé.</p>",
        {"ins": "central", "lg": 45, "spir": None},
    )
    assert text == "Cordon central, long de 45cm"   # virgule orpheline nettoyée
    assert "spiralé" not in text


def test_decimale_non_coupee_et_parenthese_preservee():
    _, text = render_user_template(
        "<p>Galette {{ f }}, de {{ ga }}cm pour {{ m }}g ({{ ds }}DS, selon Redline).</p>",
        {"f": "Ovale", "ga": None, "m": 363, "ds": 0.44},
    )
    assert text == "Galette ovale, pour 363g (0.44DS, selon Redline)."


def test_membre_entierement_vide_emporte_la_parenthese():
    _, text = render_user_template(
        "<p>Galette de {{ ga }}cm pour {{ m }}g ({{ ds }}DS, selon Redline).</p>",
        {"ga": 16, "m": None, "ds": None},
    )
    assert text == "Galette de 16cm"


def test_dict_et_liste_imbriques_ne_fuient_pas_en_repr():
    _, text = render_user_template(
        "<p>La plaque choriale est {{ pc }}.</p>",
        {"pc": {"etats": ["Normale"], "remarques": None}},
    )
    assert text == "La plaque choriale est normale."


def test_entite_html_ne_coupe_pas_la_phrase():
    _, text = render_user_template(
        "<div>Aspect&nbsp;{{ a }}. On note&nbsp;{{ b }}</div>", {"a": "Normal", "b": None}
    )
    assert text == "Aspect normal."


def test_texte_composite_une_ligne_par_compartiment():
    html, text = render_user_template(
        "<div>{{ composite }}</div>", {"composite": "Villosités : normales\nCordon : normal"}
    )
    assert "<br>" in html
    assert text.count("\n") == 1
