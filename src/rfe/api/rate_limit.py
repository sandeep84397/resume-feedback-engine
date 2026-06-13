"""Per-client fixed-window rate limiting (inbound-adapter layer).

A lightweight in-process limiter: each client (identified by API key, else
source IP) gets `limit` requests per `window_seconds`. Over the limit -> 429
with a Retry-After header. Public feedback paths (/f/) are exempt so candidates
viewing their feedback are never throttled by recruiter traffic.

In-process and best-effort: it protects a single instance against bursts and
brute-force key guessing. For multi-instance deployments, also rate-limit at the
reverse proxy. The clock is injected for deterministic testing.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

PUBLIC_PREFIXES = ("/f/",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, clock, limit: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self._clock = clock
        self._limit = limit
        self._window = window_seconds
        # client_id -> (window_start_epoch, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    def _client_id(self, request) -> str:
        key = request.headers.get("X-API-Key")
        if key:
            return f"key:{key}"
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    async def dispatch(self, request, call_next):
        if request.url.path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        now = self._clock.now().timestamp()
        cid = self._client_id(request)
        window_start, count = self._buckets.get(cid, (now, 0))

        if now - window_start >= self._window:
            window_start, count = now, 0  # window expired -> reset

        if count >= self._limit:
            retry_after = int(self._window - (now - window_start)) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded; slow down"},
                headers={"Retry-After": str(retry_after)},
            )

        self._buckets[cid] = (window_start, count + 1)
        return await call_next(request)
