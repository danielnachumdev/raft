"""Per-app ACME order state under ``state/acme/apps/<app>.json``."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from .paths import AcmePaths


@dataclass
class AcmeAppState:
    """Persisted issuance metadata (camelCase JSON keys)."""

    names: tuple[str, ...] = ()
    not_after: Optional[str] = None
    last_error: Optional[str] = None
    last_success_ts: Optional[float] = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AcmeAppState":
        names_raw = data.get("names") or []
        names = tuple(str(n) for n in names_raw) if isinstance(names_raw, list) else ()
        return cls(
            names=names,
            not_after=_opt_str(data.get("notAfter")),
            last_error=_opt_str(data.get("lastError")),
            last_success_ts=_opt_float(data.get("lastSuccessTs")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "names": list(self.names),
            "notAfter": self.not_after,
            "lastError": self.last_error,
            "lastSuccessTs": self.last_success_ts,
        }


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


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
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AcmeAppState()
        if not isinstance(data, dict):
            return AcmeAppState()
        return AcmeAppState.from_mapping(data)

    def _save_unlocked(self, app_name: str, state: AcmeAppState) -> None:
        self._paths.ensure_dirs()
        path = self._paths.app_state(app_name)
        text = json.dumps(state.to_mapping(), indent=2, sort_keys=True) + "\n"
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
