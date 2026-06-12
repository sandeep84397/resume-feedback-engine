from pydantic import BaseModel, Field

from rfe.domain.entities import Criterion, Role, Rubric
from rfe.ports.model_provider import ModelProvider


class CriteriaPayload(BaseModel):
    criteria: list[Criterion] = Field(default_factory=list)


DRAFT_SYSTEM_PROMPT = (
    "You draft a hiring rubric from a job description. Produce 4-8 criteria "
    "with short ids (snake_case), names, one-line descriptions, and mark "
    "genuine hard requirements as must_have. Criteria must be job-related "
    "and objectively assessable from a resume or interview."
)


class DraftRubric:
    """AI proposes a rubric; it stays unpublished until a human edits and publishes."""

    def __init__(self, model: ModelProvider):
        self._model = model

    def execute(self, role: Role, rubric_id: str) -> Rubric:
        payload = self._model.complete(
            DRAFT_SYSTEM_PROMPT,
            f"JOB TITLE: {role.title}\nJOB DESCRIPTION:\n{role.description}",
            CriteriaPayload,
        )
        return Rubric(id=rubric_id, role_id=role.id, criteria=payload.criteria)
