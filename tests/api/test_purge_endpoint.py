from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.api.app import build_app
from rfe.domain.entities import Candidate
from rfe.security.clock import FixedClock
from tests.api.test_wiring import mock_provider

NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)


def test_admin_purge_endpoint_deletes_stale():
    cands = InMemoryRepository()
    cands.save(Candidate(id="old", role_id="r", name="A", email="a@x.com",
                         resume_text="hi", created_at=NOW - timedelta(days=400)))
    client = TestClient(build_app(
        model_provider=mock_provider(),
        repos={"candidates": cands},
        api_keys={"ak": "admin"},
        clock=FixedClock(NOW),
        retention_days=365,
    ))
    r = client.post("/admin/purge", headers={"X-API-Key": "ak"})
    assert r.status_code == 200
    assert r.json()["candidates_deleted"] == 1


def test_purge_endpoint_requires_admin():
    client = TestClient(build_app(model_provider=mock_provider(),
                                  api_keys={"rk": "recruiter"}))
    assert client.post("/admin/purge",
                       headers={"X-API-Key": "rk"}).status_code == 403
