import pytest

from rfe.adapters.llm.mock import MockModelProvider
from rfe.domain.entities import (Candidate, Criterion, CriterionScore,
                                 CriterionType, Evaluation, EvaluationStatus,
                                 FeedbackBullet, Rubric)
from rfe.domain.errors import DomainError
from rfe.usecases.compose_feedback import BulletsPayload, ComposeFeedback


def make_rubric() -> Rubric:
    r = Rubric(id="r1", role_id="role1", criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
    ])
    r.publish()
    return r


def make_candidate() -> Candidate:
    return Candidate(id="cand1", role_id="role1", name="A", email="a@x.com",
                     resume_text="2 years kubernetes")


# --- empty / whitespace resume_text is rejected at the domain boundary ---

def test_empty_resume_text_rejected():
    with pytest.raises(ValueError):
        Candidate(id="c", role_id="r", name="A", email="a@x.com", resume_text="")


def test_whitespace_resume_text_rejected():
    with pytest.raises(ValueError):
        Candidate(id="c", role_id="r", name="A", email="a@x.com", resume_text="   \n\t ")


def test_resume_text_is_stripped():
    c = Candidate(id="c", role_id="r", name="A", email="a@x.com",
                  resume_text="  hello world  ")
    assert c.resume_text == "hello world"


# --- ComposeFeedback refuses a NEEDS_HUMAN evaluation explicitly ---

def test_compose_rejects_needs_human_evaluation():
    ev = Evaluation(id="e1", candidate_id="cand1", rubric_id="r1", scores=[],
                    status=EvaluationStatus.NEEDS_HUMAN)
    uc = ComposeFeedback(MockModelProvider([]))
    with pytest.raises(DomainError) as exc:
        uc.execute(make_candidate(), make_rubric(), ev, feedback_id="f1")
    assert "evaluation requires human review" in str(exc.value)


# --- Criterion is frozen (immutable) ---

def test_criterion_is_frozen():
    c = Criterion(id="k8s", name="Kubernetes")
    with pytest.raises(Exception):  # pydantic raises ValidationError on frozen mutation
        c.name = "Renamed"
