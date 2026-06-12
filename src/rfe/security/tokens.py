"""Signed, expiring feedback tokens (stdlib hmac + sha256).

Format: "<payload>.<exp_epoch>.<hex_sig>" where
sig = HMAC-SHA256(secret, "<payload>.<exp_epoch>"). Verification is
constant-time; a tampered, forged, expired, or malformed token all raise
the same TokenError so callers cannot distinguish cases (no enumeration)."""
from __future__ import annotations

import hashlib
import hmac
import os

from rfe.security.clock import Clock, SystemClock

DEFAULT_TTL_HOURS = 168  # 7 days


class TokenError(Exception):
    """Token is invalid: tampered, forged, expired, or malformed."""


class TokenSigner:
    def __init__(self, secret: str, ttl_hours: int, clock: Clock):
        if not secret:
            raise ValueError("token secret must not be empty")
        self._secret = secret.encode("utf-8")
        self._ttl_hours = ttl_hours
        self._clock = clock

    @classmethod
    def from_env(cls, clock: Clock | None = None) -> "TokenSigner":
        secret = os.environ.get("RFE_TOKEN_SECRET", "")
        ttl = int(os.environ.get("RFE_TOKEN_TTL_HOURS", str(DEFAULT_TTL_HOURS)))
        return cls(secret=secret, ttl_hours=ttl, clock=clock or SystemClock())

    def _mac(self, signed_part: str) -> str:
        return hmac.new(self._secret, signed_part.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    def sign(self, payload: str) -> str:
        exp = int(self._clock.now().timestamp()) + self._ttl_hours * 3600
        signed_part = f"{payload}.{exp}"
        return f"{signed_part}.{self._mac(signed_part)}"

    def verify(self, token: str) -> str:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenError("malformed token")
        payload, exp_str, sig = parts
        expected = self._mac(f"{payload}.{exp_str}")
        if not hmac.compare_digest(expected, sig):
            raise TokenError("bad signature")
        try:
            exp = int(exp_str)
        except ValueError:
            raise TokenError("malformed expiry") from None
        if int(self._clock.now().timestamp()) >= exp:
            raise TokenError("expired token")
        return payload
