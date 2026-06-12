from rfe.domain.entities import Candidate, Feedback
from rfe.ports.deliverer import FeedbackDeliverer


class DeliverFeedback:
    """Delivery only happens through the approval state machine."""

    def __init__(self, deliverer: FeedbackDeliverer):
        self._deliverer = deliverer

    def execute(self, candidate: Candidate, feedback: Feedback) -> None:
        feedback.mark_sent()  # raises InvalidTransitionError unless APPROVED
        self._deliverer.deliver(candidate, feedback)
