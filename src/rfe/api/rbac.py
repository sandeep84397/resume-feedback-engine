"""Role-based access control (inbound-adapter layer).

RoleResolverMiddleware authenticates the X-API-Key against a key->role map
(constant-time) and stashes the role on request.state.role; missing/invalid
key -> 401. Public feedback paths (/f/) are skipped, matching Phase 2.

require_role(min_role) is a FastAPI dependency: 403 when the caller's role is
below min_role in the hierarchy viewer < recruiter < admin.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from rfe.api.auth import role_for_key

PUBLIC_PREFIXES = ("/f/",)
_RANK = {"viewer": 1, "recruiter": 2, "admin": 3}


class RoleResolverMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, keymap: dict[str, str]):
        super().__init__(app)
        self._keymap = keymap

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)
        presented = request.headers.get("X-API-Key", "")
        role = role_for_key(presented, self._keymap) if presented else None
        if role is None:
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        request.state.role = role
        return await call_next(request)


def require_role(min_role: str):
    min_rank = _RANK[min_role]

    def _guard(request: Request) -> None:
        role = getattr(request.state, "role", None)
        if role is None or _RANK.get(role, 0) < min_rank:
            raise HTTPException(status_code=403, detail="insufficient role")

    return _guard
