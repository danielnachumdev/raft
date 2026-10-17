"""Controller-owned runtime.json store."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..constants import ALERTS_STATE_DIR, RUNTIME_NAME
from .atomic import AtomicText
from .runtime_state import AlertRuntime

logger = logging.getLogger(__name__)


class AlertRuntimeStore:
    """Atomic JSON store for alert runtime instances."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.path = home / ALERTS_STATE_DIR / RUNTIME_NAME

    def load(self) -> AlertRuntime:
        if not self.path.is_file():
            return AlertRuntime.empty()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._quarantine(exc)
            return AlertRuntime.empty()
        if not isinstance(raw, dict):
            self._quarantine(ValueError("not a mapping"))
            return AlertRuntime.empty()
        return AlertRuntime.from_mapping(raw)

    def save(self, runtime: AlertRuntime) -> None:
        text = json.dumps(runtime.to_mapping(), indent=2, sort_keys=False)
        AtomicText.write(self.path, text + "\n", mode=0o600)

    def ensure_writable(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        probe = self.path.parent / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)

    def _quarantine(self, exc: BaseException) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        dest = self.path.with_name(f"{RUNTIME_NAME}.corrupt-{ts}")
        try:
            self.path.rename(dest)
            logger.warning("quarantined corrupt runtime.json to %s (%s)", dest, exc)
        except OSError:
            logger.warning("corrupt runtime.json (%s); using empty runtime", exc)
