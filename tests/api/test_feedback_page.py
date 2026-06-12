from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.api.feedback_page import build_feedback_router
from rfe.domain.entities import Feedback, FeedbackBullet
from rfe.security.clock import FixedClock
from rfe.security.tokens import TokenSigner


def at(hours: float) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)


@pytest.fixture
def ctx():
    repo: InMemoryRepository[Feedback] = InMemoryRepository()
    repo.save(Feedback(id="f1", evaluation_id="e1", candidate_id="c1",
                       intro="Thank you for applying.",
                       bullets=[FeedbackBullet(criterion_id="k8s",
                                               text="Role required 5y K8s; resume showed 1y.")]))
    clock = FixedClock(at(0))
    signer = TokenSigner("secret", ttl_hours=168, clock=clock)
    app = FastAPI()
    app.include_router(build_feedback_router(repo, signer))
    return TestClient(app), signer, clock


def test_valid_token_returns_feedback_json(ctx):
    client, signer, _ = ctx
    token = signer.sign("f1")
    resp = client.get(f"/f/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intro"] == "Thank you for applying."
    assert body["bullets"][0]["criterion_id"] == "k8s"


def test_valid_token_html_format(ctx):
    client, signer, _ = ctx
    token = signer.sign("f1")
    resp = client.get(f"/f/{token}?format=html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Role required 5y K8s" in resp.text


def test_bad_token_is_404(ctx):
    client, _, _ = ctx
    assert client.get("/f/garbage.token.here").status_code == 404


def test_expired_token_is_404(ctx):
    client, signer, clock = ctx
    token = signer.sign("f1")
    clock.set(at(200))  # past 168h TTL
    assert client.get(f"/f/{token}").status_code == 404


def test_valid_token_unknown_feedback_is_404(ctx):
    client, signer, _ = ctx
    token = signer.sign("does-not-exist")
    assert client.get(f"/f/{token}").status_code == 404


def test_response_has_no_scores(ctx):
    client, signer, _ = ctx
    token = signer.sign("f1")
    body = client.get(f"/f/{token}").json()
    assert "scores" not in body
    assert "score" not in str(body)
