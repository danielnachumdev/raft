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
            try:
                app_spec = ctx.stack.spec_for(app)
            except (ValueError, FileNotFoundError, OperatorError):
                continue
            http_ports = app_spec.http_ports()
            if not http_ports:
                results.append(
                    CheckResult(
                        app.compose_id,
                        "upstream",
                        "ok",
                        "n/a (no expose=http ports)",
                    )
                )
                continue
            for port in http_ports:
                path = ctx.stack.upstream_file(app, port)
                if path.is_file():
                    results.append(CheckResult(app.compose_id, "upstream", "ok", str(path.name)))
                else:
                    results.append(
                        CheckResult(app.compose_id,
                            "upstream",
                            "warn",
                            f"missing {path.name}",
                            fix="created automatically on `raft sync` / `raft up`",
                        )
                    )
        return results
