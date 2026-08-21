"""Tests pour placenta_db.py — CRUD cases placenta, modules, photos."""

import pytest


class TestCrudCases:

    def test_create_case(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        assert isinstance(cid, int)

    def test_create_without_numero_raises(self, placenta_db_ready):
        with pytest.raises(ValueError, match="numero_dossier"):
            placenta_db_ready.create_case({"terme_sa": 38})

    def test_get_case(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        case = placenta_db_ready.get_case(cid)
        assert case is not None
        assert case["numero_dossier"] == "24PL001"
        assert case["terme_sa"] == 38
        assert case["masse_paree_g"] == 450

    def test_get_case_nonexistent(self, placenta_db_ready):
        assert placenta_db_ready.get_case(99999) is None

    def test_get_case_by_numero(self, placenta_db_ready, sample_placenta_case):
        placenta_db_ready.create_case(sample_placenta_case)
        case = placenta_db_ready.get_case_by_numero("24PL001")
        assert case is not None

    def test_update_case(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        assert placenta_db_ready.update_case(cid, {"masse_paree_g": 500, "forme": "ovale"})
        case = placenta_db_ready.get_case(cid)
        assert case["masse_paree_g"] == 500
        assert case["forme"] == "ovale"

    def test_update_json_fields(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.update_case(cid, {
            "cordon": {"insertion": "centrale", "longueur_cm": 45},
        })
        case = placenta_db_ready.get_case(cid)
        assert isinstance(case["cordon"], dict)
        assert case["cordon"]["insertion"] == "centrale"

    def test_update_empty_data(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        assert placenta_db_ready.update_case(cid, {}) is False

    def test_update_with_user_tracking(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case, user="dr_martin")
        placenta_db_ready.update_case(cid, {"notes": "RAS"}, user="dr_dupont")
        case = placenta_db_ready.get_case(cid)
        assert case["modified_by"] == "dr_dupont"

    def test_delete_case(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        assert placenta_db_ready.delete_case(cid) is True
        assert placenta_db_ready.get_case(cid) is None

    def test_list_cases(self, placenta_db_ready):
        placenta_db_ready.create_case({"numero_dossier": "PL01"})
        placenta_db_ready.create_case({"numero_dossier": "PL02"})
        cases = placenta_db_ready.list_cases()
        assert len(cases) == 2

    def test_list_cases_search(self, placenta_db_ready):
        placenta_db_ready.create_case({"numero_dossier": "PL100"})
        placenta_db_ready.create_case({"numero_dossier": "PL200"})
        results = placenta_db_ready.list_cases(search="100")
        assert len(results) == 1

    def test_list_cases_filter_statut(self, placenta_db_ready):
        placenta_db_ready.create_case({"numero_dossier": "PLA", "statut": "en_cours"})
        placenta_db_ready.create_case({"numero_dossier": "PLB", "statut": "archivé"})
        en_cours = placenta_db_ready.list_cases(statut="en_cours")
        assert len(en_cours) == 1

    def test_duplicate_numero_raises(self, placenta_db_ready, sample_placenta_case):
        placenta_db_ready.create_case(sample_placenta_case)
        with pytest.raises(Exception):
            placenta_db_ready.create_case(sample_placenta_case)


class TestModuleData:

    def test_save_and_get_module(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        data = {"villosites": "normales", "infarctus": False}
        assert placenta_db_ready.save_module_data(cid, "micro", data)
        result = placenta_db_ready.get_module_data(cid, "micro")
        assert result == data

    def test_upsert_module(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_module_data(cid, "macro_frais", {"v": 1})
        placenta_db_ready.save_module_data(cid, "macro_frais", {"v": 2})
        result = placenta_db_ready.get_module_data(cid, "macro_frais")
        assert result["v"] == 2

    def test_save_module_with_user(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_module_data(cid, "cr", {"text": "ok"}, user="dr_martin")
        result = placenta_db_ready.get_module_data(cid, "cr")
        assert result["text"] == "ok"

    def test_get_all_modules(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_module_data(cid, "macro_frais", {"a": 1})
        placenta_db_ready.save_module_data(cid, "micro", {"b": 2})
        mods = placenta_db_ready.get_all_modules(cid)
        assert "macro_frais" in mods
        assert "micro" in mods

    def test_soft_delete_hides_case(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_module_data(cid, "micro", {"x": 1})
        placenta_db_ready.delete_case(cid)
        assert placenta_db_ready.get_case(cid) is None


class TestPhotos:

    def test_save_and_get_photo(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        pid = placenta_db_ready.save_photo(
            cid, photo_key="macro_01", filename="photo1.jpg",
            label="Face foetale", module="macro_frais",
        )
        assert isinstance(pid, int)
        photos = placenta_db_ready.get_photos(cid)
        assert len(photos) == 1
        assert photos[0]["photo_key"] == "macro_01"
        assert photos[0]["label"] == "Face foetale"

    def test_upsert_photo(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_photo(cid, "key1", "old.jpg")
        placenta_db_ready.save_photo(cid, "key1", "new.jpg")
        photos = placenta_db_ready.get_photos(cid)
        assert len(photos) == 1
        assert photos[0]["filename"] == "new.jpg"

    def test_get_photos_by_module(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_photo(cid, "m1", "a.jpg", module="macro_frais")
        placenta_db_ready.save_photo(cid, "m2", "b.jpg", module="tranches_section")
        frais = placenta_db_ready.get_photos(cid, module="macro_frais")
        assert len(frais) == 1

    def test_soft_delete_hides_from_list(self, placenta_db_ready, sample_placenta_case):
        cid = placenta_db_ready.create_case(sample_placenta_case)
        placenta_db_ready.save_photo(cid, "p1", "x.jpg")
        placenta_db_ready.delete_case(cid)
        cases = placenta_db_ready.list_cases()
        assert all(c["id"] != cid for c in cases)


class TestImportMacroFrais:

    def test_import_new_case(self, placenta_db_ready):
        data = {
            "dossier": "IMP_PL01",
            "terme": {"sa": 36, "jours": 4},
            "foetus": {"masse_g": 2800, "sexe": "M"},
            "biometrie": {"grand_axe_cm": 20, "masse_paree_g": 420},
            "forme": "discoïde",
        }
        cid = placenta_db_ready.import_from_macro_frais_json(data)
        assert cid is not None
        case = placenta_db_ready.get_case(cid)
        assert case["terme_sa"] == 36
        assert case["forme"] == "discoïde"
        mod = placenta_db_ready.get_module_data(cid, "macro_frais")
        assert mod["dossier"] == "IMP_PL01"

    def test_import_without_dossier(self, placenta_db_ready):
        assert placenta_db_ready.import_from_macro_frais_json({}) is None

    def test_import_updates_existing(self, placenta_db_ready):
        placenta_db_ready.create_case({"numero_dossier": "IMP_PL02", "terme_sa": 30})
        data = {
            "dossier": "IMP_PL02",
            "terme": {"sa": 32},
            "foetus": {},
            "biometrie": {},
        }
        cid = placenta_db_ready.import_from_macro_frais_json(data)
        case = placenta_db_ready.get_case(cid)
        assert case["terme_sa"] == 32
