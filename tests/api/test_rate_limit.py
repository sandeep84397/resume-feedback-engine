from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rfe.api.rate_limit import RateLimitMiddleware


class StepClock:
    """Test clock: advances only when told."""

    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


def make_client(clock, limit=3, window_s=60):
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/f/public")
    def public():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, clock=clock,
                       limit=limit, window_seconds=window_s)
    return TestClient(app)


def test_under_limit_passes():
    clock = StepClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = make_client(clock, limit=3)
    for _ in range(3):
        assert client.get("/ping").status_code == 200


def test_over_limit_returns_429():
    clock = StepClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = make_client(clock, limit=3)
    for _ in range(3):
        client.get("/ping")
    resp = client.get("/ping")
    assert resp.status_code == 429
    assert "retry-after" in {k.lower() for k in resp.headers}


def test_window_resets_after_expiry():
    clock = StepClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = make_client(clock, limit=2, window_s=60)
    client.get("/ping")
    client.get("/ping")
    assert client.get("/ping").status_code == 429
    clock.advance(61)
    assert client.get("/ping").status_code == 200


def test_public_feedback_path_exempt():
    clock = StepClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = make_client(clock, limit=1)
    client.get("/f/public")
    # second hit on /f/ still allowed despite limit=1
    assert client.get("/f/public").status_code == 200


def test_separate_clients_have_separate_buckets():
    clock = StepClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = make_client(clock, limit=1)
    a = client.get("/ping", headers={"X-API-Key": "key-a"})
    b = client.get("/ping", headers={"X-API-Key": "key-b"})
    assert a.status_code == 200 and b.status_code == 200
