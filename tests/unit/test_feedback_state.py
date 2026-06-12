import pytest

from rfe.domain.entities import Feedback, FeedbackBullet, FeedbackStatus
from rfe.domain.errors import InvalidTransitionError


def make_feedback() -> Feedback:
    return Feedback(
        id="f1", evaluation_id="e1", candidate_id="cand1",
        intro="Thank you for applying.",
        bullets=[FeedbackBullet(criterion_id="c1", text="Role required 5y K8s; resume showed 1y.")],
    )


def test_new_feedback_is_drafted():
    assert make_feedback().status == FeedbackStatus.DRAFTED


def test_drafted_to_approved_to_sent():
    fb = make_feedback()
    fb.approve()
    assert fb.status == FeedbackStatus.APPROVED
    fb.mark_sent()
    assert fb.status == FeedbackStatus.SENT


def test_cannot_send_unapproved():
    fb = make_feedback()
    with pytest.raises(InvalidTransitionError):
        fb.mark_sent()


def test_cannot_approve_twice():
    fb = make_feedback()
    fb.approve()
    with pytest.raises(InvalidTransitionError):
        fb.approve()
