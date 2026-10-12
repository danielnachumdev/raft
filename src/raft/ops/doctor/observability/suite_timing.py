"""INFO start/done spans for one doctor check suite."""

import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SuiteTiming:
    """INFO start/done spans for one check suite."""

    def __init__(self, name: str, *, clock: Optional[Callable[[], float]] = None) -> None:
        self.name = name
        self._clock = clock or time.perf_counter
        self._started = 0.0

    def start(self) -> None:
        self._started = self._clock()
        logger.info("doctor suite start name=%s", self.name)

    def done(self) -> None:
        elapsed_ms = int((self._clock() - self._started) * 1000)
        logger.info("doctor suite done name=%s elapsed_ms=%s", self.name, elapsed_ms)
