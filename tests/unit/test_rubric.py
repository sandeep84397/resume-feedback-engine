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


# --- New immutability tests ---

def test_post_publish_field_assignment_raises():
    """Direct field assignment on a published rubric must raise RubricImmutableError."""
    rubric = Rubric(id="r1", role_id="role1", criteria=[make_criterion()])
    rubric.publish()
    with pytest.raises(RubricImmutableError):
        rubric.salary_band_min = 999


def test_post_publish_criteria_append_impossible():
    """criteria after publish must be immutable — append should raise."""
    rubric = Rubric(id="r1", role_id="role1", criteria=[make_criterion()])
    rubric.publish()
    with pytest.raises((TypeError, AttributeError)):
        rubric.criteria.append(make_criterion("c2"))


def test_post_publish_criteria_assignment_raises():
    """Direct criteria reassignment on published rubric raises RubricImmutableError."""
    rubric = Rubric(id="r1", role_id="role1", criteria=[make_criterion()])
    rubric.publish()
    with pytest.raises(RubricImmutableError):
        rubric.criteria = []


# --- Salary band validator ---

def test_salary_band_min_greater_than_max_raises():
    """salary_band_min > salary_band_max must raise at construction."""
    with pytest.raises((ValueError, DomainError)):
        Rubric(id="r1", role_id="role1", salary_band_min=100000, salary_band_max=50000)


def test_salary_band_equal_is_ok():
    r = Rubric(id="r1", role_id="role1", salary_band_min=50000, salary_band_max=50000)
    assert r.salary_band_min == r.salary_band_max


def test_salary_band_none_is_ok():
    r = Rubric(id="r1", role_id="role1")
    assert r.salary_band_min is None
    assert r.salary_band_max is None


def test_experience_range_min_greater_than_max_raises():
    with pytest.raises((ValueError, DomainError)):
        Rubric(id="r1", role_id="role1",
               experience_min_years=6, experience_max_years=3)


def test_experience_range_equal_is_ok():
    r = Rubric(id="r1", role_id="role1",
               experience_min_years=5, experience_max_years=5)
    assert r.experience_min_years == r.experience_max_years


def test_allowed_seniority_levels_are_normalized():
    r = Rubric(id="r1", role_id="role1",
               allowed_seniority_levels=[" SDE 2 ", "sde-3", ""])
    assert r.allowed_seniority_levels == ["sde2", "sde3"]


# --- Reserved criterion id ---

def test_reserved_criterion_id_raises():
    """Reserved synthetic criteria are rejected at construction."""
    for cid in ("salary_band", "experience_range", "seniority_level"):
        with pytest.raises((ValueError, DomainError)):
            Criterion(id=cid, name=cid)
