import pytest

from rfe.domain.entities import Candidate, Feedback, FeedbackBullet, FeedbackStatus
from rfe.domain.errors import InvalidTransitionError
from rfe.usecases.deliver_feedback import DeliverFeedback


class SpyDeliverer:
    def __init__(self):
        self.delivered = []

    def deliver(self, candidate, feedback):
        self.delivered.append((candidate.id, feedback.id))


def make_feedback(status=FeedbackStatus.APPROVED) -> Feedback:
    return Feedback(id="f1", evaluation_id="e1", candidate_id="cand1",
                    intro="Hi", status=status,
                    bullets=[FeedbackBullet(criterion_id="k8s", text="...")])


def make_candidate() -> Candidate:
    return Candidate(id="cand1", role_id="role1", name="A", email="a@x.com",
                     resume_text="...")


def test_delivers_approved_and_marks_sent():
    spy = SpyDeliverer()
    fb = make_feedback()
    DeliverFeedback(spy).execute(make_candidate(), fb)
    assert fb.status == FeedbackStatus.SENT
    assert spy.delivered == [("cand1", "f1")]


def test_refuses_unapproved():
    spy = SpyDeliverer()
    with pytest.raises(InvalidTransitionError):
        DeliverFeedback(spy).execute(make_candidate(),
                                     make_feedback(FeedbackStatus.DRAFTED))
    assert spy.delivered == []
