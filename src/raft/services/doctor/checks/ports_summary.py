"""Per-service port summary for doctor OK lines."""

from __future__ import annotations

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
            try:
                spec = ctx.stack.spec_for(app)
            except (OSError, OperatorError, ValueError, FileNotFoundError):
                continue
            if not spec.ports:
                continue
            seen: set[str] = set()
            ordered: list[str] = []
            for port in spec.ports:
                label = _port_number(port)
                if label in seen:
                    continue
                seen.add(label)
                ordered.append(label)
            results.append(
                CheckResult(app.compose_id, "ports", "ok", ", ".join(ordered))
            )
        return results
