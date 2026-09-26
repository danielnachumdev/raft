"""Deadline polling for e2e / integration readiness checks."""

from __future__ import annotations

import time
from typing import Callable


class Wait:
    """Poll until a predicate is true or raise TimeoutError."""

    @staticmethod
    def until(
        predicate: Callable[[], bool],
        *,
        timeout: float = 45.0,
        interval: float = 0.25,
        message: str = "condition not met",
    ) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(interval)
        raise TimeoutError(message)
