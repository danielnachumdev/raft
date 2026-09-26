"""Persistent scale-to-zero state under ``~/.raft/state/scaling/``."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SCALING_STATE_DIR = Path("state") / "scaling"
SCALING_MARKERS_DIR = SCALING_STATE_DIR / "markers"


@dataclass
class AppScalingState:
    """Runtime scaling flags for one app (JSON + nginx marker files)."""

    scaled_to_zero: bool = False
    last_activity_at: Optional[float] = None
    min_up_until: Optional[float] = None
    wake_requested_at: Optional[float] = None
    wake_timed_out: bool = False

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AppScalingState":
        return cls(
            scaled_to_zero=bool(data.get("scaledToZero", False)),
            last_activity_at=cls._opt_float(data.get("lastActivityAt")),
            min_up_until=cls._opt_float(data.get("minUpUntil")),
            wake_requested_at=cls._opt_float(data.get("wakeRequestedAt")),
            wake_timed_out=bool(data.get("wakeTimedOut", False)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "scaledToZero": self.scaled_to_zero,
            "lastActivityAt": self.last_activity_at,
            "minUpUntil": self.min_up_until,
            "wakeRequestedAt": self.wake_requested_at,
            "wakeTimedOut": self.wake_timed_out,
        }

    @staticmethod
    def _opt_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)


class ScalingStore:
    """Read/write per-app scaling JSON and gate marker files."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.root = home / SCALING_STATE_DIR
        self.markers = home / SCALING_MARKERS_DIR

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.markers.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def load(self, name: str) -> AppScalingState:
        path = self.path_for(name)
        if not path.is_file():
            return AppScalingState()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppScalingState()
        if not isinstance(data, dict):
            return AppScalingState()
        return AppScalingState.from_mapping(data)

    def save(self, name: str, state: AppScalingState) -> None:
        self.ensure_dirs()
        path = self.path_for(name)
        path.write_text(
            json.dumps(state.to_mapping(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._sync_markers(name, state)

    def is_scaled_to_zero(self, name: str) -> bool:
        return self.load(name).scaled_to_zero

    def touch_activity(self, name: str, *, now: Optional[float] = None) -> None:
        state = self.load(name)
        if state.scaled_to_zero:
            return
        state.last_activity_at = time.time() if now is None else now
        self.save(name, state)

    def mark_scaled_to_zero(self, name: str) -> None:
        state = self.load(name)
        state.scaled_to_zero = True
        state.wake_requested_at = None
        state.wake_timed_out = False
        self.save(name, state)

    def mark_awake(
        self,
        name: str,
        *,
        min_up_seconds: float,
        now: Optional[float] = None,
    ) -> None:
        when = time.time() if now is None else now
        state = self.load(name)
        state.scaled_to_zero = False
        state.wake_requested_at = None
        state.wake_timed_out = False
        state.last_activity_at = when
        state.min_up_until = when + float(min_up_seconds)
        self.save(name, state)

    def request_wake(self, name: str, *, now: Optional[float] = None) -> None:
        state = self.load(name)
        if not state.scaled_to_zero:
            return
        if state.wake_requested_at is None:
            state.wake_requested_at = time.time() if now is None else now
        state.wake_timed_out = False
        self.save(name, state)

    def mark_wake_timeout(self, name: str) -> None:
        state = self.load(name)
        state.wake_timed_out = True
        self.save(name, state)

    def _sync_markers(self, name: str, state: AppScalingState) -> None:
        self.ensure_dirs()
        zero = self.markers / f"{name}.zero"
        timeout = self.markers / f"{name}.timeout"
        self._set_marker(zero, state.scaled_to_zero)
        self._set_marker(timeout, state.scaled_to_zero and state.wake_timed_out)

    @staticmethod
    def _set_marker(path: Path, present: bool) -> None:
        if present:
            path.write_text("", encoding="utf-8")
            return
        if path.is_file():
            path.unlink()
