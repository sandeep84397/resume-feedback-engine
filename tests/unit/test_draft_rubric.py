from rfe.adapters.llm.mock import MockModelProvider
from rfe.domain.entities import Criterion, CriterionType, Role
from rfe.usecases.draft_rubric import CriteriaPayload, DraftRubric


def test_drafts_unpublished_rubric_from_role_description():
    payload = CriteriaPayload(criteria=[
        Criterion(id="k8s", name="Kubernetes", description="5y required",
                  type=CriterionType.MUST_HAVE),
    ])
    role = Role(id="role1", title="SRE", description="We need 5y Kubernetes...")
    rubric = DraftRubric(MockModelProvider([payload])).execute(role, rubric_id="r1")
    assert rubric.published is False
    assert rubric.role_id == "role1"
    assert rubric.criteria[0].id == "k8s"


def test_draft_can_include_salary_band_from_role_description():
    payload = CriteriaPayload(
        criteria=[Criterion(id="k8s", name="Kubernetes")],
        salary_band_min=100000,
        salary_band_max=130000,
    )
    role = Role(id="role1", title="SRE", description="Salary 100000-130000")

    rubric = DraftRubric(MockModelProvider([payload])).execute(role, rubric_id="r1")

    assert rubric.salary_band_min == 100000
    assert rubric.salary_band_max == 130000


def test_draft_can_include_experience_and_seniority_constraints():
    payload = CriteriaPayload(
        criteria=[Criterion(id="android", name="Android")],
        experience_min_years=3,
        experience_max_years=6,
        allowed_seniority_levels=["SDE 2", "SDE 3"],
    )
    role = Role(id="role1", title="Android SDE",
                description="SDE 2 or SDE 3 with 3-6 years experience")

    rubric = DraftRubric(MockModelProvider([payload])).execute(role, rubric_id="r1")

    assert rubric.experience_min_years == 3
    assert rubric.experience_max_years == 6
    assert rubric.allowed_seniority_levels == ["sde2", "sde3"]
