"""Conflict when creating an alert rule whose id already exists."""

from raft.core.core.errors.cta import OperatorError


class RuleConflict(OperatorError):
    """Raised when creating a rule whose id already exists."""
