from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from rfe.domain.errors import DomainError, RubricImmutableError


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
