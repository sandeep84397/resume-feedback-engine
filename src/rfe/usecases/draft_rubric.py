from pydantic import BaseModel, Field

from rfe.domain.entities import Criterion, Role, Rubric
from rfe.ports.model_provider import ModelProvider


class CriteriaPayload(BaseModel):
    criteria: list[Criterion] = Field(default_factory=list)
    salary_band_min: float | None = None
    salary_band_max: float | None = None
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    allowed_seniority_levels: list[str] = Field(default_factory=list)


DRAFT_SYSTEM_PROMPT = (
    "You draft a hiring rubric from a job description. Produce 4-8 criteria "
    "with short ids (snake_case), names, one-line descriptions, and mark "
    "genuine hard requirements as must_have. Criteria must be job-related "
    "and objectively assessable from a resume or interview. If the job "
    "description states compensation, extract salary_band_min and/or "
    "salary_band_max as plain numbers. If the job description states years "
    "of experience or levels, extract experience_min_years, "
    "experience_max_years, and allowed_seniority_levels."
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
        return Rubric(id=rubric_id, role_id=role.id, criteria=payload.criteria,
                      salary_band_min=payload.salary_band_min,
                      salary_band_max=payload.salary_band_max,
                      experience_min_years=payload.experience_min_years,
                      experience_max_years=payload.experience_max_years,
                      allowed_seniority_levels=payload.allowed_seniority_levels)
