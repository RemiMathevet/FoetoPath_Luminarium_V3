"""Tests d'intégration des 4 coutures entre le hub, le viewer et la PWA :
liaison dossier↔lame, génération de CR, accès WSI, accès PWA.

Les numéros de dossier sont des fixtures inventées (25P…) : ce répertoire part
dans le miroir public.
"""

import json
import sqlite3

import pytest

_LAMES_SCHEMA = """
CREATE TABLE lames (id INTEGER PRIMARY KEY, nom_lame TEXT UNIQUE,
                    taille_mo REAL, chemin TEXT, storage TEXT DEFAULT 'hot',
                    cold_root TEXT);
CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE slides (slide_id TEXT PRIMARY KEY, tissue_type TEXT);
CREATE TABLE diagnoses (id INTEGER PRIMARY KEY, slide_id TEXT, diagnosis TEXT);
CREATE TABLE annotations (id INTEGER PRIMARY KEY, slide_id TEXT,
                          tissue_type TEXT, ann_class TEXT, label TEXT);
CREATE TABLE organ_status (id INTEGER PRIMARY KEY, slide_id TEXT,
                           organ TEXT, status TEXT);
CREATE TABLE slide_notes (slide_id TEXT PRIMARY KEY, note TEXT);
CREATE TABLE embeddings (id INTEGER PRIMARY KEY, slide_id TEXT, magnification TEXT);
"""

_FOETO_SCHEMA = """
CREATE TABLE foeto_terms (id TEXT PRIMARY KEY, viewer_id TEXT, organe TEXT,
                          cr_description TEXT, cr_section TEXT, label_fr TEXT);
CREATE TABLE foeto_structures (name TEXT, label_fr TEXT, texte_normal TEXT,
                               type TEXT, domain TEXT, sort_order INTEGER);
"""


@pytest.fixture()
def lames_db(tmp_path, foetus_db_ready):
    """lames.db temporaire, injectée dans les settings du hub."""
    from services import lumi

    path = tmp_path / "lames.db"
    conn = sqlite3.connect(path)
    conn.executescript(_LAMES_SCHEMA)
    conn.execute("INSERT INTO config VALUES ('hot_root', '/tmp/hot')")
    conn.commit()
    foetus_db_ready.set_setting(lumi.LUMI_DB_PATH_SETTING, str(path))
    yield conn
    conn.close()


@pytest.fixture()
def foeto_db(tmp_path, monkeypatch):
    """foeto_base temporaire (terminologie), injectée via config.FOETO_DB_PATH."""
    path = tmp_path / "syndromes_foetaux.db"
    conn = sqlite3.connect(path)
    conn.executescript(_FOETO_SCHEMA)
    conn.commit()
    monkeypatch.setattr("config.FOETO_DB_PATH", str(path), raising=False)
    yield conn
    conn.close()


# ── 1. Liaison dossier ↔ placenta ↔ lame ────────────────────────────────────

