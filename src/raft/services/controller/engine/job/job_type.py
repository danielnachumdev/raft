"""Kind of controller work (not the orchestrator key)."""

from enum import Enum


class JobType(Enum):
    """Kind of controller work (not the orchestrator key)."""

    HEAL = "heal"
    METRICS = "metrics"
    SERVICE_LOGS = "service-logs"
    ACME = "acme"
    ALERTS = "alerts"
    # SCALE intentionally absent — transitional side_ticks only.
