"""Atomic read/write for per-app ACME JSON state."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Optional

from ..paths import AcmePaths
from .state import AcmeAppState


class AcmeAppStore:
    """Atomic read/write for per-app ACME JSON state."""

    def __init__(self, data_home: Path) -> None:
        self._paths = AcmePaths(data_home)
        self._lock = threading.Lock()

    def load(self, app_name: str) -> AcmeAppState:
        with self._lock:
            return self._load_unlocked(app_name)

    def save(self, app_name: str, state: AcmeAppState) -> None:
        with self._lock:
            self._save_unlocked(app_name, state)

    def record_success(
        self,
        app_name: str,
        *,
        names: List[str],
        not_after: str,
        now: Optional[float] = None,
    ) -> None:
        when = time.time() if now is None else now
        self.save(
            app_name,
            AcmeAppState(
                names=tuple(names),
                not_after=not_after,
                last_error=None,
                last_success_ts=when,
            ),
        )

    def record_error(self, app_name: str, message: str) -> None:
        with self._lock:
            state = self._load_unlocked(app_name)
            state.last_error = message.strip() or "ACME ensure failed"
            self._save_unlocked(app_name, state)

    def _load_unlocked(self, app_name: str) -> AcmeAppState:
        path = self._paths.app_state(app_name)
        if not path.is_file():
            return AcmeAppState()
        data = self._read_json(path)
        if data is None:
            return AcmeAppState()
        return AcmeAppState.from_mapping(data)

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _save_unlocked(self, app_name: str, state: AcmeAppState) -> None:
        self._paths.ensure_dirs()
        path = self._paths.app_state(app_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(state.to_mapping(), indent=2, sort_keys=True) + "\n"
        self._atomic_write(path, text)

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
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
            AcmeAppStore._unlink_quiet(tmp_name)
            raise

    @staticmethod
    def _unlink_quiet(tmp_name: str) -> None:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
