"""Persistent scale-to-zero state under ``~/.raft/state/scaling/``."""

from __future__ import annotations

import json
import os
import tempfile
import threading
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
        self._lock = threading.Lock()

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.markers.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def load(self, name: str) -> AppScalingState:
        with self._lock:
            return self._load_unlocked(name)

    def save(self, name: str, state: AppScalingState) -> None:
        with self._lock:
            self._save_unlocked(name, state)

    def is_scaled_to_zero(self, name: str) -> bool:
        return self.load(name).scaled_to_zero

    def touch_activity(self, name: str, *, now: Optional[float] = None) -> None:
        with self._lock:
            state = self._load_unlocked(name)
            if state.scaled_to_zero:
                return
            state.last_activity_at = time.time() if now is None else now
            self._save_unlocked(name, state)

    def mark_scaled_to_zero(self, name: str) -> None:
        with self._lock:
            state = self._load_unlocked(name)
            state.scaled_to_zero = True
            state.wake_requested_at = None
            state.wake_timed_out = False
            self._save_unlocked(name, state)

    def clear_scaled_to_zero(self, name: str) -> None:
        """Drop intentional zero marker (co-stopped deps on wake) without min-up."""
        with self._lock:
            state = self._load_unlocked(name)
            if not state.scaled_to_zero:
                return
            state.scaled_to_zero = False
            state.wake_requested_at = None
            state.wake_timed_out = False
            self._save_unlocked(name, state)

    def mark_awake(
        self,
        name: str,
        *,
        min_up_seconds: float,
        now: Optional[float] = None,
    ) -> None:
        when = time.time() if now is None else now
        with self._lock:
            state = self._load_unlocked(name)
            state.scaled_to_zero = False
            state.wake_requested_at = None
            state.wake_timed_out = False
            state.last_activity_at = when
            state.min_up_until = when + float(min_up_seconds)
            self._save_unlocked(name, state)

    def request_wake(self, name: str, *, now: Optional[float] = None) -> None:
        with self._lock:
            state = self._load_unlocked(name)
            if not state.scaled_to_zero:
                return
            when = time.time() if now is None else now
            # Fresh deadline after timeout (or first request). Sticky only while
            # the same wake attempt is still in flight.
            if state.wake_requested_at is None or state.wake_timed_out:
                state.wake_requested_at = when
            state.wake_timed_out = False
            self._save_unlocked(name, state)

    def mark_wake_timeout(self, name: str) -> None:
        with self._lock:
            state = self._load_unlocked(name)
            state.wake_timed_out = True
            self._save_unlocked(name, state)

    def _load_unlocked(self, name: str) -> AppScalingState:
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

    def _save_unlocked(self, name: str, state: AppScalingState) -> None:
        self.ensure_dirs()
        self._atomic_write_json(self.path_for(name), state.to_mapping())
        self._sync_markers(name, state)

    @staticmethod
    def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
        """Unique temp + replace so readers never see torn JSON (or shared .tmp)."""
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _sync_markers(self, name: str, state: AppScalingState) -> None:
        """Exclusive markers: ``.zero`` (holding) or ``.timeout``, never both."""
        self.ensure_dirs()
        zero = self.markers / f"{name}.zero"
        timeout = self.markers / f"{name}.timeout"
        timed_out = state.scaled_to_zero and state.wake_timed_out
        self._set_marker(zero, state.scaled_to_zero and not state.wake_timed_out)
        self._set_marker(timeout, timed_out)

    @staticmethod
    def _set_marker(path: Path, present: bool) -> None:
        if present:
            path.write_text("", encoding="utf-8")
            return
        if path.is_file():
            path.unlink()
