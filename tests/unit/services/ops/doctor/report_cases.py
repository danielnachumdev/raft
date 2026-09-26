"""Doctor report CheckResult factories and assertion helpers."""

from __future__ import annotations

import io

from raft.services.ops.doctor import INFRA, CheckResult


class ReportCases:
    @staticmethod
    def ok_infra_and_svc():
        return [
            CheckResult(INFRA, "docker", "ok", "fine"),
            CheckResult("svc", "auth", "ok", "fine"),
            CheckResult("svc", "sync", "ok", "fine"),
        ]

    @staticmethod
    def warn_svc():
        return [
            CheckResult("svc", "auth", "ok", "fine"),
            CheckResult("svc", "sync", "warn", "maybe", fix="do x"),
        ]

    @staticmethod
    def fail_hub_multiline():
        return [
            CheckResult(
                "hub",
                "sync",
                "fail",
                "docker image missing locally: ghcr.io/org/hub:main",
                fix="line one\nline two\nline three",
            ),
        ]

    @staticmethod
    def fail_infra_docker():
        return [CheckResult(INFRA, "docker", "fail", "bad", fix="fix it")]

    @staticmethod
    def raft_group_mix():
        return [
            CheckResult(INFRA, "compose.yaml", "ok", "fine"),
            CheckResult(INFRA, "port 80", "ok", "host probe"),
            CheckResult("raft-gate", "running", "ok", "up"),
            CheckResult("raft-gate", "ports", "ok", "80, 443"),
            CheckResult("raft-router", "ports", "ok", "80"),
            CheckResult("raft-raftling", "contract", "ok", "fine"),
            CheckResult("raft-raftling", "ports", "ok", "80"),
            CheckResult("solo", "contract", "ok", "fine"),
            CheckResult("solo", "ports", "ok", "80"),
            CheckResult("orphan", "x", "ok", "fine"),
        ]


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


class NoTty:
    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        return None
