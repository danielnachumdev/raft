"""Check suite protocol."""

from __future__ import annotations

from typing import Protocol

from ..context import DoctorContext
from ..models import CheckResult


class CheckSuite(Protocol):  # pragma: no cover
    """One cohesive group of doctor probes."""

    name: str

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        ...
