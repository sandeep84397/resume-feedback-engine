import pytest

from rfe.domain.entities import Criterion, CriterionType, Rubric
from rfe.domain.errors import DomainError, RubricImmutableError


def make_criterion(cid: str = "c1") -> Criterion:
    return Criterion(id=cid, name="Kubernetes", description="5y K8s",
                     type=CriterionType.MUST_HAVE, weight=2.0)


def test_publish_requires_criteria():
    rubric = Rubric(id="r1", role_id="role1")
    with pytest.raises(DomainError):
        rubric.publish()


def test_published_rubric_rejects_criteria_changes():
    rubric = Rubric(id="r1", role_id="role1", criteria=[make_criterion()])
    rubric.publish()
    assert rubric.published is True
    with pytest.raises(RubricImmutableError):
        rubric.replace_criteria([make_criterion("c2")])


def test_unpublished_rubric_allows_criteria_changes():
    rubric = Rubric(id="r1", role_id="role1", criteria=[make_criterion()])
    rubric.replace_criteria([make_criterion("c2")])
    assert rubric.criteria[0].id == "c2"
