"""Per-app scale-to-zero contract (``spec.scaling``)."""

from dataclasses import dataclass
from typing import Optional

DEFAULT_WAKE_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class ScalingSpec:
    """Idle stop + wake. ``idleSeconds`` / ``minUpSeconds`` required; wake timeout defaults to 60."""

    idle_seconds: float
    wake_timeout_seconds: float
    min_up_seconds: float
    holding_page: Optional[str] = None
