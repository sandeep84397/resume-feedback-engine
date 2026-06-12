from typing import Protocol

from rfe.domain.entities import Candidate, Feedback


class FeedbackDeliverer(Protocol):
    def deliver(self, candidate: Candidate, feedback: Feedback) -> None:
        """Send approved feedback to the candidate. Raises on failure."""
        ...
