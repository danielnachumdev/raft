"""Raised when a download requests an unregistered format id."""


class UnknownExportFormat(ValueError):
    """Raised when a download requests a format the registry does not have."""

    def __init__(self, format_id: str, known: list[str]) -> None:
        listed = ", ".join(known) if known else "(none)"
        super().__init__(
            f"unknown export format '{format_id}' (known: {listed})"
        )
        self.format_id = format_id
        self.known = known
