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


def test_salary_band_from_drafted_rubric_can_drive_feedback():
    mock = MockModelProvider([
        CriteriaPayload(
            criteria=[Criterion(id="k8s", name="Kubernetes",
                                type=CriterionType.MUST_HAVE)],
            salary_band_max=130000,
        ),
        ScoresPayload(scores=[CriterionScore(criterion_id="k8s", score=5)]),
        BulletsPayload(intro="Thank you for applying.",
                       bullets=[FeedbackBullet(
                           criterion_id="salary_band",
                           text="The expected compensation was above the budgeted band.")]),
    ])
    client = TestClient(build_app(model_provider=mock))
    role = client.post("/roles", json={
        "title": "SRE",
        "description": "5y K8s. Salary up to 130000.",
    }).json()
    client.post(f"/roles/{role['id']}/rubric/draft")
    pub = client.post(f"/roles/{role['id']}/rubric/publish").json()
    assert pub["salary_band_max"] == 130000
    cand = client.post(f"/roles/{role['id']}/candidates", json={
        "name": "A",
        "email": "a@x.com",
        "resume_text": "strong kubernetes",
        "salary_expectation": 150000,
    }).json()

    ev = client.post(f"/candidates/{cand['id']}/evaluate").json()
    fb = client.post(f"/evaluations/{ev['id']}/feedback/draft").json()

    assert ev["salary_mismatch"] is True
    assert fb["bullets"][0]["criterion_id"] == "salary_band"


def test_experience_and_seniority_mismatch_can_drive_feedback():
    mock = MockModelProvider([
        ScoresPayload(scores=[CriterionScore(criterion_id="android", score=5)]),
        BulletsPayload(intro="Thank you for applying.",
                       bullets=[
                           FeedbackBullet(
                               criterion_id="experience_range",
                               text="The role was scoped for 3-6 years; the profile showed 11."),
                           FeedbackBullet(
                               criterion_id="seniority_level",
                               text="The role targeted SDE 2 or SDE 3; the profile showed SDE 4."),
                       ]),
    ])
    client = TestClient(build_app(model_provider=mock))
    role = client.post("/roles", json={
        "title": "Android SDE",
        "description": "Android role for SDE 2 or SDE 3, 3-6 years experience",
    }).json()
    client.post(f"/roles/{role['id']}/rubric/publish", json={
        "criteria": [{"id": "android", "name": "Android", "type": "must_have"}],
        "experience_min_years": 3,
        "experience_max_years": 6,
        "allowed_seniority_levels": ["SDE 2", "SDE 3"],
    })
    cand = client.post(f"/roles/{role['id']}/candidates", json={
        "name": "A",
        "email": "a@x.com",
        "resume_text": "11 years Android, currently SDE 4",
        "years_experience": 11,
        "current_level": "SDE 4",
    }).json()

    ev = client.post(f"/candidates/{cand['id']}/evaluate").json()
    fb = client.post(f"/evaluations/{ev['id']}/feedback/draft").json()

    assert ev["experience_checked"] is True
    assert ev["experience_mismatch"] is True
    assert ev["seniority_checked"] is True
    assert ev["seniority_mismatch"] is True
    assert [b["criterion_id"] for b in fb["bullets"]] == [
        "experience_range", "seniority_level",
    ]


