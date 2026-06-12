import pytest

from rfe.adapters.llm.mock import MockModelProvider
from rfe.domain.entities import (Candidate, Criterion, CriterionScore,
                                 CriterionType, EvaluationStatus, Rubric)
from rfe.domain.errors import DomainError
from rfe.ports.model_provider import ModelOutputError
from rfe.usecases.evaluate_candidate import EvaluateCandidate, ScoresPayload


def make_rubric(published=True) -> Rubric:
    r = Rubric(id="r1", role_id="role1", salary_band_max=70000.0, criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
    ])
    if published:
        r.publish()
    return r


def make_candidate(salary=None) -> Candidate:
    return Candidate(id="cand1", role_id="role1", name="A", email="a@x.com",
                     resume_text="2 years kubernetes at CompanyX",
                     salary_expectation=salary)


GOOD = ScoresPayload(scores=[CriterionScore(criterion_id="k8s", score=2,
                                            evidence="2 years at CompanyX")])


def test_happy_path_scores_and_completes():
    uc = EvaluateCandidate(MockModelProvider([GOOD]))
    ev = uc.execute(make_candidate(), make_rubric(), evaluation_id="e1")
    assert ev.status == EvaluationStatus.COMPLETE
    assert ev.scores[0].criterion_id == "k8s"


def test_unpublished_rubric_rejected():
    uc = EvaluateCandidate(MockModelProvider([GOOD]))
    with pytest.raises(DomainError):
        uc.execute(make_candidate(), make_rubric(published=False), evaluation_id="e1")


def test_salary_above_band_sets_mismatch():
    uc = EvaluateCandidate(MockModelProvider([GOOD]))
    ev = uc.execute(make_candidate(salary=85000.0), make_rubric(), evaluation_id="e1")
    assert ev.salary_mismatch is True


def test_retries_once_then_needs_human():
    mock = MockModelProvider([ModelOutputError("bad"), ModelOutputError("bad again")])
    ev = EvaluateCandidate(mock).execute(make_candidate(), make_rubric(), evaluation_id="e1")
    assert ev.status == EvaluationStatus.NEEDS_HUMAN
    assert ev.scores == []
    assert len(mock.calls) == 2


def test_scores_for_unknown_criteria_are_dropped():
    payload = ScoresPayload(scores=[
        CriterionScore(criterion_id="k8s", score=2),
        CriterionScore(criterion_id="injected_by_resume", score=5),
    ])
    ev = EvaluateCandidate(MockModelProvider([payload])).execute(
        make_candidate(), make_rubric(), evaluation_id="e1")
    assert [s.criterion_id for s in ev.scores] == ["k8s"]


def test_resume_is_delimited_as_untrusted_data():
    mock = MockModelProvider([GOOD])
    EvaluateCandidate(mock).execute(make_candidate(), make_rubric(), evaluation_id="e1")
    _, user_content, _ = mock.calls[0]
    assert "<resume>" in user_content and "</resume>" in user_content
