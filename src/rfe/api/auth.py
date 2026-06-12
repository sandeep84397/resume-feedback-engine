"""API-key auth as Starlette middleware.

Every request requires a valid X-API-Key except the public feedback page
(paths under /f/). Keys are compared in constant time. Missing/invalid -> 401.
"""
from __future__ import annotations

import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

PUBLIC_PREFIXES = ("/f/",)


def parse_api_keys(raw: str) -> set[str]:
    return {k.strip() for k in raw.split(",") if k.strip()}


def api_keys_from_env() -> set[str]:
    return parse_api_keys(os.environ.get("RFE_API_KEYS", ""))


def _key_valid(presented: str, valid_keys: set[str]) -> bool:
    # constant-time across all keys: compare every key, never short-circuit
    ok = False
    for key in valid_keys:
        if hmac.compare_digest(presented, key):
            ok = True
    return ok


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_keys: set[str]):
        super().__init__(app)
        self._keys = api_keys

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)
        presented = request.headers.get("X-API-Key", "")
        if not presented or not _key_valid(presented, self._keys):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)
