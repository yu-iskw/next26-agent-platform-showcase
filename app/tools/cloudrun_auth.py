from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Final, cast

from google.auth.transport.requests import Request
from google.oauth2 import id_token as id_token_module
from opentelemetry.propagate import inject

_DEFAULT_REFRESH_SKEW_SEC: Final[int] = 120


def tool_api_id_token_audience(base_url: str) -> str | None:
    """Return the OIDC audience (https service origin) or None if calls are unauthenticated."""
    stripped = base_url.strip().rstrip("/")
    if stripped.startswith(("http://localhost", "http://127.0.0.1")):
        return None
    if stripped.startswith("https://"):
        return stripped
    return None


def should_attach_cloud_run_id_token(base_url: str, skip_id_token: bool) -> bool:
    if skip_id_token:
        return False
    return tool_api_id_token_audience(base_url) is not None


def _jwt_exp_unix(token: str) -> float | None:
    try:
        payload_b64 = token.split(".", 1)[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        body = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        exp = body.get("exp")
        if isinstance(exp, (int, float)):
            return float(exp)
    except (ValueError, IndexError, TypeError, json.JSONDecodeError):
        return None
    return None


_cached_audience: str | None = None
_cached_token: str | None = None
_cached_exp_unix: float = 0.0


def _get_fresh_id_token(audience: str) -> tuple[str, float]:
    request = Request()
    raw = id_token_module.fetch_id_token(request, audience)
    token = cast(str, raw)
    exp = _jwt_exp_unix(token) or (time.time() + 3000.0)
    return token, exp


def _get_cached_id_token(audience: str) -> str:
    global _cached_audience, _cached_token, _cached_exp_unix
    now = time.time()
    if audience == _cached_audience and _cached_token and now < _cached_exp_unix - _DEFAULT_REFRESH_SKEW_SEC:
        return _cached_token
    token, exp = _get_fresh_id_token(audience)
    _cached_audience = audience
    _cached_token = token
    _cached_exp_unix = exp
    return token


def authorization_headers_for_tool_api(*, base_url: str, skip_id_token: bool) -> dict[str, str]:
    """Headers for HTTPS calls to a private Cloud Run service (OIDC ID token)."""
    if not should_attach_cloud_run_id_token(base_url, skip_id_token):
        return {}
    audience = tool_api_id_token_audience(base_url)
    if not audience:
        return {}
    token = _get_cached_id_token(audience)
    return {"Authorization": f"Bearer {token}"}


def correlation_headers_for_tool_api() -> dict[str, str]:
    """Outbound correlation: X-Request-ID plus W3C trace context when a span is active."""
    headers: dict[str, str] = {"X-Request-ID": str(uuid.uuid4())}
    carrier: dict[str, str] = {}
    inject(carrier)
    headers.update(carrier)
    return headers
