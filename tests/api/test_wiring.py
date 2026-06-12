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


# --- Phase 3 Wiring tests ---

from cryptography.fernet import Fernet

from rfe.adapters.persistence.encrypted_repo import EncryptedCandidateRepository
from rfe.security.crypto import FieldCipher


def test_build_app_still_backward_compatible_no_args():
    # bare call shape unchanged
    client = TestClient(build_app(model_provider=mock_provider()))
    assert client.post("/roles", json={"title": "X"}).status_code == 200


def test_created_at_stamped_on_candidate_create():
    clock = FixedClock(datetime(2026, 6, 1, tzinfo=timezone.utc))
    client = TestClient(build_app(model_provider=mock_provider(), clock=clock))
    role = client.post("/roles", json={"title": "SRE"}).json()
    cand = client.post(f"/roles/{role['id']}/candidates",
                       json={"name": "A", "email": "a@x.com",
                             "resume_text": "hi"}).json()
    assert cand["created_at"].startswith("2026-06-01")


def test_rbac_viewer_blocked_from_write():
    client = TestClient(build_app(model_provider=mock_provider(),
                                  api_keys={"vk": "viewer"}))
    assert client.post("/roles", json={"title": "X"},
                       headers={"X-API-Key": "vk"}).status_code == 403


def test_rbac_recruiter_can_write_but_not_delete():
    client = TestClient(build_app(model_provider=mock_provider(),
                                  api_keys={"rk": "recruiter"}))
    h = {"X-API-Key": "rk"}
    role = client.post("/roles", json={"title": "X"}, headers=h).json()
    cand = client.post(f"/roles/{role['id']}/candidates",
                       json={"name": "A", "email": "a@x.com", "resume_text": "hi"},
                       headers=h).json()
    assert client.delete(f"/candidates/{cand['id']}", headers=h).status_code == 403


def test_admin_can_erase_candidate():
    client = TestClient(build_app(model_provider=mock_provider(),
                                  api_keys={"ak": "admin"}))
    h = {"X-API-Key": "ak"}
    role = client.post("/roles", json={"title": "X"}, headers=h).json()
    cand = client.post(f"/roles/{role['id']}/candidates",
                       json={"name": "A", "email": "a@x.com", "resume_text": "hi"},
                       headers=h).json()
    assert client.delete(f"/candidates/{cand['id']}", headers=h).status_code in (200, 204)


def test_bare_set_api_keys_still_admin():
    # Phase 2 call shape: api_keys as a set -> every key is admin
    client = TestClient(build_app(model_provider=mock_provider(),
                                  api_keys={"key-a"}))
    assert client.post("/roles", json={"title": "X"}).status_code == 401
    assert client.post("/roles", json={"title": "X"},
                       headers={"X-API-Key": "key-a"}).status_code == 200


def test_ui_served_when_enabled():
    client = TestClient(build_app(model_provider=mock_provider(), serve_ui=True))
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_encrypted_candidate_repo_used_when_cipher_passed(tmp_path):
    conn = open_connection(str(tmp_path / "w.db"))
    backing = SqliteRepository(conn, Candidate, "candidates")
    repos = {"candidates": EncryptedCandidateRepository(
        backing, FieldCipher(Fernet.generate_key()))}
    client = TestClient(build_app(model_provider=mock_provider(), repos=repos))
    role = client.post("/roles", json={"title": "X"}).json()
    client.post(f"/roles/{role['id']}/candidates",
                json={"name": "Secret", "email": "s@x.com", "resume_text": "hi"})
    raw = conn.execute("SELECT payload FROM candidates").fetchone()[0]
    assert "s@x.com" not in raw   # encrypted at rest
    conn.close()


def test_ui_shell_public_when_auth_enabled():
    # blocker regression: key-entry SPA must load without a key; API stays guarded
    client = TestClient(build_app(model_provider=mock_provider(), serve_ui=True,
                                  api_keys={"ak": "admin"}))
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.post("/roles", json={"title": "SRE"}).status_code == 401
    assert client.post("/roles", json={"title": "SRE"},
                       headers={"X-API-Key": "ak"}).status_code == 200
