"""Edge listener probes and gate published-port drift."""

from __future__ import annotations

import shutil
import socket

from .....config.settings import load_config
from ..context import DoctorContext
from ..models import INFRA, CheckResult


class EdgeChecks:
    name = "edge"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        results = self._listeners(ctx)
        results.extend(self._gate_drift(ctx))
        return results

    def _listeners(self, ctx: DoctorContext) -> list[CheckResult]:
        edge = load_config(ctx.stack.root).edge
        published = edge.published_ports()
        if not published:
            return [
                CheckResult(
                    INFRA,
                    "edge",
                    "warn",
                    "no edge listeners declared in settings.yaml",
                    fix="set edge.http / edge.https / edge.streams in ~/.raft/settings.yaml",
                )
            ]
        gate_up = self._gate_is_up(ctx)
        return [
            self._probe_listener(port, protocol, gate_up=gate_up)
            for port, protocol in published
        ]

    def _gate_is_up(self, ctx: DoctorContext) -> bool:
        try:
            running = set(ctx.docker.running_services()) if shutil.which("docker") else set()
        except Exception:  # noqa: BLE001
            running = set()
        return ctx.stack.gate in running

    def _probe_listener(
        self, port: int, protocol: str, *, gate_up: bool
    ) -> CheckResult:
        if protocol != "tcp":
            return CheckResult(
                INFRA, f"port {port}/{protocol}", "ok",
                "declared (udp listen not probed)",
            )
        return self._tcp_listener_result(port, in_use=self._tcp_in_use(port), gate_up=gate_up)

    @staticmethod
    def _tcp_listener_result(port: int, *, in_use: bool, gate_up: bool) -> CheckResult:
        label = f"port {port}"
        if in_use and gate_up:
            return CheckResult(INFRA, label, "ok", "accepting (gate running)")
        if in_use and not gate_up:
            return CheckResult(
                INFRA, label, "warn",
                f"something is listening on 127.0.0.1:{port} (gate may fail to bind)",
                fix="stop the other process, or change edge ports in settings.yaml",
            )
        if gate_up:
            return CheckResult(
                INFRA, label, "warn",
                f"gate running but nothing accepting on 127.0.0.1:{port}",
                fix="raft gate recreate   # pick up edge: ports",
            )
        return CheckResult(
            INFRA, label, "ok", f"nothing accepting on 127.0.0.1:{port}"
        )

    @staticmethod
    def _tcp_in_use(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                return True
        except OSError:
            return False

    def _gate_drift(self, ctx: DoctorContext) -> list[CheckResult]:
        if not shutil.which("docker"):
            return []
        try:
            running = set(ctx.docker.running_services())
        except Exception:  # noqa: BLE001
            return []
        if ctx.stack.gate not in running:
            return []
        return self._compare_gate_ports(ctx)

    def _compare_gate_ports(self, ctx: DoctorContext) -> list[CheckResult]:
        edge = load_config(ctx.stack.root).edge
        declared = sorted({p for p, _ in edge.published_ports()})
        actual = ctx.docker.gate_published_ports()
        gate = ctx.stack.gate
        if not actual:
            return [CheckResult(gate, "ports", "warn",
                "could not inspect gate published ports", fix="raft gate recreate")]
        if declared == actual:
            return [CheckResult(gate, "ports", "ok", ", ".join(str(p) for p in actual))]
        return [CheckResult(gate, "ports", "fail",
            f"declared {declared} but gate publishes {actual}",
            fix="raft gate recreate   # Docker binds ports at create time")]