def test_publish_accepts_manual_rubric_payload_without_draft(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()

    resp = client.post(f"/roles/{role['id']}/rubric/publish", json={
        "criteria": [{
            "id": "k8s",
            "name": "Kubernetes",
            "description": "5y required",
            "type": "must_have",
            "weight": 1,
        }],
        "salary_band_min": 100000,
        "salary_band_max": 130000,
    })

    assert resp.status_code == 200
    rubric = resp.json()
    assert rubric["published"] is True
    assert rubric["criteria"][0]["id"] == "k8s"
    assert rubric["salary_band_min"] == 100000
    assert rubric["salary_band_max"] == 130000


def test_publish_payload_changed_after_publish_creates_new_version(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()
    publish_url = f"/roles/{role['id']}/rubric/publish"
    body = {
        "criteria": [{
            "id": "k8s",
            "name": "Kubernetes",
            "type": "must_have",
            "weight": 1,
        }],
    }
    first = client.post(publish_url, json=body).json()

    resp = client.post(publish_url, json={
        "criteria": [{
            "id": "python",
            "name": "Python",
            "type": "weighted",
            "weight": 1,
        }],
        "salary_band_max": 130000,
    })

    assert resp.status_code == 200
    second = resp.json()
    assert second["id"] != first["id"]
    assert second["version"] == first["version"] + 1
    assert second["salary_band_max"] == 130000


def test_publish_salary_only_update_preserves_existing_criteria(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()
    publish_url = f"/roles/{role['id']}/rubric/publish"
    first = client.post(publish_url, json={
        "criteria": [{
            "id": "k8s",
            "name": "Kubernetes",
            "type": "must_have",
            "weight": 1,
        }],
    }).json()

    resp = client.post(publish_url, json={
        "criteria": [],
        "salary_band_min": 100000,
        "salary_band_max": 130000,
    })

    assert resp.status_code == 200
    second = resp.json()
    assert second["id"] != first["id"]
    assert second["criteria"][0]["id"] == "k8s"
    assert second["salary_band_min"] == 100000
    assert second["salary_band_max"] == 130000


def test_publish_salary_only_update_preserves_unpublished_draft_criteria(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()
    draft = client.post(f"/roles/{role['id']}/rubric/draft").json()

    resp = client.post(f"/roles/{role['id']}/rubric/publish", json={
        "criteria": [],
        "salary_band_min": 100000,
        "salary_band_max": 130000,
    })

    assert resp.status_code == 200
    rubric = resp.json()
    assert rubric["id"] == draft["id"]
    assert rubric["published"] is True
    assert rubric["criteria"][0]["id"] == "k8s"
    assert rubric["salary_band_max"] == 130000


def test_evaluate_uses_latest_published_rubric_version():
    mock = MockModelProvider([
        ScoresPayload(scores=[CriterionScore(criterion_id="python", score=5)]),
    ])
    client = TestClient(build_app(model_provider=mock))
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()
    publish_url = f"/roles/{role['id']}/rubric/publish"
    client.post(publish_url, json={
        "criteria": [{"id": "k8s", "name": "Kubernetes", "type": "must_have"}],
    })
    latest = client.post(publish_url, json={
        "criteria": [{"id": "python", "name": "Python", "type": "must_have"}],
        "salary_band_max": 130000,
    }).json()
    cand = client.post(f"/roles/{role['id']}/candidates", json={
        "name": "A", "email": "a@x.com", "resume_text": "strong python",
        "salary_expectation": 150000,
    }).json()

    ev = client.post(f"/candidates/{cand['id']}/evaluate").json()

    assert ev["rubric_id"] == latest["id"]
    assert ev["salary_mismatch"] is True


def test_publish_payload_is_idempotent_when_unchanged(client):
    role = client.post("/roles", json={"title": "SRE", "description": "5y K8s"}).json()
    publish_url = f"/roles/{role['id']}/rubric/publish"
    body = {
        "criteria": [{
            "id": "k8s",
            "name": "Kubernetes",
            "type": "must_have",
            "weight": 1,
        }],
        "salary_band_min": 100000,
        "salary_band_max": 130000,
    }

    first = client.post(publish_url, json=body)
    second = client.post(publish_url, json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["published"] is True


def test_publish_payload_idempotent_with_normalized_seniority_levels(client):
    role = client.post("/roles", json={"title": "Android", "description": "SDE 2"}).json()
    publish_url = f"/roles/{role['id']}/rubric/publish"
    body = {
        "criteria": [{"id": "android", "name": "Android", "type": "must_have"}],
        "allowed_seniority_levels": ["SDE 2", "sde-3"],
    }

    first = client.post(publish_url, json=body)
    second = client.post(publish_url, json=body)

    assert second.json()["id"] == first.json()["id"]
    assert second.json()["allowed_seniority_levels"] == ["sde2", "sde3"]


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
