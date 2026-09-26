"""Compose runtime: which core services are up (and healthy)."""

from __future__ import annotations

import shutil

from raft.models.scaling_store import ScalingStore

from ..context import DoctorContext
from ..models import INFRA, CheckResult


class RuntimeChecks:
    name = "runtime"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        if not shutil.which("docker"):
            return [CheckResult(INFRA, "stack", "warn", "skipped (docker unavailable)")]
        try:
            running = set(ctx.docker.running_services())
        except Exception as exc:  # noqa: BLE001
            return [
                CheckResult(
                    INFRA,
                    "stack",
                    "warn",
                    f"could not query compose: {exc}",
                    fix="ensure compose.yaml is valid and docker works",
                )
            ]
        return [
            *self._edge_running(ctx, running),
            *self._scaled_apps(ctx),
            *self._health_for_running(ctx, running),
            self._stack_summary(ctx, running),
        ]

    @classmethod
    def _edge_running(cls, ctx: DoctorContext, running: set[str]) -> list[CheckResult]:
        results: list[CheckResult] = []
        for name in (ctx.stack.gate, ctx.stack.router):
            if name not in running:
                results.append(
                    CheckResult(name, "running", "warn", "not running", fix="raft up")
                )
            else:
                results.append(cls._health_result(ctx, name))
        return results

    @staticmethod
    def _scaled_apps(ctx: DoctorContext) -> list[CheckResult]:
        store = ScalingStore(ctx.stack.root)
        return [
            CheckResult(
                app.compose_id,
                "scaling",
                "ok",
                "scaled to zero (intentional)",
            )
            for app in ctx.stack.apps
            if store.is_scaled_to_zero(app.name)
        ]

    @classmethod
    def _health_for_running(
        cls, ctx: DoctorContext, running: set[str]
    ) -> list[CheckResult]:
        """Fail/warn when a running app or controller is unhealthy/restarting."""
        edge = {ctx.stack.gate, ctx.stack.router}
        skip = edge | cls._scaled_compose_ids(ctx)
        results: list[CheckResult] = []
        for service in sorted(running):
            if service in skip:
                continue
            result = cls._health_result(ctx, service)
            if result.status != "ok":
                results.append(result)
        return results

    @classmethod
    def _health_result(cls, ctx: DoctorContext, service: str) -> CheckResult:
        status, health = ctx.docker.service_runtime(service)
        bad = cls._bad_health(status, health)
        if bad is None:
            return CheckResult(service, "running", "ok", "up")
        level, detail = bad
        return CheckResult(
            service, "running", level, detail, fix=cls._health_fix(service)
        )

    @staticmethod
    def _bad_health(status: str, health: str):
        if status == "restarting":
            return ("fail", "restarting")
        if health == "unhealthy":
            return ("fail", "unhealthy")
        if health == "starting":
            return ("warn", "health starting")
        return None

    @staticmethod
    def _health_fix(service: str) -> str:
        return (
            f"docker compose -f ~/.raft/compose.yaml logs --tail=40 {service}   "
            f"# then raft redeploy <app> (or raft redeploy router)"
        )

    @classmethod
    def _stack_summary(cls, ctx: DoctorContext, running: set[str]) -> CheckResult:
        expected = list(ctx.stack.core_services)
        intentional = cls._scaled_compose_ids(ctx)
        missing = [s for s in expected if s not in running and s not in intentional]
        if not missing:
            live = [s for s in expected if s in running]
            return CheckResult(INFRA, "stack", "ok", f"running: {', '.join(live)}")
        if not running:
            return CheckResult(INFRA, "stack", "warn", "no core services running", fix="raft up")
        return CheckResult(
            INFRA,
            "stack",
            "warn",
            f"running {sorted(running)}; missing {missing}",
            fix="raft up   # or redeploy the missing service",
        )

    @staticmethod
    def _scaled_compose_ids(ctx: DoctorContext) -> set[str]:
        store = ScalingStore(ctx.stack.root)
        return {
            app.compose_id
            for app in ctx.stack.apps
            if store.is_scaled_to_zero(app.name)
        }
