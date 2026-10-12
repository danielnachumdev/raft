"""Runtime scaling flags for one app (JSON + nginx marker files)."""

from dataclasses import dataclass
from typing import Any, Optional

from .wake_progress import WakeProgress


@dataclass
class AppScalingState:
    """Runtime scaling flags for one app (JSON + nginx marker files)."""

    scaled_to_zero: bool = False
    last_activity_at: Optional[float] = None
    min_up_until: Optional[float] = None
    wake_requested_at: Optional[float] = None
    wake_timed_out: bool = False
    wake_id: Optional[str] = None
    wake_progress: Optional[WakeProgress] = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AppScalingState":
        return cls(
            scaled_to_zero=bool(data.get("scaledToZero", False)),
            last_activity_at=cls._opt_float(data.get("lastActivityAt")),
            min_up_until=cls._opt_float(data.get("minUpUntil")),
            wake_requested_at=cls._opt_float(data.get("wakeRequestedAt")),
            wake_timed_out=bool(data.get("wakeTimedOut", False)),
            wake_id=cls._opt_id(data.get("wakeId")),
            wake_progress=WakeProgress.from_mapping(data.get("lastWakeProgress")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "scaledToZero": self.scaled_to_zero,
            "lastActivityAt": self.last_activity_at,
            "minUpUntil": self.min_up_until,
            "wakeRequestedAt": self.wake_requested_at,
            "wakeTimedOut": self.wake_timed_out,
            "wakeId": self.wake_id,
            "lastWakeProgress": (
                None if self.wake_progress is None else self.wake_progress.to_mapping()
            ),
        }

    @staticmethod
    def _opt_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _opt_id(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
