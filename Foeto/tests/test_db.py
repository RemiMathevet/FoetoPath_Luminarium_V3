"""Tests pour db.py — CRUD cases foetus, modules, settings."""

import pytest


class TestCrudCases:

    def test_create_case(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        assert isinstance(cid, int)
        assert cid > 0

    def test_get_case(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        case = foetus_db_ready.get_case(cid)
        assert case is not None
        assert case["numero_dossier"] == "24P0001"
        assert case["sexe"] == "M"
        assert case["statut"] == "en_cours"

    def test_get_case_nonexistent(self, foetus_db_ready):
        assert foetus_db_ready.get_case(99999) is None

    def test_get_case_by_numero(self, foetus_db_ready, sample_foetus_case):
        foetus_db_ready.create_case(sample_foetus_case)
        case = foetus_db_ready.get_case_by_numero("24P0001")
        assert case is not None
        assert case["nom_mere"] == "DUPONT"

    def test_get_case_by_numero_not_found(self, foetus_db_ready):
        assert foetus_db_ready.get_case_by_numero("INEXISTANT") is None

    def test_update_case(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        assert foetus_db_ready.update_case(cid, {"sexe": "F", "terme_issue": "28"})
        case = foetus_db_ready.get_case(cid)
        assert case["sexe"] == "F"
        assert case["terme_issue"] == "28 SA"

    def test_update_case_empty_data(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        assert foetus_db_ready.update_case(cid, {}) is True

    def test_update_ignores_unknown_fields(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        assert foetus_db_ready.update_case(cid, {"unknown_field": "value"}) is True

    def test_delete_case(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        assert foetus_db_ready.delete_case(cid) is True
        assert foetus_db_ready.get_case(cid) is None

    def test_delete_nonexistent(self, foetus_db_ready):
        assert foetus_db_ready.delete_case(99999) is False

    def test_list_cases(self, foetus_db_ready):
        foetus_db_ready.create_case({"numero_dossier": "A001", "statut": "en_cours"})
        foetus_db_ready.create_case({"numero_dossier": "A002", "statut": "archivé"})
        cases = foetus_db_ready.list_cases()
        assert len(cases) == 2

    def test_list_cases_filter_statut(self, foetus_db_ready):
        foetus_db_ready.create_case({"numero_dossier": "B001", "statut": "en_cours"})
        foetus_db_ready.create_case({"numero_dossier": "B002", "statut": "archivé"})
        en_cours = foetus_db_ready.list_cases(statut="en_cours")
        assert all(c["statut"] == "en_cours" for c in en_cours)

    def test_list_cases_search(self, foetus_db_ready):
        foetus_db_ready.create_case({"numero_dossier": "24P1234"})
        foetus_db_ready.create_case({"numero_dossier": "24P5678"})
        results = foetus_db_ready.list_cases(search="1234")
        assert len(results) == 1
        assert results[0]["numero_dossier"] == "24P1234"

    def test_duplicate_numero_creates_second(self, foetus_db_ready, sample_foetus_case):
        foetus_db_ready.create_case(sample_foetus_case)
        cid2 = foetus_db_ready.create_case(sample_foetus_case)
        assert cid2 is not None

    def test_timestamps_set_on_create(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        case = foetus_db_ready.get_case(cid)
        assert case["created_at"] is not None
        assert case["updated_at"] is not None


class TestModuleData:

    def test_save_and_get_module(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        data = {"poids": 1200, "taille": 32}
        assert foetus_db_ready.save_module_data(cid, "biometries", data)
        result = foetus_db_ready.get_module_data(cid, "biometries")
        assert result == data

    def test_get_module_nonexistent(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        assert foetus_db_ready.get_module_data(cid, "inexistant") is None

    def test_upsert_module(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        foetus_db_ready.save_module_data(cid, "externe", {"note": "v1"})
        foetus_db_ready.save_module_data(cid, "externe", {"note": "v2"})
        result = foetus_db_ready.get_module_data(cid, "externe")
        assert result["note"] == "v2"

    def test_get_all_modules(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        foetus_db_ready.save_module_data(cid, "externe", {"a": 1})
        foetus_db_ready.save_module_data(cid, "interne", {"b": 2})
        all_mods = foetus_db_ready.get_all_modules(cid)
        assert "externe" in all_mods
        assert "interne" in all_mods
        assert all_mods["externe"]["data"]["a"] == 1

    def test_module_updates_case_timestamp(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        case_before = foetus_db_ready.get_case(cid)
        import time
        time.sleep(0.05)
        foetus_db_ready.save_module_data(cid, "radio", {"finding": "normal"})
        case_after = foetus_db_ready.get_case(cid)
        assert case_after["updated_at"] >= case_before["updated_at"]

    def test_cascade_delete_modules(self, foetus_db_ready, sample_foetus_case):
        cid = foetus_db_ready.create_case(sample_foetus_case)
        foetus_db_ready.save_module_data(cid, "externe", {"a": 1})
        foetus_db_ready.delete_case(cid)
        assert foetus_db_ready.get_module_data(cid, "externe") is None


class TestSettings:

    def test_get_default_setting(self, foetus_db_ready):
        val = foetus_db_ready.get_setting("data_root")
        assert val == ""

    def test_set_and_get_setting(self, foetus_db_ready):
        foetus_db_ready.set_setting("data_root", "/mnt/data")
        assert foetus_db_ready.get_setting("data_root") == "/mnt/data"

    def test_get_setting_with_default(self, foetus_db_ready):
        assert foetus_db_ready.get_setting("unknown_key", "fallback") == "fallback"

    def test_get_all_settings(self, foetus_db_ready):
        settings = foetus_db_ready.get_all_settings()
        assert isinstance(settings, dict)
        assert "data_root" in settings


class TestImportJson:

    def test_import_new_case(self, foetus_db_ready, tmp_data_dir):
        import json
        from pathlib import Path
        json_data = {
            "case_admin": {
                "numero_dossier": "IMP001",
                "sexe": "F",
                "terme_issue": "22",
            },
            "atcd_maternels": {"age": 32, "tabac": False},
        }
        json_path = Path(tmp_data_dir) / "import_test.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")

        cid = foetus_db_ready.import_case_from_json(json_path)
        assert cid is not None
        case = foetus_db_ready.get_case(cid)
        assert case["numero_dossier"] == "IMP001"
        mod = foetus_db_ready.get_module_data(cid, "atcd_maternels")
        assert mod["age"] == 32

    def test_import_updates_existing(self, foetus_db_ready, tmp_data_dir):
        import json
        from pathlib import Path
        foetus_db_ready.create_case({"numero_dossier": "IMP002", "sexe": "M"})

        json_data = {"case_admin": {"numero_dossier": "IMP002", "sexe": "F"}}
        json_path = Path(tmp_data_dir) / "import_update.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")

        cid = foetus_db_ready.import_case_from_json(json_path)
        case = foetus_db_ready.get_case(cid)
        assert case["sexe"] == "F"

    def test_import_nonexistent_file(self, foetus_db_ready):
        assert foetus_db_ready.import_case_from_json("/nonexistent.json") is None
