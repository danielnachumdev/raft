"""Persistent scale-to-zero state under ``~/.raft/state/scaling/``."""

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .app_scaling_state import AppScalingState
from .wake_progress import WakeProgress

SCALING_STATE_DIR = Path("state") / "scaling"
SCALING_MARKERS_DIR = SCALING_STATE_DIR / "markers"


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
            state.wake_id = None
            state.wake_progress = None
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
            state.wake_id = None
            state.wake_progress = None
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
            state.wake_id = None
            state.wake_progress = None
            state.last_activity_at = when
            state.min_up_until = when + float(min_up_seconds)
            self._save_unlocked(name, state)

    def request_wake(self, name: str, *, now: Optional[float] = None) -> Optional[str]:
        with self._lock:
            state = self._load_unlocked(name)
            if not state.scaled_to_zero:
                return None
            when = time.time() if now is None else now
            # Fresh deadline after timeout (or first request). Sticky only while
            # the same wake attempt is still in flight.
            if state.wake_requested_at is None or state.wake_timed_out:
                state.wake_requested_at = when
                state.wake_id = self._new_wake_id()
                state.wake_progress = None
            elif not state.wake_id:
                state.wake_id = self._new_wake_id()
                state.wake_progress = None
            state.wake_timed_out = False
            self._save_unlocked(name, state)
            return state.wake_id

    @staticmethod
    def _new_wake_id() -> str:
        return uuid.uuid4().hex

    def mark_wake_timeout(self, name: str) -> None:
        with self._lock:
            state = self._load_unlocked(name)
            state.wake_timed_out = True
            self._save_unlocked(name, state)

    def note_wake_progress(
        self,
        name: str,
        stage: str,
        *,
        service: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        with self._lock:
            state = self._load_unlocked(name)
            state.wake_progress = WakeProgress(
                stage=stage, service=service, detail=detail
            )
            self._save_unlocked(name, state)

    def wake_progress_log(self, name: str) -> str:
        progress = self.load(name).wake_progress
        return progress.log_tail() if progress is not None else "-"

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
        self._sync_id_marker(name, state)

    def _sync_id_marker(self, name: str, state: AppScalingState) -> None:
        ident = self.markers / f"{name}.id"
        if state.scaled_to_zero and state.wake_id:
            ident.write_text(state.wake_id, encoding="utf-8")
            return
        if ident.is_file():
            ident.unlink()

    @staticmethod
    def _set_marker(path: Path, present: bool) -> None:
        if present:
            path.write_text("", encoding="utf-8")
            return
        if path.is_file():
            path.unlink()