class TestLiaisonDossierLame:

    def test_lames_du_cas_remontent_avec_diagnostics(self, lames_db):
        from services import lumi

        lames_db.executescript("""
            INSERT INTO lames (nom_lame, chemin) VALUES ('25P1234_1_1', '25P1234/a.mrxs');
            INSERT INTO lames (nom_lame, chemin) VALUES ('25P1234_2_1', '25P1234/b.mrxs');
            INSERT INTO slides VALUES ('25P1234_1_1', 'placenta');
            INSERT INTO diagnoses (slide_id, diagnosis) VALUES ('25P1234_1_1', 'FOETO:PP.PAR-VIL-001');
            INSERT INTO annotations (slide_id, ann_class) VALUES ('25P1234_1_1', 'villite');
        """)
        lames_db.commit()

        data = lumi.get_slides_for_case("25P1234")
        assert data["available"]
        assert data["stats"]["total"] == 2
        assert data["stats"]["in_viewer"] == 1
        assert data["stats"]["diagnosed"] == 1
        noms = sorted(s["nom_lame"] for s in data["slides"])
        assert noms == ["25P1234_1_1", "25P1234_2_1"]

    def test_chemin_resolu_depuis_le_tier_de_stockage(self, lames_db):
        from services import lumi

        lames_db.execute(
            "INSERT INTO lames (nom_lame, chemin, storage, cold_root) "
            "VALUES ('25P5678_1_1', '25P5678/a.mrxs', 'cold', '/tmp/cold')")
        lames_db.execute(
            "INSERT INTO lames (nom_lame, chemin) VALUES ('25P5678_2_1', '25P5678/b.mrxs')")
        lames_db.commit()

        by_name = {s["nom_lame"]: s for s in lumi.get_slides_for_case("25P5678")["slides"]}
        assert by_name["25P5678_1_1"]["full_path"] == "/tmp/cold/25P5678/a.mrxs"
        assert by_name["25P5678_2_1"]["full_path"] == "/tmp/hot/25P5678/b.mrxs"

    def test_prefixe_plus_long_pas_capture(self, lames_db):
        """`_` est un joker LIKE : 25P123 ne doit pas rafler 25P1234.
        Constaté en production, où les deux longueurs de numéro coexistent."""
        from services import lumi

        lames_db.executescript("""
            INSERT INTO lames (nom_lame, chemin) VALUES ('25P123_1_1', 'x/a.mrxs');
            INSERT INTO lames (nom_lame, chemin) VALUES ('25P1234_1_1', 'y/b.mrxs');
            INSERT INTO annotations (slide_id, ann_class) VALUES ('25P1234_1_1', 'villite');
        """)
        lames_db.commit()

        noms = [s["nom_lame"] for s in lumi.get_slides_for_case("25P123")["slides"]]
        assert noms == ["25P123_1_1"]
        assert lumi._load_case_annotations("25P123") == []

    def test_lame_supprimee_hors_comptage(self, lames_db):
        from services import lumi

        lames_db.executescript("""
            INSERT INTO lames (nom_lame, chemin) VALUES ('25P9012_1_1', 'x/a.mrxs');
            INSERT INTO lames (nom_lame, chemin, storage) VALUES ('25P9012_2_1', 'x/b.mrxs', 'deleted');
            INSERT INTO lames (nom_lame, chemin) VALUES ('25P3456_1_1', 'y/c.mrxs');
        """)
        lames_db.commit()

        assert lumi.get_slide_counts(["25P9012", "25P3456"]) == {"25P9012": 1, "25P3456": 1}

    def test_lames_db_absente_ne_casse_pas(self, foetus_db_ready):
        from services import lumi

        foetus_db_ready.set_setting(lumi.LUMI_DB_PATH_SETTING, "/nowhere/lames.db")
        assert lumi.get_slides_for_case("25P1234")["available"] is False
        assert lumi.get_slide_counts(["25P1234"]) == {}


# ── 2. Génération du CR ─────────────────────────────────────────────────────

