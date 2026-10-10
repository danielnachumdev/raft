"""Doctor warns when host MemAvailable is critically low."""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

from raft.adapters.host import HostMemory, HostResources
from raft.ops.doctor.checks.host import HostChecks
from raft.ops.doctor.context import DoctorContext
from raft.ops.doctor.models import INFRA

from .base import DoctorTestCase


class _FakeGateway:
    def __init__(self, memory: Optional[HostMemory]) -> None:
        self._memory = memory

    def resources(self) -> HostResources:
        return HostResources(
            cpus=1,
            loadavg=(0.0, 0.0, 0.0),
            memory=self._memory,
            disk=None,
            uptime_seconds=1.0,
        )


class TestHostMemoryWarn(DoctorTestCase):
    def test_warns_when_available_below_threshold(self) -> None:
        memory = HostMemory(
            total_bytes=1024 * 1024 * 1024,
            available_bytes=64 * 1024 * 1024,
            used_bytes=960 * 1024 * 1024,
            used_percent=93.75,
        )
        result = HostChecks()._memory(self._ctx(), gateway=_FakeGateway(memory))
        assert result is not None
        assert result.service == INFRA and result.check == "memory"
        assert result.status == "warn"
        assert "OOM" in result.detail
        assert "free memory" in (result.fix or "")

    def test_skips_when_memory_ok_or_unknown(self) -> None:
        ok = HostMemory(
            total_bytes=2 * 1024 * 1024 * 1024,
            available_bytes=512 * 1024 * 1024,
            used_bytes=1536 * 1024 * 1024,
            used_percent=75.0,
        )
        assert HostChecks()._memory(self._ctx(), gateway=_FakeGateway(ok)) is None
        assert HostChecks()._memory(self._ctx(), gateway=_FakeGateway(None)) is None

    def _ctx(self) -> DoctorContext:
        return DoctorContext(
            stack=self.stack,
            shell=MagicMock(),
            auth=MagicMock(),
            docker=self.mock_docker(),
        )
