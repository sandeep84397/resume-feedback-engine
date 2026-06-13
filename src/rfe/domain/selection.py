from rfe.domain.entities import (Evaluation, EXPERIENCE_CRITERION_ID, Rubric,
                                 SALARY_CRITERION_ID, SENIORITY_CRITERION_ID)

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
    if evaluation.experience_mismatch:
        unmet.append(EXPERIENCE_CRITERION_ID)
    if evaluation.seniority_mismatch:
        unmet.append(SENIORITY_CRITERION_ID)
    return unmet
