import pytest

from rfe.adapters.llm.mock import MockModelProvider
from rfe.domain.entities import (Candidate, Criterion, CriterionScore,
                                 CriterionType, EvaluationStatus, Rubric)
from rfe.domain.errors import DomainError
from rfe.ports.model_provider import ModelOutputError
from rfe.usecases.evaluate_candidate import EvaluateCandidate, ScoresPayload


def make_rubric(published=True, **kwargs) -> Rubric:
    r = Rubric(id="r1", role_id="role1", salary_band_max=70000.0, criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
    ], **kwargs)
    if published:
        r.publish()
    return r


def make_candidate(salary=None, **kwargs) -> Candidate:
    return Candidate(id="cand1", role_id="role1", name="A", email="a@x.com",
                     resume_text="2 years kubernetes at CompanyX",
                     salary_expectation=salary, **kwargs)


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
    assert ev.salary_checked is True
    assert ev.salary_mismatch is True


def test_missing_salary_band_marks_salary_not_checked():
    rubric = Rubric(id="r1", role_id="role1", criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
    ])
    rubric.publish()

    ev = EvaluateCandidate(MockModelProvider([GOOD])).execute(
        make_candidate(salary=85000.0), rubric, evaluation_id="e1")

    assert ev.salary_checked is False
    assert ev.salary_mismatch is False


@pytest.mark.parametrize(
    ("years", "checked", "mismatch"),
    [
        (2, True, True),    # below 3 years
        (3, True, False),   # lower boundary
        (5, True, False),   # inside range
        (6, True, False),   # upper boundary
        (11, True, True),   # overqualified for 3-6 year role
        (None, False, False),
    ],
)
def test_experience_range_scenarios(years, checked, mismatch):
    rubric = make_rubric(experience_min_years=3, experience_max_years=6)

    ev = EvaluateCandidate(MockModelProvider([GOOD])).execute(
        make_candidate(years_experience=years), rubric, evaluation_id="e1")

    assert ev.experience_checked is checked
    assert ev.experience_mismatch is mismatch


@pytest.mark.parametrize(
    ("level", "checked", "mismatch"),
    [
        ("SDE 2", True, False),
        ("sde-3", True, False),
        ("SDE 4", True, True),
        ("Staff Engineer", True, True),
        (None, False, False),
        ("", False, False),
    ],
)
def test_seniority_level_scenarios(level, checked, mismatch):
    rubric = make_rubric(allowed_seniority_levels=["SDE 2", "SDE 3"])

    ev = EvaluateCandidate(MockModelProvider([GOOD])).execute(
        make_candidate(current_level=level), rubric, evaluation_id="e1")

    assert ev.seniority_checked is checked
    assert ev.seniority_mismatch is mismatch


def test_overqualified_sde4_with_11_years_sets_both_mismatches():
    rubric = make_rubric(experience_min_years=3, experience_max_years=6,
                         allowed_seniority_levels=["SDE 2", "SDE 3"])

    ev = EvaluateCandidate(MockModelProvider([GOOD])).execute(
        make_candidate(years_experience=11, current_level="SDE 4"),
        rubric, evaluation_id="e1")

    assert ev.experience_mismatch is True
    assert ev.seniority_mismatch is True


def test_missing_rubric_experience_and_level_constraints_are_not_checked():
    ev = EvaluateCandidate(MockModelProvider([GOOD])).execute(
        make_candidate(years_experience=11, current_level="SDE 4"),
        make_rubric(), evaluation_id="e1")

    assert ev.experience_checked is False
    assert ev.experience_mismatch is False
    assert ev.seniority_checked is False
    assert ev.seniority_mismatch is False


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
