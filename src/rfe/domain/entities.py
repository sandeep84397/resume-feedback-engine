from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from rfe.domain.errors import DomainError, InvalidTransitionError, RubricImmutableError


class CriterionType(str, Enum):
    MUST_HAVE = "must_have"
    WEIGHTED = "weighted"


class Criterion(BaseModel):
    id: str
    name: str
    description: str = ""
    type: CriterionType = CriterionType.WEIGHTED
    weight: float = 1.0


class Rubric(BaseModel):
    id: str
    role_id: str
    version: int = 1
    criteria: list[Criterion] = Field(default_factory=list)
    salary_band_min: float | None = None
    salary_band_max: float | None = None
    published: bool = False

    def publish(self) -> None:
        if not self.criteria:
            raise DomainError("cannot publish a rubric with no criteria")
        self.published = True

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
