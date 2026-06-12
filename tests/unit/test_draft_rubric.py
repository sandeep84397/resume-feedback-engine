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
