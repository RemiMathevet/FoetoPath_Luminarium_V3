"""
Magos service: queue-based LLM broker client for FoetoPath.
Replaces the Ollama direct-generation layer with Magos job queue semantics.
Uses only Python standard library (urllib) — no 'requests' dependency.

Magos API (port 8200):
  GET  /health          → {status, llm, queued, running}
  GET  /models          → {models: [{name, model, id, path, loaded}], current, tags}
  POST /jobs            → {uuid, status: "queued", ...}
  GET  /jobs/{uuid}     → {uuid, status, response, thinking, ...}
  GET  /jobs/{uuid}/wait?timeout=N → blocks until done
"""

import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import db

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _magos_url() -> str:
    """Get Magos URL from settings, default http://localhost:8200."""
    url = db.get_setting("magos_url", "http://localhost:8200").strip()
    if not url:
        return "http://localhost:8200"
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def _http_get(url: str, timeout: int = 10) -> dict:
    """GET request returning parsed JSON."""
    req = Request(url)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    """POST JSON request returning parsed JSON."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_magos_status() -> dict:
    """
    Check if Magos is running and list available models.

    Returns:
        {running: bool, url: str, models: [{name: str, loaded: bool}]}

    Raises RuntimeError if Magos is unreachable.
    """
    url = _magos_url()

    # 1. Health check
    try:
        health = _http_get(f"{url}/health", timeout=5)
    except (URLError, OSError) as e:
        log.warning("Magos non joignable sur %s: %s", url, e)
        return {"running": False, "url": url, "models": []}

    # 2. List models
    try:
        data = _http_get(f"{url}/models", timeout=5)
        models = []
        for m in data.get("models", []):
            models.append({
                "name": m.get("name", m.get("model", "")),
                "loaded": m.get("loaded", False),
            })
        return {
            "running": True,
            "url": url,
            "llm": health.get("llm", ""),
            "queued": health.get("queued", 0),
            "models": models,
        }
    except (URLError, OSError) as e:
        # Health OK but models endpoint failed — still report as running
        log.warning("Magos /models echoue: %s", e)
        return {"running": True, "url": url, "models": []}


def submit_job(
    prompt: str,
    model: str = None,
    system: str = None,
    options: dict = None,
    timeout_s: int = 0,
    priority: int = 5,
) -> str:
    """
    Submit a job to the Magos queue.

    Args:
        prompt:    The user prompt.
        model:     Model name (defaults to llm_model setting / Qwen3.6-35B).
        system:    Optional system prompt.
        options:   Optional dict of generation options (temperature, top_p, ...).
        timeout_s: Server-side generation timeout (0 = server default).
        priority:  Queue priority 1-9, default 5 (lower = higher priority).

    Returns:
        Job UUID string.

    Raises RuntimeError on submission failure.
    """
    if model is None:
        model = db.get_setting("llm_model", "Qwen3.6-35B")

    url = _magos_url()

    payload = {
        "model": model,
        "prompt": prompt,
        "priority": priority,
        "client_id": "foetopath",
    }
    if system:
        payload["system"] = system
    if options:
        payload["options"] = options
    if timeout_s > 0:
        payload["timeout_s"] = timeout_s

    try:
        result = _http_post_json(f"{url}/jobs", payload, timeout=15)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(
            f"Magos POST /jobs echoue ({e.code}): {body}"
        ) from e
    except (URLError, OSError) as e:
        raise RuntimeError(f"Magos non accessible sur {url}: {e}") from e

    uuid = result.get("uuid")
    if not uuid:
        raise RuntimeError(f"Magos /jobs n'a pas retourne d'uuid: {result}")

    log.info("Job soumis a Magos: %s (model=%s, priority=%d)", uuid, model, priority)
    return uuid


def wait_job(job_uuid: str, timeout: int = 300) -> dict:
    """
    Wait for a Magos job to complete (long-poll).

    Args:
        job_uuid: The UUID returned by submit_job.
        timeout:  Max seconds to wait (default 300).

    Returns:
        {status, response, thinking, tokens_in, tokens_out, duration_s, error}

    Raises RuntimeError on network error or job failure.
    """
    url = _magos_url()

    try:
        result = _http_get(
            f"{url}/jobs/{job_uuid}/wait?timeout={timeout}",
            timeout=timeout + 10,  # urllib timeout slightly longer than server wait
        )
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(
            f"Magos wait echoue ({e.code}): {body}"
        ) from e
    except (URLError, OSError) as e:
        raise RuntimeError(
            f"Magos non accessible lors du wait {job_uuid}: {e}"
        ) from e

    status = result.get("status", "unknown")

    if status == "failed":
        error_msg = result.get("error", "erreur inconnue")
        raise RuntimeError(f"Job Magos {job_uuid} echoue: {error_msg}")

    if status == "cancelled":
        raise RuntimeError(f"Job Magos {job_uuid} annule")

    if status != "done":
        raise RuntimeError(
            f"Job Magos {job_uuid} non termine apres {timeout}s (status={status})"
        )

    return {
        "status": status,
        "response": result.get("response", ""),
        "thinking": result.get("thinking", ""),
        "tokens_in": result.get("tokens_in", 0),
        "tokens_out": result.get("tokens_out", 0),
        "duration_s": result.get("duration_s", 0),
        "error": result.get("error"),
    }


def run_generation(
    prompt: str,
    model: str = None,
    system: str = None,
    options: dict = None,
    timeout: int = 300,
) -> dict:
    """
    Convenience wrapper: submit a job then wait for completion.

    Args:
        prompt:  The user prompt.
        model:   Model name (defaults to llm_model setting / Qwen3.6-35B).
        system:  Optional system prompt.
        options: Optional dict of generation options.
        timeout: Max seconds to wait for completion (default 300).

    Returns:
        {response, thinking, tokens_in, tokens_out, duration_s}

    Raises RuntimeError on any failure.
    """
    uuid = submit_job(prompt, model=model, system=system, options=options)
    result = wait_job(uuid, timeout=timeout)

    log.info(
        "Magos generation terminee: %s — %d tok_in, %d tok_out, %.1fs",
        uuid,
        result.get("tokens_in", 0),
        result.get("tokens_out", 0),
        result.get("duration_s", 0),
    )

    return {
        "response": result["response"],
        "thinking": result["thinking"],
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "duration_s": result["duration_s"],
    }
