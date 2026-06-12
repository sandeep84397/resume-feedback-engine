from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rfe.domain.errors import DomainError, InvalidTransitionError, RubricImmutableError

SALARY_CRITERION_ID = "salary_band"


class CriterionType(str, Enum):
    MUST_HAVE = "must_have"
    WEIGHTED = "weighted"


class Criterion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    type: CriterionType = CriterionType.WEIGHTED
    weight: float = 1.0

    @field_validator("id")
    @classmethod
    def _reject_reserved_id(cls, v: str) -> str:
        if v == SALARY_CRITERION_ID:
            raise ValueError(
                f"criterion id '{SALARY_CRITERION_ID}' is reserved; use a different id"
            )
        return v


class Rubric(BaseModel):
    id: str
    role_id: str
    version: int = 1
    criteria: list[Criterion] | tuple[Criterion, ...] = Field(default_factory=list)
    salary_band_min: float | None = None
    salary_band_max: float | None = None
    published: bool = False

    @model_validator(mode="after")
    def _validate_salary_band(self) -> "Rubric":
        if (
            self.salary_band_min is not None
            and self.salary_band_max is not None
            and self.salary_band_min > self.salary_band_max
        ):
            raise ValueError(
                f"salary_band_min ({self.salary_band_min}) must be <= "
                f"salary_band_max ({self.salary_band_max})"
            )
        return self

    def __setattr__(self, name: str, value: Any) -> None:
        # Allow the publish() flip: setting published from False → True
        if name == "published" and not self.__dict__.get("published", False):
            super().__setattr__(name, value)
            return
        if self.__dict__.get("published", False):
            raise RubricImmutableError(
                "published rubric is immutable; create a new version"
            )
        super().__setattr__(name, value)

    def publish(self) -> None:
        if not self.criteria:
            raise DomainError("cannot publish a rubric with no criteria")
        # Use object.__setattr__ to bypass our guard for the publish flip itself
        object.__setattr__(self, "published", True)
        # Freeze criteria as tuple so in-place append is impossible
        object.__setattr__(self, "criteria", tuple(self.criteria))

    def replace_criteria(self, criteria: list[Criterion]) -> None:
        if self.published:
            raise RubricImmutableError(
                "published rubric is immutable; create a new version"
            )
        self.criteria = criteria


class Role(BaseModel):
    id: str
    title: str
    description: str = ""


class Candidate(BaseModel):
    id: str
    role_id: str
    name: str
    email: str
    resume_text: str
    salary_expectation: float | None = None

    @field_validator("resume_text")
    @classmethod
    def _reject_blank_resume(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("resume_text must not be empty or whitespace")
        return stripped


class CriterionScore(BaseModel):
    criterion_id: str
    score: int = Field(ge=0, le=5)
    evidence: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EvaluationStatus(str, Enum):
    COMPLETE = "complete"
    NEEDS_HUMAN = "needs_human"


class Evaluation(BaseModel):
    id: str
    candidate_id: str
    rubric_id: str
    scores: list[CriterionScore] = Field(default_factory=list)
    status: EvaluationStatus = EvaluationStatus.COMPLETE
    salary_mismatch: bool = False


class FeedbackStatus(str, Enum):
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"


class FeedbackBullet(BaseModel):
    criterion_id: str
    text: str


class Feedback(BaseModel):
    id: str
    evaluation_id: str
    candidate_id: str
    intro: str
    bullets: list[FeedbackBullet]
    status: FeedbackStatus = FeedbackStatus.DRAFTED

    def approve(self) -> None:
        if self.status != FeedbackStatus.DRAFTED:
            raise InvalidTransitionError(f"cannot approve feedback in state {self.status}")
        self.status = FeedbackStatus.APPROVED

    def mark_sent(self) -> None:
        if self.status != FeedbackStatus.APPROVED:
            raise InvalidTransitionError(f"cannot send feedback in state {self.status}")
        self.status = FeedbackStatus.SENT
