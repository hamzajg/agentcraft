"""
config.py — Handles resolution between custom Ollama gateway and fallback API base.
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

# Cached values so we only ping the gateway once per process
_resolved_base: str | None = None
_resolved_headers: dict | None = None
_resolved_reason: str | None = None

def get_ollama_config() -> tuple[str, dict, str]:
    """
    Returns (base_url, headers, reason) for use in httpx clients via Ollama APIs.
    
    Tries the custom gateway first. If reachable, returns the gateway with Auth headers.
    If unavailable or not set up, falls back to the direct OLLAMA_API_BASE and attached a reason.
    """
    global _resolved_base, _resolved_headers, _resolved_reason
    if _resolved_base is not None and _resolved_headers is not None:
        return _resolved_base, _resolved_headers, _resolved_reason or ""

    gateway_url = os.getenv("OLLAMA_GATEWAY_URL")
    api_key     = os.getenv("OLLAMA_API_KEY", "")
    fallback    = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

    # If gateway is not even configured, fail fast
    if not gateway_url:
        _resolved_base = fallback
        _resolved_headers = {}
        _resolved_reason = "OLLAMA_GATEWAY_URL not set"
        return _resolved_base, _resolved_headers, _resolved_reason

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Verify if gateway is reachable
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{gateway_url}/api/tags", headers=headers)
            resp.raise_for_status()
            logger.info("[llm config] gateway %s is active", gateway_url)
            _resolved_base = gateway_url
            _resolved_headers = headers
            _resolved_reason = ""
            return _resolved_base, _resolved_headers, _resolved_reason
    except Exception as e:
        reason = f"Gateway unreachable: {type(e).__name__}({e})"
        logger.info("[llm config] %s, falling back to %s", reason, fallback)
        _resolved_base = fallback
        _resolved_headers = {}
        _resolved_reason = reason
        return _resolved_base, _resolved_headers, _resolved_reason
