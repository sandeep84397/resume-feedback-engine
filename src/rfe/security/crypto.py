"""Field-level symmetric encryption for PII at rest.

Wraps cryptography.fernet.Fernet (AES-128-CBC + HMAC-SHA256, authenticated,
random IV per token). We do NOT hand-roll crypto. The key comes from the
RFE_ENCRYPTION_KEY env var (a urlsafe-base64 32-byte Fernet key); it never
lives in the repo or the database.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class FieldCipher:
    """Encrypt/decrypt individual string fields. encrypt() output is a
    urlsafe-base64 Fernet token (str); decrypt() reverses it."""

    def __init__(self, key: bytes | str):
        if isinstance(key, str):
            key = key.encode()
        self._f = Fernet(key)  # raises ValueError on a malformed key

    def encrypt(self, plaintext: str) -> str:
        return self._f.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("cannot decrypt field (wrong key or corrupt data)") from exc


def cipher_from_env() -> FieldCipher | None:
    """Build a FieldCipher from RFE_ENCRYPTION_KEY. Returns None when the env
    var is unset (encryption disabled). Raises ValueError on a malformed key."""
    raw = os.environ.get("RFE_ENCRYPTION_KEY")
    if not raw:
        return None
    try:
        return FieldCipher(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("RFE_ENCRYPTION_KEY is not a valid Fernet key") from exc
