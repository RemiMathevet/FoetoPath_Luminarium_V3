"""Tests pour divers_db.py — CRUD cas divers (curetage, gémellaire)."""

import pytest


class TestSaveCas:

    def test_create_curetage(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        assert isinstance(cas_id, int)
        assert cas_id > 0

    def test_create_gemellaire(self, divers_db_ready):
        db = divers_db_ready
        data = {"type_cas": "gemellaire", "dossier": "GEM01", "ag_sa": 16}
        cas_id = db.save_cas(data)
        assert cas_id > 0

    def test_invalid_type_cas_raises(self, divers_db_ready):
        db = divers_db_ready
        with pytest.raises(ValueError, match="type_cas invalide"):
            db.save_cas({"type_cas": "unknown"})

    def test_update_cas(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        updated = sample_divers_case.copy()
        updated["id"] = cas_id
        updated["indication"] = "FCS incomplète"
        db.save_cas(updated)
        result = db.load_cas(cas_id)
        assert result["indication"] == "FCS incomplète"

    def test_form_data_serialized(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        result = db.load_cas(cas_id)
        assert isinstance(result["form_data"], dict)
        assert result["form_data"]["fragments_g"] == 15


class TestLoadCas:

    def test_load_existing(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        result = db.load_cas(cas_id)
        assert result is not None
        assert result["type_cas"] == "curetage"
        assert result["dossier"] == "24D001"

    def test_load_nonexistent(self, divers_db_ready):
        db = divers_db_ready
        assert db.load_cas(99999) is None

    def test_load_deleted_returns_none(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        db.soft_delete_cas(cas_id)
        assert db.load_cas(cas_id) is None


class TestListCas:

    def test_list_all(self, divers_db_ready):
        db = divers_db_ready
        db.save_cas({"type_cas": "curetage", "dossier": "C1"})
        db.save_cas({"type_cas": "gemellaire", "dossier": "G1"})
        results = db.list_cas()
        assert len(results) == 2

    def test_list_filter_type(self, divers_db_ready):
        db = divers_db_ready
        db.save_cas({"type_cas": "curetage", "dossier": "C2"})
        db.save_cas({"type_cas": "gemellaire", "dossier": "G2"})
        curetages = db.list_cas(type_cas="curetage")
        assert len(curetages) == 1
        assert curetages[0]["type_cas"] == "curetage"

    def test_list_excludes_deleted(self, divers_db_ready):
        db = divers_db_ready
        cas_id = db.save_cas({"type_cas": "curetage", "dossier": "DEL"})
        db.soft_delete_cas(cas_id)
        results = db.list_cas()
        assert len(results) == 0

    def test_list_pagination(self, divers_db_ready):
        db = divers_db_ready
        for i in range(5):
            db.save_cas({"type_cas": "curetage", "dossier": f"P{i}"})
        page1 = db.list_cas(limit=2, offset=0)
        page2 = db.list_cas(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["dossier"] != page2[0]["dossier"]


class TestSoftDelete:

    def test_soft_delete(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        result = db.soft_delete_cas(cas_id)
        assert result is True

    def test_soft_delete_preserves_data(self, divers_db_ready, sample_divers_case):
        db = divers_db_ready
        cas_id = db.save_cas(sample_divers_case)
        db.soft_delete_cas(cas_id)
        with db._connect() as conn:
            row = conn.execute("SELECT deleted FROM cas_divers WHERE id = ?", (cas_id,)).fetchone()
            assert row["deleted"] == 1
