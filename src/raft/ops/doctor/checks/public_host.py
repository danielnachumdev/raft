"""Public Host HTTP probes — catch green doctor while sites return 404/timeout."""

from __future__ import annotations

from raft.models.state.scaling_store import ScalingStore

from raft.adapters.http import HttpProbe
from ..context import DoctorContext
from ..models import CheckResult


class PublicHostChecks:
    name = "public_host"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        http = HttpProbe(ctx.stack)
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            if app.public_host:
                results.append(self._probe(ctx, http, app))
        return results

    def _probe(self, ctx: DoctorContext, http: HttpProbe, app) -> CheckResult:
        host = app.public_host
        if ScalingStore(ctx.stack.root).is_scaled_to_zero(app.name):
            return CheckResult(
                app.compose_id,
                "host",
                "ok",
                f"Host {host} (scaled to zero)",
            )
        path = self._readiness_path(ctx, app)
        if http.public_host_ok(app, path=path):
            return CheckResult(app.compose_id, "host", "ok", f"Host {host}{path}")
        return self._host_fail(ctx, app, host, path=path)

    def _host_fail(self, ctx: DoctorContext, app, host: str, *, path: str) -> CheckResult:
        detail = f"Host {host}{path} not OK on {ctx.stack.public_base_url}"
        first = self._first_diag_line(ctx, app)
        if first:
            detail = f"{detail} — {first}"
        return CheckResult(
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

    @staticmethod
    def _readiness_path(ctx: DoctorContext, app) -> str:
        try:
            path = ctx.stack.spec_for(app).readiness.path
        except Exception:  # noqa: BLE001 — doctor must still probe /
            return "/"
        if not path:
            return "/"
        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def _first_diag_line(ctx: DoctorContext, app) -> str:
        try:
            raw = ctx.docker.diagnostics_for(app.compose_id)
        except Exception:  # noqa: BLE001 — doctor must still report host fail
            return ""
        if not isinstance(raw, str) or not raw:
            return ""
        return next(
            (line for line in raw.splitlines() if line and not line.startswith("---")),
            "",
        )
