"""Compose runtime: which core services are up (and healthy)."""

from __future__ import annotations

import shutil
from typing import Optional, Tuple

from raft.adapters.docker.crash_loop import CrashLoopDetector
from raft.models.scaling_store import ScalingStore

from ..context import DoctorContext
from ..models import INFRA, CheckResult

_Bad = Optional[Tuple[str, str]]


class RuntimeChecks:
    name = "runtime"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        if not shutil.which("docker"):
            return [CheckResult(INFRA, "stack", "warn", "skipped (docker unavailable)")]
        try:
            running = set(ctx.running_services())
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
        return [
            cls._edge_service_result(ctx, name, running)
            for name in (ctx.stack.gate, ctx.stack.router)
        ]

    @classmethod
    def _edge_service_result(
        cls, ctx: DoctorContext, name: str, running: set[str]
    ) -> CheckResult:
        if name in running:
            return cls._health_result(ctx, name)
        crash = cls._crash_loop_bad(ctx, name)
        if crash is not None:
            level, detail = crash
            return CheckResult(
                name,
                "running",
                level,
                detail,
                fix=CrashLoopDetector.fix_cta(name),
            )
        return CheckResult(name, "running", "warn", "not running", fix="raft up")

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
        """Fail/warn when a running app or controller is unhealthy/crash-looping."""
        edge = {ctx.stack.gate, ctx.stack.router}
        skip = edge | cls._scaled_compose_ids(ctx)
        results: list[CheckResult] = []
        watched = running | cls._restarting_services(ctx, skip)
        for service in sorted(watched):
            if service in skip:
                continue
            result = cls._health_result(ctx, service)
            if result.status != "ok":
                results.append(result)
        return results

    @staticmethod
    def _restarting_services(ctx: DoctorContext, skip: set[str]) -> set[str]:
        """Compose services in ``restarting`` state (not covered by ``running``)."""
        found: set[str] = set()
        for name in ctx.stack.core_services:
            if name in skip:
                continue
            status, _health = ctx.service_runtime(name)
            if status == "restarting":
                found.add(name)
        return found

    @classmethod
    def _health_result(cls, ctx: DoctorContext, service: str) -> CheckResult:
        status, health = ctx.service_runtime(service)
        bad = cls._crash_loop_bad(ctx, service) or cls._bad_health(status, health)
        if bad is None:
            return CheckResult(service, "running", "ok", "up")
        level, detail = bad
        fix = (
            CrashLoopDetector.fix_cta(service)
            if detail.startswith("crash-looping")
            else cls._health_fix(service)
        )
        return CheckResult(service, "running", level, detail, fix=fix)

    @classmethod
    def _crash_loop_bad(cls, ctx: DoctorContext, service: str) -> _Bad:
        row = ctx.runtime_rows().get(service)
        if row is None:
            return None
        uptime = CrashLoopDetector.uptime_seconds(row.started_at)
        if not CrashLoopDetector.is_crash_looping(
            status=row.status,
            restart_count=row.restart_count,
            uptime_seconds=uptime,
            oom_killed=row.oom_killed,
        ):
            return None
        # Intentional stop must not look like crash-loop (scaled apps skipped upstream).
        return (
            "fail",
            CrashLoopDetector.detail(
                restart_count=row.restart_count,
                uptime_seconds=uptime,
                oom_killed=row.oom_killed,
            ),
        )

    @staticmethod
    def _bad_health(status: str, health: str) -> _Bad:
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
            return CheckResult(
                INFRA, "stack", "warn", "no core services running", fix="raft up"
            )
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
