import pytest
from fastapi.testclient import TestClient

from rfe.adapters.llm.mock import MockModelProvider
from rfe.api.app import build_app
from rfe.domain.entities import (Criterion, CriterionScore, CriterionType,
                                 FeedbackBullet)
from rfe.usecases.compose_feedback import BulletsPayload
from rfe.usecases.draft_rubric import CriteriaPayload
from rfe.usecases.evaluate_candidate import ScoresPayload


@pytest.fixture
def client() -> TestClient:
    mock = MockModelProvider([
        CriteriaPayload(criteria=[Criterion(id="k8s", name="Kubernetes",
                                            description="5y required",
                                            type=CriterionType.MUST_HAVE)]),
        ScoresPayload(scores=[CriterionScore(criterion_id="k8s", score=1,
                                             evidence="1y at CompanyX")]),
        BulletsPayload(intro="Thank you for applying.",
                       bullets=[FeedbackBullet(criterion_id="k8s",
                                               text="Role required 5y K8s; resume showed 1y.")]),
    ])
    return TestClient(build_app(model_provider=mock))


def test_full_flow_role_to_sent_feedback(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()

    rubric = client.post(f"/roles/{role['id']}/rubric/draft").json()
    assert rubric["published"] is False

    pub = client.post(f"/roles/{role['id']}/rubric/publish")
    assert pub.status_code == 200

    cand = client.post(f"/roles/{role['id']}/candidates", json={
        "name": "A", "email": "a@x.com", "resume_text": "1y kubernetes",
    }).json()

    ev = client.post(f"/candidates/{cand['id']}/evaluate").json()
    assert ev["status"] == "complete"

    fb = client.post(f"/evaluations/{ev['id']}/feedback/draft").json()
    assert fb["status"] == "drafted"
    assert fb["bullets"][0]["criterion_id"] == "k8s"

    assert client.post(f"/feedback/{fb['id']}/approve").json()["status"] == "approved"
    assert client.post(f"/feedback/{fb['id']}/send").json()["status"] == "sent"


def test_send_before_approve_is_409(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()
    client.post(f"/roles/{role['id']}/rubric/draft")
    client.post(f"/roles/{role['id']}/rubric/publish")
    cand = client.post(f"/roles/{role['id']}/candidates", json={
        "name": "A", "email": "a@x.com", "resume_text": "1y kubernetes",
    }).json()
    ev = client.post(f"/candidates/{cand['id']}/evaluate").json()
    fb = client.post(f"/evaluations/{ev['id']}/feedback/draft").json()
    assert client.post(f"/feedback/{fb['id']}/send").status_code == 409


def test_unknown_ids_are_404(client):
    assert client.post("/candidates/nope/evaluate").status_code == 404


def test_feedback_draft_returns_503_when_model_output_invalid():
    from rfe.ports.model_provider import ModelOutputError
    mock = MockModelProvider([
        CriteriaPayload(criteria=[Criterion(id="k8s", name="Kubernetes",
                                            type=CriterionType.MUST_HAVE)]),
        ScoresPayload(scores=[CriterionScore(criterion_id="k8s", score=1)]),
        ModelOutputError("schema echo"), ModelOutputError("schema echo"),
    ])
    client = TestClient(build_app(model_provider=mock))
    role = client.post("/roles", json={"title": "SRE", "description": "5y"}).json()
    client.post(f"/roles/{role['id']}/rubric/draft")
    client.post(f"/roles/{role['id']}/rubric/publish")
    cand = client.post(f"/roles/{role['id']}/candidates", json={
        "name": "A", "email": "a@x.com", "resume_text": "1y kubernetes"}).json()
    ev = client.post(f"/candidates/{cand['id']}/evaluate").json()
    resp = client.post(f"/evaluations/{ev['id']}/feedback/draft")
    assert resp.status_code == 503
