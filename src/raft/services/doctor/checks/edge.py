"""Edge listener probes and gate published-port drift."""

from __future__ import annotations

import shutil
import socket

from ....config.settings import load_config
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
        try:
            running = set(ctx.docker.running_services()) if shutil.which("docker") else set()
        except Exception:  # noqa: BLE001
            running = set()
        gate_up = ctx.stack.gate in running
        results: list[CheckResult] = []
        for port, protocol in published:
            if protocol != "tcp":
                results.append(
                    CheckResult(
                        INFRA,
                        f"port {port}/{protocol}",
                        "ok",
                        "declared (udp listen not probed)",
                    )
                )
                continue
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                    in_use = True
            except OSError:
                in_use = False
            label = f"port {port}"
            if in_use and gate_up:
                results.append(CheckResult(INFRA, label, "ok", "accepting (gate running)"))
            elif in_use and not gate_up:
                results.append(
                    CheckResult(
                        INFRA,
                        label,
                        "warn",
                        f"something is listening on 127.0.0.1:{port} (gate may fail to bind)",
                        fix="stop the other process, or change edge ports in settings.yaml",
                    )
                )
            elif gate_up:
                results.append(
                    CheckResult(
                        INFRA,
                        label,
                        "warn",
                        f"gate running but nothing accepting on 127.0.0.1:{port}",
                        fix="raft gate recreate   # pick up edge: ports",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        INFRA,
                        label,
                        "ok",
                        f"nothing accepting on 127.0.0.1:{port}",
                    )
                )
        return results

    def _gate_drift(self, ctx: DoctorContext) -> list[CheckResult]:
        if not shutil.which("docker"):
            return []
        try:
            running = set(ctx.docker.running_services())
        except Exception:  # noqa: BLE001
            return []
        if ctx.stack.gate not in running:
            return []
        edge = load_config(ctx.stack.root).edge
        declared = sorted({p for p, _ in edge.published_ports()})
        actual = ctx.docker.gate_published_ports()
        if not actual:
            return [
                CheckResult(
                    ctx.stack.gate,
                    "ports",
                    "warn",
                    "could not inspect gate published ports",
                    fix="raft gate recreate",
                )
            ]
        if declared == actual:
            return [
                CheckResult(
                    ctx.stack.gate,
                    "ports",
                    "ok",
                    f"match edge: {declared}",
                )
            ]
        return [
            CheckResult(
                ctx.stack.gate,
                "ports",
                "fail",
                f"declared {declared} but gate publishes {actual}",
                fix="raft gate recreate   # Docker binds ports at create time",
            )
        ]
