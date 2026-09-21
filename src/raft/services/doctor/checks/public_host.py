"""Public Host HTTP probes — catch green doctor while sites return 404/timeout."""

from __future__ import annotations

from ....adapters.http import HttpProbe
from ..context import DoctorContext
from ..models import CheckResult


class PublicHostChecks:
    name = "public_host"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        http = HttpProbe(ctx.stack)
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            if not app.public_host:
                continue
            host = app.public_host
            if http.public_host_ok(app):
                results.append(
                    CheckResult(
                        app.compose_id,
                        "host",
                        "ok",
                        f"Host {host}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        app.compose_id,
                        "host",
                        "fail",
                        f"Host {host} not OK on {ctx.stack.public_base_url}",
                        fix=(
                            "raft render && raft redeploy router   "
                            "# gate must reach raft-router; check certs / upstream"
                        ),
                    )
                )
        return results
