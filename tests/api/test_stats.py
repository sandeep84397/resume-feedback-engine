"""Tests for GET /admin/stats — bias-audit aggregate endpoint.

Supports external bias audits (e.g. NYC LL144): returns aggregate counts and
rates only; contains no candidate PII.
"""

import pytest
from fastapi.testclient import TestClient

from rfe.adapters.llm.mock import MockModelProvider
from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.api.app import build_app
from rfe.domain.entities import (
    Criterion,
    CriterionScore,
    CriterionType,
    Evaluation,
    EvaluationStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app_with_evaluations(evaluations: list[Evaluation], api_keys=None):
    ev_repo = InMemoryRepository()
    for ev in evaluations:
        ev_repo.save(ev)
    mock = MockModelProvider([])
    repos = {"evaluations": ev_repo}
    return build_app(model_provider=mock, repos=repos, api_keys=api_keys)


def _make_ev(
    ev_id: str,
    candidate_id: str,
    rubric_id: str,
    scores: list[CriterionScore],
    *,
    status: EvaluationStatus = EvaluationStatus.COMPLETE,
    salary_mismatch: bool = False,
) -> Evaluation:
    return Evaluation(
        id=ev_id,
        candidate_id=candidate_id,
        rubric_id=rubric_id,
        scores=scores,
        status=status,
        salary_mismatch=salary_mismatch,
    )


# ---------------------------------------------------------------------------
# Stats correctness
# ---------------------------------------------------------------------------

def test_stats_empty_repo():
    client = TestClient(_app_with_evaluations([]))
    r = client.get("/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["evaluations"] == 0
    assert body["needs_human"] == 0
    assert body["salary_mismatch_rate"] == 0.0
    assert body["criteria"] == []


def test_stats_counts_and_rates():
    ev1 = _make_ev(
        "e1", "c1", "r1",
        [
            CriterionScore(criterion_id="k8s", score=1, evidence=""),
            CriterionScore(criterion_id="python", score=5, evidence=""),
        ],
    )
    ev2 = _make_ev(
        "e2", "c2", "r1",
        [
            CriterionScore(criterion_id="k8s", score=4, evidence=""),
            CriterionScore(criterion_id="python", score=2, evidence=""),
        ],
        status=EvaluationStatus.NEEDS_HUMAN,
        salary_mismatch=True,
    )
    ev3 = _make_ev(
        "e3", "c3", "r1",
        [
            CriterionScore(criterion_id="k8s", score=5, evidence=""),
            CriterionScore(criterion_id="python", score=5, evidence=""),
        ],
        salary_mismatch=True,
    )

    client = TestClient(_app_with_evaluations([ev1, ev2, ev3]))
    body = client.get("/admin/stats").json()

    assert body["evaluations"] == 3
    assert body["needs_human"] == 1
    # 2 out of 3 evaluations have salary_mismatch=True
    assert abs(body["salary_mismatch_rate"] - 2 / 3) < 1e-6

    by_id = {c["criterion_id"]: c for c in body["criteria"]}

    # k8s: scores 1, 4, 5 → avg = 10/3 ≈ 3.333; pass (>=3): 2 → pass_rate = 2/3
    assert by_id["k8s"]["evaluated"] == 3
    assert abs(by_id["k8s"]["avg_score"] - 10 / 3) < 1e-6
    assert abs(by_id["k8s"]["pass_rate"] - 2 / 3) < 1e-6

    # python: scores 5, 2, 5 → avg = 4.0; pass: 2 → pass_rate = 2/3
    assert by_id["python"]["evaluated"] == 3
    assert abs(by_id["python"]["avg_score"] - 4.0) < 1e-6
    assert abs(by_id["python"]["pass_rate"] - 2 / 3) < 1e-6


def test_stats_no_pii_fields():
    """Response must contain no candidate-identifying fields."""
    ev = _make_ev(
        "e1", "c1", "r1",
        [CriterionScore(criterion_id="k8s", score=3, evidence="")],
    )
    client = TestClient(_app_with_evaluations([ev]))
    body = client.get("/admin/stats").json()

    forbidden = {"name", "email", "resume_text", "salary_expectation",
                 "candidate_id", "rubric_id"}
    def _scan(obj):
        if isinstance(obj, dict):
            for k in obj:
                assert k not in forbidden, f"PII field '{k}' found in stats response"
                _scan(obj[k])
        elif isinstance(obj, list):
            for item in obj:
                _scan(item)

    _scan(body)


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

KEYMAP = {"ak": "admin", "rk": "recruiter", "vk": "viewer"}


def _rbac_client(evaluations=None):
    return TestClient(_app_with_evaluations(evaluations or [], api_keys=KEYMAP))


def test_stats_admin_access():
    assert _rbac_client().get(
        "/admin/stats", headers={"X-API-Key": "ak"}
    ).status_code == 200


def test_stats_viewer_forbidden():
    assert _rbac_client().get(
        "/admin/stats", headers={"X-API-Key": "vk"}
    ).status_code == 403


def test_stats_recruiter_forbidden():
    assert _rbac_client().get(
        "/admin/stats", headers={"X-API-Key": "rk"}
    ).status_code == 403


def test_stats_no_key_unauthorized():
    assert _rbac_client().get("/admin/stats").status_code == 401
