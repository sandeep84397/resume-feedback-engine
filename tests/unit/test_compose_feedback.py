import pytest

from rfe.adapters.llm.mock import MockModelProvider
from rfe.domain.entities import (Candidate, Criterion, CriterionScore,
                                 CriterionType, Evaluation, FeedbackBullet,
                                 FeedbackStatus, Rubric)
from rfe.domain.errors import DomainError, FeedbackValidationError
from rfe.usecases.compose_feedback import BulletsPayload, ComposeFeedback


def make_rubric() -> Rubric:
    r = Rubric(id="r1", role_id="role1", criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
        Criterion(id="python", name="Python"),
    ])
    r.publish()
    return r


def make_candidate() -> Candidate:
    return Candidate(id="cand1", role_id="role1", name="A", email="a@x.com",
                     resume_text="...")


def make_evaluation() -> Evaluation:
    return Evaluation(id="e1", candidate_id="cand1", rubric_id="r1", scores=[
        CriterionScore(criterion_id="k8s", score=1, evidence="1y only"),
        CriterionScore(criterion_id="python", score=5),
    ])


LINKED = BulletsPayload(
    intro="Thank you for your application.",
    bullets=[FeedbackBullet(criterion_id="k8s",
                            text="The role required 5 years of Kubernetes; your resume showed 1.")],
)

UNLINKED = BulletsPayload(
    intro="Thanks.",
    bullets=[FeedbackBullet(criterion_id="made_up_reason", text="You seemed unenthusiastic.")],
)


def test_composes_drafted_feedback_from_unmet_criteria():
    uc = ComposeFeedback(MockModelProvider([LINKED]))
    fb = uc.execute(make_candidate(), make_rubric(), make_evaluation(), feedback_id="f1")
    assert fb.status == FeedbackStatus.DRAFTED
    assert fb.bullets[0].criterion_id == "k8s"


def test_unlinked_bullet_retries_then_raises():
    mock = MockModelProvider([UNLINKED, UNLINKED])
    with pytest.raises(FeedbackValidationError):
        ComposeFeedback(mock).execute(make_candidate(), make_rubric(),
                                      make_evaluation(), feedback_id="f1")
    assert len(mock.calls) == 2


def test_unlinked_then_valid_recovers_on_retry():
    mock = MockModelProvider([UNLINKED, LINKED])
    fb = ComposeFeedback(mock).execute(make_candidate(), make_rubric(),
                                       make_evaluation(), feedback_id="f1")
    assert fb.bullets[0].criterion_id == "k8s"


def test_no_unmet_criteria_raises():
    ev = Evaluation(id="e1", candidate_id="cand1", rubric_id="r1",
                    scores=[CriterionScore(criterion_id="k8s", score=5)])
    with pytest.raises(DomainError):
        ComposeFeedback(MockModelProvider([LINKED])).execute(
            make_candidate(), make_rubric(), ev, feedback_id="f1")


def test_model_output_error_then_valid_recovers_on_retry():
    from rfe.ports.model_provider import ModelOutputError
    mock = MockModelProvider([ModelOutputError("schema echo"), LINKED])
    fb = ComposeFeedback(mock).execute(make_candidate(), make_rubric(),
                                       make_evaluation(), feedback_id="f1")
    assert fb.bullets[0].criterion_id == "k8s"


def test_model_output_error_twice_raises_model_output_error():
    from rfe.ports.model_provider import ModelOutputError
    mock = MockModelProvider([ModelOutputError("bad"), ModelOutputError("bad")])
    with pytest.raises(ModelOutputError):
        ComposeFeedback(mock).execute(make_candidate(), make_rubric(),
                                      make_evaluation(), feedback_id="f1")
    assert len(mock.calls) == 2
