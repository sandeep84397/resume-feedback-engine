from datetime import datetime, timedelta, timezone

import pytest

from rfe.security.clock import FixedClock
from rfe.security.tokens import TokenError, TokenSigner


def at(hours: float) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)


def test_sign_then_verify_roundtrip():
    signer = TokenSigner(secret="s3cret", ttl_hours=168, clock=FixedClock(at(0)))
    token = signer.sign("feedback-123")
    assert signer.verify(token) == "feedback-123"


def test_tampered_token_rejected():
    signer = TokenSigner(secret="s3cret", ttl_hours=168, clock=FixedClock(at(0)))
    token = signer.sign("feedback-123")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(TokenError):
        signer.verify(tampered)


def test_payload_swap_rejected():
    signer = TokenSigner(secret="s3cret", ttl_hours=168, clock=FixedClock(at(0)))
    token = signer.sign("feedback-123")
    parts = token.split(".")
    forged = "feedback-999." + parts[1] + "." + parts[2]
    with pytest.raises(TokenError):
        signer.verify(forged)


def test_expired_token_rejected():
    clock = FixedClock(at(0))
    signer = TokenSigner(secret="s3cret", ttl_hours=1, clock=clock)
    token = signer.sign("feedback-123")
    clock.set(at(1.5))  # 1.5h later, TTL was 1h
    with pytest.raises(TokenError):
        signer.verify(token)


def test_not_yet_expired_token_valid():
    clock = FixedClock(at(0))
    signer = TokenSigner(secret="s3cret", ttl_hours=2, clock=clock)
    token = signer.sign("feedback-123")
    clock.set(at(1.9))
    assert signer.verify(token) == "feedback-123"


def test_wrong_secret_rejected():
    token = TokenSigner("right", 168, FixedClock(at(0))).sign("fb")
    with pytest.raises(TokenError):
        TokenSigner("wrong", 168, FixedClock(at(0))).verify(token)


def test_malformed_token_rejected():
    signer = TokenSigner("s", 168, FixedClock(at(0)))
    for bad in ("", "a", "a.b", "a.b.c.d", "no-dots"):
        with pytest.raises(TokenError):
            signer.verify(bad)