class TestGenerationCR:

    @pytest.fixture(autouse=True)
    def _terminologie(self, foeto_db):
        foeto_db.executescript("""
            INSERT INTO foeto_structures VALUES
                ('cr_cordon', 'Cordon', 'cordon sans particularité.', 'cr_section', 'placenta', 1),
                ('cr_membranes', 'Membranes', 'membranes sans particularité.', 'cr_section', 'placenta', 2),
                ('cr_villosites', 'Villosités', 'villosités sans particularité.', 'cr_section', 'placenta', 3);
            INSERT INTO foeto_terms VALUES
                ('FOETO:PP.PAR-VIL-001', 'villite', 'parenchyme',
                 'infiltrat lymphocytaire des villosités (villite).', 'cr_villosites', 'Villite chronique'),
                ('FOETO:PP.COR-FUN-002', 'funisite', 'cordon',
                 'infiltrat de la gelée de Wharton (funisite stade 2).', 'cr_cordon', 'Funisite'),
                ('FOETO:PP.PAR-MUE-003', 'muet', 'parenchyme', NULL, 'cr_villosites', 'Signe muet');
        """)
        foeto_db.commit()

    def _lame(self, conn, nom, organ="parenchyme", status="normal"):
        conn.execute("INSERT INTO lames (nom_lame, chemin) VALUES (?, ?)", (nom, "x/" + nom))
        conn.execute("INSERT INTO organ_status (slide_id, organ, status) VALUES (?, ?, ?)",
                     (nom, organ, status))
        conn.commit()

    def test_section_sans_finding_prend_le_texte_normal(self, lames_db, foeto_db):
        from services import lumi

        self._lame(lames_db, "25P1234_1_1")
        desc, concl = lumi.build_composite_micro_cr("25P1234")
        assert desc == "Villosités : villosités sans particularité."
        assert concl == []

    def test_section_sans_organe_examine_est_omise(self, lames_db, foeto_db):
        """Le cordon n'a pas été examiné : pas de ligne « Cordon »."""
        from services import lumi

        self._lame(lames_db, "25P1234_1_1")
        desc, _ = lumi.build_composite_micro_cr("25P1234")
        assert "Cordon" not in desc and "Membranes" not in desc

    def test_diagnostic_remplace_le_normal_et_part_en_conclusion(self, lames_db, foeto_db):
        from services import lumi

        self._lame(lames_db, "25P1234_1_1", status="patho")
        lames_db.execute("INSERT INTO diagnoses (slide_id, diagnosis) "
                         "VALUES ('25P1234_1_1', 'FOETO:PP.PAR-VIL-001.G2')")
        lames_db.commit()

        desc, concl = lumi.build_composite_micro_cr("25P1234")
        assert desc == "Villosités : infiltrat lymphocytaire des villosités."
        assert concl == ["Villite chronique"]

    def test_diagnostic_sans_cr_description_est_ignore(self, lames_db, foeto_db):
        """Piège connu : un terme sans cr_description disparaît en silence."""
        from services import lumi

        self._lame(lames_db, "25P1234_1_1", status="patho")
        lames_db.execute("INSERT INTO diagnoses (slide_id, diagnosis) "
                         "VALUES ('25P1234_1_1', 'FOETO:PP.PAR-MUE-003')")
        lames_db.commit()

        desc, concl = lumi.build_composite_micro_cr("25P1234")
        assert desc == "Villosités : villosités sans particularité."
        assert concl == []

    def test_annotation_surcharge_une_lame_labellisee_normale(self, lames_db, foeto_db):
        from services import lumi

        self._lame(lames_db, "25P1234_1_1", organ="cordon")
        lames_db.executescript("""
            INSERT INTO annotations (slide_id, ann_class) VALUES ('25P1234_1_1', 'funisite');
            INSERT INTO annotations (slide_id, ann_class) VALUES ('25P1234_1_1', 'STRUCT:villosite');
        """)
        lames_db.commit()

        desc, concl = lumi.build_composite_micro_cr("25P1234")
        assert desc == "Cordon : infiltrat de la gelée de Wharton."
        assert concl == ["Funisite"]

    def test_trois_lames_ou_plus_marquent_le_diffus(self, lames_db, foeto_db):
        from services import lumi

        for i in (1, 2, 3):
            self._lame(lames_db, f"25P1234_{i}_1", status="patho")
            lames_db.execute("INSERT INTO diagnoses (slide_id, diagnosis) VALUES (?, ?)",
                             (f"25P1234_{i}_1", "FOETO:PP.PAR-VIL-001"))
        lames_db.commit()

        desc, concl = lumi.build_composite_micro_cr("25P1234")
        assert "(diffus, 3 lames)" in desc
        assert concl == ["Villite chronique (diffus)"]

    def test_cas_sans_labellisation_ne_produit_rien(self, lames_db, foeto_db):
        from services import lumi

        lames_db.execute("INSERT INTO lames (nom_lame, chemin) VALUES ('25P1234_1_1', 'x/a')")
        lames_db.commit()
        assert lumi.build_composite_micro_cr("25P1234") == ("", [])


# ── 3. Accès WSI (proxy viewer) ─────────────────────────────────────────────

class _FakeResponse:
    status_code = 200
    headers = {"Content-Type": "image/jpeg", "Transfer-Encoding": "chunked"}

    def iter_content(self, chunk_size=8192):
        yield b"tuile"


