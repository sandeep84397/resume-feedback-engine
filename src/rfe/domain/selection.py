from rfe.domain.entities import Evaluation, Rubric

SALARY_CRITERION_ID = "salary_band"
PASS_SCORE = 3


def select_unmet_criteria(rubric: Rubric, evaluation: Evaluation) -> list[str]:
    """Return ids of criteria the candidate did not meet.

    Only ids present in the rubric can appear — scores against unknown
    criteria (e.g. injected by a hostile resume) are discarded.
    """
    known = {c.id for c in rubric.criteria}
    unmet = [s.criterion_id for s in evaluation.scores
             if s.criterion_id in known and s.score < PASS_SCORE]
    if evaluation.salary_mismatch:
        unmet.append(SALARY_CRITERION_ID)
    return unmet
