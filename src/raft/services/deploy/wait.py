"""Poll-until helpers for redeploy/cutover readiness waits."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from raft.errors import OperatorError, append_diagnostics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Step:
    key: str
    summary: str
    run: Callable[["CutoverSession"], None]


def wait_until(
    description: str,
    predicate: Callable[[], bool],
    *,
    timeout: float,
    interval: float = 1.0,
    fix: str = "",
    diagnostics: Optional[Callable[[], str]] = None,
    progress_every: float = 15.0,
) -> None:
    WaitUntil(
        description,
        predicate,
        timeout=timeout,
        interval=interval,
        fix=fix,
        diagnostics=diagnostics,
        progress_every=progress_every,
    ).run()


class WaitUntil:
    """Poll ``predicate`` until true or raise a timed-out OperatorError."""

    def __init__(
        self,
        description: str,
        predicate: Callable[[], bool],
        *,
        timeout: float,
        interval: float = 1.0,
        fix: str = "",
        diagnostics: Optional[Callable[[], str]] = None,
        progress_every: float = 15.0,
    ) -> None:
        self.description = description
        self.predicate = predicate
        self.timeout = timeout
        self.interval = interval
        self.fix = fix
        self.diagnostics = diagnostics
        self.progress_every = progress_every

    def run(self) -> None:
        started = time.monotonic()
        deadline = started + self.timeout
        next_progress = started + self.progress_every
        while time.monotonic() < deadline:
            if self.predicate():
                return
            next_progress = self._maybe_progress(started, deadline, next_progress)
            time.sleep(self.interval)
        self._raise_timeout(started)

    def _maybe_progress(self, started: float, deadline: float, next_progress: float) -> float:
        now = time.monotonic()
        if self.progress_every <= 0 or now < next_progress:
            return next_progress
        remaining = max(0.0, deadline - now)
        logger.info(
            "still waiting for: %s (%.0fs of %.0fs elapsed, %.0fs left)",
            self.description,
            now - started,
            self.timeout,
            remaining,
        )
        return now + self.progress_every

    def _raise_timeout(self, started: float) -> None:
        waited = time.monotonic() - started
        logger.error(
            "timed out waiting for: %s (waited %.0fs of %.0fs budget)",
            self.description,
            waited,
            self.timeout,
        )
        message = (
            f"timed out waiting for: {self.description} "
            f"(waited {waited:.0f}s of {self.timeout:.0f}s budget)"
        )
        message = self._with_diagnostics(message)
        if self.fix:
            message = f"{message}\nFix: {self.fix}"
        raise OperatorError(message, has_fix=bool(self.fix))

    def _with_diagnostics(self, message: str) -> str:
        if self.diagnostics is None:
            return message
        try:
            return append_diagnostics(message, self.diagnostics())
        except Exception:  # noqa: BLE001 — never mask the timeout
            logger.debug("diagnostics callback failed", exc_info=True)
            return message
