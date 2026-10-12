"""Errors for invalid ``dependsOn`` graphs."""


class DependsOnError(ValueError):
    """Cycle or missing name in a ``dependsOn`` graph."""
