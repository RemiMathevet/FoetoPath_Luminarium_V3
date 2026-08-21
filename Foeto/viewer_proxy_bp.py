"""
FoetoPath — Reverse proxy vers le viewer Luminarium local.

Monte sous /viewer/ — toutes les requêtes sont relayées vers
le viewer local (127.0.0.1:<viewer_port>).
Auth requise : le hub sert de point d'entrée unique.
"""

import logging

import requests as http_requests
from flask import Blueprint, Response, abort, request, stream_with_context

import db
from auth_bp import login_required

log = logging.getLogger(__name__)

viewer_proxy_bp = Blueprint("viewer_proxy", __name__, url_prefix="/viewer")

VIEWER_LOCAL = "http://127.0.0.1"
TILE_TIMEOUT = 10
DEFAULT_TIMEOUT = 15

HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})


def _viewer_base() -> str:
    port = db.get_setting("viewer_port", "5080")
    return f"{VIEWER_LOCAL}:{port}"


def _proxy(subpath: str):
    url = f"{_viewer_base()}/{subpath}"
    if request.query_string:
        url += f"?{request.query_string.decode()}"

    timeout = TILE_TIMEOUT if "/tile/" in subpath else DEFAULT_TIMEOUT

    try:
        resp = http_requests.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers if k.lower() not in ("host",)},
            data=request.get_data(),
            stream=True,
            timeout=timeout,
        )
    except http_requests.RequestException as e:
        log.warning("Viewer proxy error: %s", e)
        abort(502)

    headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    return Response(
        stream_with_context(resp.iter_content(chunk_size=8192)),
        status=resp.status_code,
        headers=headers,
    )


@viewer_proxy_bp.route("/", defaults={"subpath": ""})
@viewer_proxy_bp.route("/<path:subpath>", methods=["GET", "POST"])
@login_required
def proxy_all(subpath):
    return _proxy(subpath)
