class DomainError(Exception):
    """Base error for domain rule violations."""


class RubricImmutableError(DomainError):
    """Published rubrics cannot be modified; create a new version."""


class InvalidTransitionError(DomainError):
    """Illegal feedback state transition."""


class FeedbackValidationError(DomainError):
    """Feedback bullet not linked to an unmet rubric criterion."""
