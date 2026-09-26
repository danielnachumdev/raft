"""Per-service port summary for doctor OK lines."""

from __future__ import annotations

from typing import Optional

from raft.errors import OperatorError

from ....models.ports import PortSpec
from ..context import DoctorContext
from ..models import CheckResult


def _port_number(port: PortSpec) -> str:
    """Host-facing port when published; otherwise the container listen port."""
    if port.public_port is not None:
        return str(port.public_port)
    return str(port.container_port)


class PortSummaryChecks:
    """Emit an ok ``ports`` check for router + each app (gate comes from EdgeChecks)."""

    name = "ports_summary"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        results: list[CheckResult] = [
            CheckResult(ctx.stack.router, "ports", "ok", "80"),
        ]
        for app in ctx.stack.apps:
            detail = self._app_ports_detail(ctx, app)
            if detail is not None:
                results.append(CheckResult(app.compose_id, "ports", "ok", detail))
        return results

    @staticmethod
    def _app_ports_detail(ctx: DoctorContext, app) -> Optional[str]:
        try:
            spec = ctx.stack.spec_for(app)
        except (OSError, OperatorError, ValueError, FileNotFoundError):
            return None
        if not spec.ports:
            return None
        seen: set[str] = set()
        ordered: list[str] = []
        for port in spec.ports:
            label = _port_number(port)
            if label not in seen:
                seen.add(label)
                ordered.append(label)
        return ", ".join(ordered)
