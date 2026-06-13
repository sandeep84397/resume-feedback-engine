from rfe.domain.entities import (Criterion, CriterionScore, CriterionType,
                                 Evaluation, Rubric)
from rfe.domain.selection import SALARY_CRITERION_ID, select_unmet_criteria


def make_rubric() -> Rubric:
    return Rubric(id="r1", role_id="role1", criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
        Criterion(id="python", name="Python", type=CriterionType.WEIGHTED),
        Criterion(id="comms", name="Communication", type=CriterionType.WEIGHTED),
    ])


def make_evaluation(scores, salary_mismatch=False, experience_mismatch=False,
                    seniority_mismatch=False) -> Evaluation:
    return Evaluation(id="e1", candidate_id="cand1", rubric_id="r1",
                      scores=scores, salary_mismatch=salary_mismatch,
                      experience_mismatch=experience_mismatch,
                      seniority_mismatch=seniority_mismatch)


def test_low_scores_are_unmet():
    ev = make_evaluation([
        CriterionScore(criterion_id="k8s", score=1),
        CriterionScore(criterion_id="python", score=2),
        CriterionScore(criterion_id="comms", score=5),
    ])
    assert select_unmet_criteria(make_rubric(), ev) == ["k8s", "python"]


def test_salary_mismatch_adds_salary_criterion():
    ev = make_evaluation([CriterionScore(criterion_id="k8s", score=5)],
                         salary_mismatch=True)
    assert select_unmet_criteria(make_rubric(), ev) == [SALARY_CRITERION_ID]


def test_experience_and_seniority_mismatches_add_reserved_criteria():
    ev = make_evaluation([CriterionScore(criterion_id="k8s", score=5)],
                         experience_mismatch=True, seniority_mismatch=True)
    assert select_unmet_criteria(make_rubric(), ev) == [
        "experience_range", "seniority_level",
    ]


def test_unknown_criterion_ids_ignored():
    ev = make_evaluation([CriterionScore(criterion_id="injected", score=0)])
    assert select_unmet_criteria(make_rubric(), ev) == []
