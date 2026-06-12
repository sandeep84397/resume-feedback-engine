from pydantic import BaseModel, Field

from rfe.domain.entities import (Candidate, Evaluation, Feedback,
                                 FeedbackBullet, Rubric)
from rfe.domain.errors import DomainError, FeedbackValidationError
from rfe.domain.selection import SALARY_CRITERION_ID, select_unmet_criteria
from rfe.ports.model_provider import ModelProvider


class BulletsPayload(BaseModel):
    intro: str
    bullets: list[FeedbackBullet] = Field(default_factory=list)


COMPOSE_SYSTEM_PROMPT = (
    "You write humane, factual rejection feedback for a job candidate. "
    "Write one bullet per provided unmet criterion, keeping its criterion_id. "
    "State what the role required and what the application showed; optionally "
    "add one growth suggestion. You MUST NOT introduce any reason that is not "
    "in the provided list. Never invite a reply; this is a one-way message."
)


class ComposeFeedback:
    """AI writes; the validator guarantees every bullet maps to an unmet criterion."""

    def __init__(self, model: ModelProvider):
        self._model = model

    def execute(self, candidate: Candidate, rubric: Rubric,
                evaluation: Evaluation, feedback_id: str) -> Feedback:
        unmet = select_unmet_criteria(rubric, evaluation)
        if not unmet:
            raise DomainError("no unmet criteria; nothing to compose feedback from")

        by_id = {c.id: c for c in rubric.criteria}
        evidence = {s.criterion_id: s.evidence for s in evaluation.scores}
        lines = []
        for cid in unmet:
            if cid == SALARY_CRITERION_ID:
                lines.append(f"- id={cid}: salary expectation above the budgeted band")
            else:
                c = by_id[cid]
                lines.append(f"- id={cid} name={c.name} required={c.description} "
                             f"evidence_found={evidence.get(cid, '')}")
        user_content = "UNMET CRITERIA:\n" + "\n".join(lines)

        last_error: FeedbackValidationError | None = None
        for _ in range(2):  # one retry on validation failure
            payload = self._model.complete(
                COMPOSE_SYSTEM_PROMPT, user_content, BulletsPayload)
            allowed = set(unmet)
            bad = [b.criterion_id for b in payload.bullets
                   if b.criterion_id not in allowed]
            if bad:
                last_error = FeedbackValidationError(
                    f"bullets reference non-unmet criteria: {bad}")
                continue
            return Feedback(id=feedback_id, evaluation_id=evaluation.id,
                            candidate_id=candidate.id, intro=payload.intro,
                            bullets=payload.bullets)
        raise last_error
