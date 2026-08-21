"""Proxy vers l'API convergence de foetodata_hub (data.pazuzu.uk)."""

import logging
import requests

import db

log = logging.getLogger(__name__)

_DEFAULT_URL = "http://127.0.0.1:5010"


def _base_url():
    try:
        return db.get_setting("convergence_api_url", _DEFAULT_URL)
    except Exception:
        return _DEFAULT_URL


def query(clinical_text: str, top_k: int = 15) -> list[dict]:
    url = _base_url().rstrip("/") + "/api/convergence/query"
    r = requests.post(url, json={"id": "soffoet", "prompt": clinical_text}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data.get("message", data["error"]))
    return data.get("results", [])[:top_k]