@pytest.fixture()
def viewer_app(flask_app, monkeypatch):
    """flask_app + le proxy viewer, avec l'appel HTTP sortant intercepté.
    `calls` reçoit les kwargs de chaque requête relayée."""
    import viewer_proxy_bp as vp

    calls = []

    def _fake_request(**kwargs):
        calls.append(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(vp.http_requests, "request", _fake_request)
    flask_app.register_blueprint(vp.viewer_proxy_bp)
    flask_app.viewer_calls = calls
    return flask_app


class TestAccesWSI:

    def test_anonyme_n_atteint_pas_le_viewer(self, viewer_app, client):
        resp = client.get("/viewer/slide/25P1234_1_1")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]
        assert viewer_app.viewer_calls == []

    def test_authentifie_relaye_vers_le_port_configure(self, viewer_app, admin_client):
        import db

        db.set_setting("viewer_port", "5999")
        resp = admin_client.get("/viewer/tile/25P1234_1_1?level=3")

        assert resp.status_code == 200
        assert resp.data == b"tuile"
        assert viewer_app.viewer_calls[0]["url"] == \
            "http://127.0.0.1:5999/tile/25P1234_1_1?level=3"

    def test_le_viewer_reste_sur_la_boucle_locale(self, viewer_app, admin_client):
        admin_client.get("/viewer/slide/25P1234_1_1")
        assert viewer_app.viewer_calls[0]["url"].startswith("http://127.0.0.1:")

    def test_en_tetes_hop_by_hop_non_relayees(self, viewer_app, admin_client):
        resp = admin_client.get("/viewer/tile/25P1234_1_1")
        assert "Transfer-Encoding" not in resp.headers

    def test_viewer_injoignable_donne_502(self, viewer_app, admin_client, monkeypatch):
        import viewer_proxy_bp as vp

        def _boom(**kwargs):
            raise vp.http_requests.RequestException("connection refused")

        monkeypatch.setattr(vp.http_requests, "request", _boom)
        assert admin_client.get("/viewer/slide/x").status_code == 502


# ── 4. Accès PWA ────────────────────────────────────────────────────────────

class TestAccesPWA:

    def _submit(self, client, dossier, data, **extra):
        form = {"dossier": dossier, "module": "macro_frais",
                "json_data": json.dumps(data), **extra}
        return client.post("/placenta/api/cases/submit", data=form)

    def test_submit_ecrit_le_json_sur_disque(self, user_client, tmp_path):
        import db

        db.set_setting("data_root", str(tmp_path))
        resp = self._submit(user_client, "25P1234",
                            {"masse_paree_g": 450, "aspect": "normal"})
        assert resp.status_code == 200

        on_disk = tmp_path / "Placentas" / "25P1234" / "25P1234_macro_frais.json"
        assert json.loads(on_disk.read_text())["masse_paree_g"] == 450

    def test_resoumission_plus_vide_bloquee_en_409(self, user_client, tmp_path):
        """Cause réelle de perte de données : resaisie d'un formulaire quasi
        vide sur un cas déjà rempli."""
        import db

        db.set_setting("data_root", str(tmp_path))
        self._submit(user_client, "25P5678",
                     {"masse_paree_g": 450, "aspect": "normal", "cordon": "3 vaisseaux"})

        resp = self._submit(user_client, "25P5678", {"masse_paree_g": 450})
        assert resp.status_code == 409
        body = resp.get_json()
        assert body["error"] == "clobber_blocked"
        assert body["existing_filled"] > body["incoming_filled"]

        on_disk = tmp_path / "Placentas" / "25P5678" / "25P5678_macro_frais.json"
        assert json.loads(on_disk.read_text())["cordon"] == "3 vaisseaux"

    def test_force_1_contourne_le_garde(self, user_client, tmp_path):
        import db

        db.set_setting("data_root", str(tmp_path))
        self._submit(user_client, "25P9012", {"masse_paree_g": 450, "aspect": "normal"})

        resp = self._submit(user_client, "25P9012", {"masse_paree_g": 460}, force="1")
        assert resp.status_code == 200

        on_disk = tmp_path / "Placentas" / "25P9012" / "25P9012_macro_frais.json"
        assert json.loads(on_disk.read_text()) == {"masse_paree_g": 460, "dossier": "25P9012"}

    def test_resoumission_plus_riche_passe(self, user_client, tmp_path):
        import db

        db.set_setting("data_root", str(tmp_path))
        self._submit(user_client, "25P3456", {"masse_paree_g": 450})

        resp = self._submit(user_client, "25P3456",
                            {"masse_paree_g": 450, "aspect": "normal"})
        assert resp.status_code == 200

    def test_submit_audite(self, user_client, tmp_path, audit_db_ready):
        import db

        db.set_setting("data_root", str(tmp_path))
        self._submit(user_client, "25P1234", {"masse_paree_g": 450})

        actions = [e["action"] for e in audit_db_ready.get_recent_logs(10)]
        assert "pwa_submit_placenta" in actions
