"""HTTP upstream fragment checks."""

from __future__ import annotations

from raft.errors import OperatorError

from ..context import DoctorContext
from ..models import CheckResult


class UpstreamChecks:
    name = "upstreams"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            results.extend(self._check_app(ctx, app))
        return results

    def _check_app(self, ctx: DoctorContext, app) -> list[CheckResult]:
        try:
            app_spec = ctx.stack.spec_for(app)
        except (ValueError, FileNotFoundError, OperatorError):
            return []
        http_ports = app_spec.http_ports()
        if not http_ports:
            return [
                CheckResult(
                    app.compose_id, "upstream", "ok", "n/a (no expose=http ports)"
                )
            ]
        return [self._port_result(ctx, app, port) for port in http_ports]

    @staticmethod
    def _port_result(ctx: DoctorContext, app, port) -> CheckResult:
        path = ctx.stack.upstream_file(app, port)
        if path.is_file():
            return CheckResult(app.compose_id, "upstream", "ok", str(path.name))
        return CheckResult(
            app.compose_id,
            "upstream",
            "warn",
            f"missing {path.name}",
            fix="created automatically on `raft sync` / `raft up`",
        )
