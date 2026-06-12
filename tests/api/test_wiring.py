import pytest
from fastapi.testclient import TestClient

from rfe.adapters.llm.mock import MockModelProvider
from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.adapters.persistence.sqlite_repo import SqliteRepository, open_connection
from rfe.api.app import build_app
from rfe.domain.entities import (Candidate, Criterion, CriterionScore,
                                 CriterionType, Evaluation, Feedback,
                                 FeedbackBullet, Role, Rubric)
from rfe.security.audit import AuditLog
from rfe.security.clock import FixedClock
from rfe.usecases.compose_feedback import BulletsPayload
from rfe.usecases.draft_rubric import CriteriaPayload
from rfe.usecases.evaluate_candidate import ScoresPayload
from datetime import datetime, timezone


def mock_provider() -> MockModelProvider:
    return MockModelProvider([
        CriteriaPayload(criteria=[Criterion(id="k8s", name="Kubernetes",
                                            description="5y required",
                                            type=CriterionType.MUST_HAVE)]),
        ScoresPayload(scores=[CriterionScore(criterion_id="k8s", score=1,
                                             evidence="1y")]),
        BulletsPayload(intro="Thank you.",
                       bullets=[FeedbackBullet(criterion_id="k8s",
                                               text="Role required 5y K8s; resume showed 1y.")]),
    ])


def test_build_app_backward_compatible_no_args():
    # existing call shape still works (in-memory, no auth)
    client = TestClient(build_app(model_provider=mock_provider()))
    role = client.post("/roles", json={"title": "SRE", "description": "5y"}).json()
    assert "id" in role


def test_build_app_accepts_injected_sqlite_repos(tmp_path):
    conn = open_connection(str(tmp_path / "wire.db"))
    repos = {
        "roles": SqliteRepository(conn, Role, "roles"),
        "rubrics": SqliteRepository(conn, Rubric, "rubrics"),
        "candidates": SqliteRepository(conn, Candidate, "candidates"),
        "evaluations": SqliteRepository(conn, Evaluation, "evaluations"),
        "feedbacks": SqliteRepository(conn, Feedback, "feedbacks"),
    }
    client = TestClient(build_app(model_provider=mock_provider(), repos=repos))
    role = client.post("/roles", json={"title": "SRE", "description": "5y"}).json()
    # persisted to sqlite
    assert SqliteRepository(conn, Role, "roles").get(role["id"]).title == "SRE"
    conn.close()


def test_build_app_with_audit_records_publish(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLog(str(audit_path),
                     clock=FixedClock(datetime(2026, 1, 1, tzinfo=timezone.utc)))
    client = TestClient(build_app(model_provider=mock_provider(), audit=audit))
    role = client.post("/roles", json={"title": "SRE", "description": "5y"}).json()
    client.post(f"/roles/{role['id']}/rubric/draft")
    client.post(f"/roles/{role['id']}/rubric/publish")
    contents = audit_path.read_text()
    assert '"action": "publish"' in contents


def test_build_app_with_auth_requires_key():
    client = TestClient(build_app(model_provider=mock_provider(),
                                  api_keys={"key-a"}))
    assert client.post("/roles", json={"title": "X"}).status_code == 401
    ok = client.post("/roles", json={"title": "X"},
                     headers={"X-API-Key": "key-a"})
    assert ok.status_code == 200
