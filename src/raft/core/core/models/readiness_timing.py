"""Compose-aligned readiness wait budget helpers."""

# Compose healthcheck defaults (cold start / migrations need a long start_period).
DEFAULT_START_PERIOD_SECONDS = 45.0
DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_PROBE_TIMEOUT_SECONDS = 2.0
DEFAULT_RETRIES = 15
# Extra seconds after start_period + probe budget so raft does not race Compose.
_TIMEOUT_BUFFER_SECONDS = 15.0
# Floor for the raft wait budget when the formula would be lower.
DEFAULT_TIMEOUT_SECONDS = 120.0


class ReadinessTiming:
    """Derive and format readiness timeout budgets."""

    @staticmethod
    def recommended_timeout_seconds(
        *,
        start_period_seconds: float = DEFAULT_START_PERIOD_SECONDS,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        retries: int = DEFAULT_RETRIES,
    ) -> float:
        """Minimum wait that covers Compose start_period plus probe retries."""
        return (
            float(start_period_seconds)
            + float(retries) * float(interval_seconds)
            + _TIMEOUT_BUFFER_SECONDS
        )

    @staticmethod
    def default_timeout_seconds(
        *,
        start_period_seconds: float = DEFAULT_START_PERIOD_SECONDS,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        retries: int = DEFAULT_RETRIES,
    ) -> float:
        """Default raft wait: at least 120s, and never below the Compose probe budget."""
        return max(
            DEFAULT_TIMEOUT_SECONDS,
            ReadinessTiming.recommended_timeout_seconds(
                start_period_seconds=start_period_seconds,
                interval_seconds=interval_seconds,
                retries=retries,
            ),
        )

    @staticmethod
    def format_duration_seconds(seconds: float) -> str:
        """Compose-friendly duration (``45s``, ``2.5s``)."""
        value = float(seconds)
        if value == int(value):
            return f"{int(value)}s"
        return f"{value:g}s"
