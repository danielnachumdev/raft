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
                detail = f"Host {host} not OK on {ctx.stack.public_base_url}"
                try:
                    raw = ctx.docker.diagnostics_for(app.compose_id)
                except Exception:  # noqa: BLE001 — doctor must still report host fail
                    raw = ""
                diag = raw if isinstance(raw, str) else ""
                if diag:
                    # Keep the first log line in the detail so the table stays scannable.
                    first = next(
                        (
                            line
                            for line in diag.splitlines()
                            if line and not line.startswith("---")
                        ),
                        "",
                    )
                    if first:
                        detail = f"{detail} — {first}"
                results.append(
                    CheckResult(
                        app.compose_id,
                        "host",
                        "fail",
                        detail,
                        fix=(
                            "raft render && raft redeploy router   "
                            "# gate must reach raft-router; check certs / upstream; "
                            f"docker compose -f ~/.raft/compose.yaml logs --tail=40 "
                            f"{app.compose_id}"
                        ),
                    )
                )
        return results
