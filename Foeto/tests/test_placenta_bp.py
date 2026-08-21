"""Tests d'intégration pour placenta_bp — CRUD cases placenta, modules."""

import json

import pytest


class TestPlacentaAuth:

    def test_api_requires_login(self, client):
        resp = client.get("/placenta/api/cases")
        assert resp.status_code == 401


class TestCasesCrud:

    def test_list_cases_empty(self, admin_client):
        resp = admin_client.get("/placenta/api/cases")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0

    def test_create_case(self, admin_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL001",
            "terme_sa": 38,
            "masse_paree_g": 450,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data

    def test_create_case_missing_numero(self, admin_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "terme_sa": 38,
        })
        assert resp.status_code == 400

    def test_create_case_merge_existing(self, admin_client):
        admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_MERGE",
            "terme_sa": 36,
        })
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_MERGE",
            "terme_sa": 38,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("merged") is True

    def test_get_case(self, admin_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_GET",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.get(f"/placenta/api/cases/{cid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["numero_dossier"] == "PL_GET"
        assert "modules" in data
        assert "photos" in data

    def test_get_case_not_found(self, admin_client):
        resp = admin_client.get("/placenta/api/cases/99999")
        assert resp.status_code == 404

    def test_update_case(self, admin_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_UPD",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.put(f"/placenta/api/cases/{cid}", json={
            "masse_paree_g": 500,
            "forme": "ovale",
        })
        assert resp.status_code == 200

    def test_update_case_not_found(self, admin_client):
        resp = admin_client.put("/placenta/api/cases/99999",
                                json={"forme": "ronde"})
        assert resp.status_code == 404

    def test_update_case_no_data(self, admin_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_NODATA",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.put(f"/placenta/api/cases/{cid}",
                                data="", content_type="application/json")
        assert resp.status_code == 400

    def test_delete_case(self, admin_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_DEL",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.delete(f"/placenta/api/cases/{cid}")
        assert resp.status_code == 200
        resp = admin_client.get(f"/placenta/api/cases/{cid}")
        assert resp.status_code == 404

    def test_delete_case_not_found(self, admin_client):
        resp = admin_client.delete("/placenta/api/cases/99999")
        assert resp.status_code == 404

    def test_list_cases_with_search(self, admin_client):
        admin_client.post("/placenta/api/cases", json={"numero_dossier": "PL_SRCH_A"})
        admin_client.post("/placenta/api/cases", json={"numero_dossier": "PL_SRCH_B"})
        resp = admin_client.get("/placenta/api/cases?q=SRCH_A")
        data = resp.get_json()
        assert data["total"] == 1


class TestModules:

    def _create_case(self, client, numero="PL_MOD"):
        resp = client.post("/placenta/api/cases", json={
            "numero_dossier": numero,
        })
        return resp.get_json()["id"]

    def test_save_and_get_module(self, admin_client):
        cid = self._create_case(admin_client)
        resp = admin_client.put(f"/placenta/api/cases/{cid}/modules/macro_frais",
                                json={"forme": "discoide"})
        assert resp.status_code == 200
        resp = admin_client.get(f"/placenta/api/cases/{cid}/modules/macro_frais")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["forme"] == "discoide"

    def test_get_module_not_found(self, admin_client):
        cid = self._create_case(admin_client, "PL_MOD_NF")
        resp = admin_client.get(f"/placenta/api/cases/{cid}/modules/macro_frais")
        assert resp.status_code == 404

    def test_unknown_module_rejected(self, admin_client):
        cid = self._create_case(admin_client, "PL_MOD_UNK")
        resp = admin_client.get(f"/placenta/api/cases/{cid}/modules/unknown")
        assert resp.status_code == 400

    def test_modules_in_case_detail(self, admin_client):
        cid = self._create_case(admin_client, "PL_MOD_DET")
        admin_client.put(f"/placenta/api/cases/{cid}/modules/micro",
                         json={"villosites": "normales"})
        resp = admin_client.get(f"/placenta/api/cases/{cid}")
        data = resp.get_json()
        assert "micro" in data["modules"]


class TestCheckCase:

    def test_check_existing(self, admin_client):
        admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "PL_CHECK",
        })
        resp = admin_client.get("/placenta/api/cases/check?numero=PL_CHECK")
        data = resp.get_json()
        assert data["exists"] is True
        assert data["case_id"] is not None

    def test_check_nonexistent(self, admin_client):
        resp = admin_client.get("/placenta/api/cases/check?numero=NOPE")
        data = resp.get_json()
        assert data["exists"] is False

    def test_check_empty_numero(self, admin_client):
        resp = admin_client.get("/placenta/api/cases/check?numero=")
        data = resp.get_json()
        assert data["exists"] is False


class TestPwaSubmit:

    def test_submit_creates_case(self, client, tmp_data_dir):
        import db as foetopath_db
        foetopath_db.set_setting("data_root", tmp_data_dir)
        resp = client.post("/placenta/api/cases/submit", data={
            "dossier": "PWA_SUB01",
            "module": "macro_frais",
            "json_data": json.dumps({
                "dossier": "PWA_SUB01",
                "terme": {"sa": 37},
                "foetus": {"sexe": "M"},
                "biometrie": {"masse_paree_g": 400},
            }),
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["case_id"] is not None

    def test_submit_missing_dossier(self, client):
        resp = client.post("/placenta/api/cases/submit", data={
            "module": "macro_frais",
            "json_data": "{}",
        })
        assert resp.status_code == 400

    def test_submit_invalid_json(self, client):
        resp = client.post("/placenta/api/cases/submit", data={
            "dossier": "BAD_JSON",
            "module": "macro_frais",
            "json_data": "{invalid json",
        })
        assert resp.status_code == 400


class TestPermissions:

    def test_spectator_cannot_create(self, spectator_client):
        resp = spectator_client.post("/placenta/api/cases", json={
            "numero_dossier": "SPEC_PL",
        })
        assert resp.status_code == 403

    def test_spectator_can_read(self, admin_client, spectator_client):
        admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "SPEC_PL_RD",
        })
        resp = spectator_client.get("/placenta/api/cases")
        assert resp.status_code == 200

    def test_user_cannot_delete(self, admin_client, user_client):
        resp = admin_client.post("/placenta/api/cases", json={
            "numero_dossier": "USER_PL_DEL",
        })
        cid = resp.get_json()["id"]
        resp = user_client.delete(f"/placenta/api/cases/{cid}")
        assert resp.status_code == 403
