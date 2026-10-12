"""Operator-facing failure that already includes a Fix CTA."""


class OperatorError(RuntimeError):
    """Operator-facing failure that already includes a Fix CTA."""

    def __init__(self, message: str, *, has_fix: bool = True) -> None:
        super().__init__(message)
        self.has_fix = has_fix
