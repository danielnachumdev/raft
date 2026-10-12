"""Doctor suite timing and compose-call observability."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from raft.ops.doctor.context import DoctorContext
from raft.ops.doctor.models import CheckResult
from raft.ops.doctor.observability import ComposeCallCounter, SuiteTiming

from .base import DoctorTestCase


class _ComposeProbeSuite:
    name = "compose_probe"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        ctx.shell.compose("ps", "-q", "raft-gate", capture=True, check=False)
        ctx.shell.compose("logs", "--tail", "1", "raft-gate", capture=True, check=False)
        return []


class TestDoctorObservability(DoctorTestCase):
    def test_suite_start_done_and_compose_summary(self, caplog) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        shell = self.mock_shell()
        docker = self.mock_docker(running=["raft-gate", "raft-router"])
        doctor = self.doctor(shell=shell, docker=docker)
        doctor._suites = (_ComposeProbeSuite(),)  # type: ignore[assignment]
        with caplog.at_level(logging.INFO, logger="raft.ops.doctor.observability"):
            with self.doctor_env():
                doctor.run()
        messages = [r.getMessage() for r in caplog.records]
        assert "doctor suite start name=compose_probe" in messages
        assert any(
            m.startswith("doctor suite done name=compose_probe elapsed_ms=") for m in messages
        )
        assert "doctor compose calls total=2 ps=1" in messages
        assert shell.compose.call_count == 2

    def test_all_default_suites_emit_timing(self, caplog) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        docker = self.mock_docker(running=["raft-gate", "raft-router"])
        doctor = self.doctor(shell=self.mock_shell(), docker=docker)
        with caplog.at_level(logging.INFO, logger="raft.ops.doctor.observability"):
            with self.doctor_env():
                doctor.run()
        messages = [r.getMessage() for r in caplog.records]
        for name in ("host", "apps", "runtime", "public_host"):
            assert f"doctor suite start name={name}" in messages
            assert any(m.startswith(f"doctor suite done name={name} elapsed_ms=") for m in messages)
        assert any(m.startswith("doctor compose calls total=") for m in messages)


class TestComposeCallCounter(DoctorTestCase):
    def test_counts_ps_and_restores(self) -> None:
        shell = MagicMock()
        shell.compose = MagicMock(return_value="ok")
        counter = ComposeCallCounter()
        counter.install(shell, shell, None)
        shell.compose("ps", "-q", "x")
        shell.compose("up", "-d")
        assert counter.total == 2
        assert counter.ps == 1
        counter.uninstall()
        shell.compose("ps")
        assert counter.total == 2

    def test_skips_shell_without_callable_compose(self) -> None:
        bare = MagicMock(spec=[])
        counter = ComposeCallCounter()
        counter.install(bare)
        assert counter.total == 0
        assert counter._restores == []


class TestSuiteTiming(DoctorTestCase):
    def test_elapsed_ms_from_clock(self, caplog) -> None:
        ticks = iter([1.0, 1.25])
        timing = SuiteTiming("edge", clock=lambda: next(ticks))
        with caplog.at_level(logging.INFO, logger="raft.ops.doctor.observability"):
            timing.start()
            timing.done()
        messages = [r.getMessage() for r in caplog.records]
        assert messages == [
            "doctor suite start name=edge",
            "doctor suite done name=edge elapsed_ms=250",
        ]
