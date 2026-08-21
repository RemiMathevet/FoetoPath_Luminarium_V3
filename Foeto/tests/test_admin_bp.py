"""Tests d'intégration pour admin_bp — CRUD cases, modules, settings."""

import json

import pytest


class TestAdminAuth:

    def test_admin_page_requires_login(self, client):
        resp = client.get("/admin/", follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_api_requires_login(self, client):
        resp = client.get("/admin/api/cases")
        assert resp.status_code == 401


class TestCasesCrud:

    def test_list_cases_empty(self, admin_client):
        resp = admin_client.get("/admin/api/cases")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "cases" in data
        assert data["total"] == 0

    def test_create_case(self, admin_client):
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "25P0001",
            "sexe": "M",
            "terme_issue": "28",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data

    def test_create_case_missing_numero(self, admin_client):
        resp = admin_client.post("/admin/api/cases", json={
            "sexe": "F",
        })
        assert resp.status_code == 400

    def test_create_case_merge_existing(self, admin_client):
        admin_client.post("/admin/api/cases", json={
            "numero_dossier": "MERGE01",
        })
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "MERGE01",
            "sexe": "F",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("merged") is True

    def test_get_case(self, admin_client):
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "GET01",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.get(f"/admin/api/cases/{cid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["numero_dossier"] == "GET01"
        assert "modules" in data

    def test_get_case_not_found(self, admin_client):
        resp = admin_client.get("/admin/api/cases/99999")
        assert resp.status_code == 404

    def test_update_case(self, admin_client):
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "UPD01",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.put(f"/admin/api/cases/{cid}", json={
            "sexe": "F",
            "terme_issue": "32",
        })
        assert resp.status_code == 200

        resp = admin_client.get(f"/admin/api/cases/{cid}")
        assert resp.get_json()["sexe"] == "F"

    def test_update_case_not_found(self, admin_client):
        resp = admin_client.put("/admin/api/cases/99999", json={"sexe": "M"})
        assert resp.status_code == 404

    def test_update_case_no_data(self, admin_client):
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "NODATA01",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.put(f"/admin/api/cases/{cid}",
                                data="", content_type="application/json")
        assert resp.status_code == 400

    def test_delete_case(self, admin_client):
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "DEL01",
        })
        cid = resp.get_json()["id"]
        resp = admin_client.delete(f"/admin/api/cases/{cid}")
        assert resp.status_code == 200
        resp = admin_client.get(f"/admin/api/cases/{cid}")
        assert resp.status_code == 404

    def test_delete_case_not_found(self, admin_client):
        resp = admin_client.delete("/admin/api/cases/99999")
        assert resp.status_code == 404

    def test_list_cases_with_search(self, admin_client):
        admin_client.post("/admin/api/cases", json={"numero_dossier": "SEARCH_AAA"})
        admin_client.post("/admin/api/cases", json={"numero_dossier": "SEARCH_BBB"})
        resp = admin_client.get("/admin/api/cases?q=AAA")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["cases"][0]["numero_dossier"] == "SEARCH_AAA"

    def test_list_cases_with_statut(self, admin_client):
        admin_client.post("/admin/api/cases", json={
            "numero_dossier": "STAT01", "statut": "en_cours",
        })
        admin_client.post("/admin/api/cases", json={
            "numero_dossier": "STAT02", "statut": "archivé",
        })
        resp = admin_client.get("/admin/api/cases?statut=en_cours")
        data = resp.get_json()
        assert all(c["statut"] == "en_cours" for c in data["cases"])


class TestModules:

    def _create_case(self, client, numero="MOD_CASE"):
        resp = client.post("/admin/api/cases", json={
            "numero_dossier": numero,
        })
        return resp.get_json()["id"]

    def test_save_and_get_module(self, admin_client):
        cid = self._create_case(admin_client)
        resp = admin_client.put(f"/admin/api/cases/{cid}/modules/externe", json={
            "poids": 1200,
            "taille": 32,
        })
        assert resp.status_code == 200
        resp = admin_client.get(f"/admin/api/cases/{cid}/modules/externe")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["poids"] == 1200

    def test_get_module_not_found(self, admin_client):
        cid = self._create_case(admin_client, "MOD_NF")
        resp = admin_client.get(f"/admin/api/cases/{cid}/modules/externe")
        assert resp.status_code == 404

    def test_unknown_module_rejected(self, admin_client):
        cid = self._create_case(admin_client, "MOD_UNK")
        resp = admin_client.get(f"/admin/api/cases/{cid}/modules/unknown_module")
        assert resp.status_code == 400

    def test_save_module_no_data(self, admin_client):
        cid = self._create_case(admin_client, "MOD_EMPTY")
        resp = admin_client.put(f"/admin/api/cases/{cid}/modules/externe",
                                data="", content_type="application/json")
        assert resp.status_code == 400

    def test_save_module_case_not_found(self, admin_client):
        resp = admin_client.put("/admin/api/cases/99999/modules/externe",
                                json={"key": "value"})
        assert resp.status_code == 404

    def test_modules_in_case_detail(self, admin_client):
        cid = self._create_case(admin_client, "MOD_DET")
        admin_client.put(f"/admin/api/cases/{cid}/modules/interne",
                         json={"finding": "normal"})
        resp = admin_client.get(f"/admin/api/cases/{cid}")
        data = resp.get_json()
        assert "interne" in data["modules"]


class TestSettings:

    def test_get_settings(self, admin_client):
        resp = admin_client.get("/admin/api/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "viewer_port" in data

    def test_save_settings(self, admin_client):
        resp = admin_client.put("/admin/api/settings", json={
            "viewer_port": "5099",
        })
        assert resp.status_code == 200
        resp = admin_client.get("/admin/api/settings")
        assert resp.get_json()["viewer_port"] == "5099"

    def test_save_settings_no_data(self, admin_client):
        resp = admin_client.put("/admin/api/settings",
                                data="", content_type="application/json")
        assert resp.status_code == 400


class TestPermissions:

    def test_spectator_cannot_create(self, spectator_client):
        resp = spectator_client.post("/admin/api/cases", json={
            "numero_dossier": "SPEC_CREATE",
        })
        assert resp.status_code == 403

    def test_spectator_can_read(self, admin_client, spectator_client):
        admin_client.post("/admin/api/cases", json={
            "numero_dossier": "SPEC_READ",
        })
        resp = spectator_client.get("/admin/api/cases")
        assert resp.status_code == 200

    def test_user_cannot_delete(self, admin_client, user_client):
        resp = admin_client.post("/admin/api/cases", json={
            "numero_dossier": "USER_DEL",
        })
        cid = resp.get_json()["id"]
        resp = user_client.delete(f"/admin/api/cases/{cid}")
        assert resp.status_code == 403

    def test_user_can_create(self, user_client):
        resp = user_client.post("/admin/api/cases", json={
            "numero_dossier": "USER_CREATE",
        })
        assert resp.status_code == 201
