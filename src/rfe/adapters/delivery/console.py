import logging

from rfe.domain.entities import Candidate, Feedback

logger = logging.getLogger("rfe.delivery")


class ConsoleDeliverer:
    """Phase 1 deliverer: logs the outgoing message. SMTP adapter lands in Phase 2.

    Logs candidate id only — never email/name/feedback body (no PII in logs).
    """

    def deliver(self, candidate: Candidate, feedback: Feedback) -> None:
        logger.info("feedback %s delivered to candidate %s",
                    feedback.id, candidate.id)
