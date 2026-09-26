"""Shared Orchestrator test case."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest

from tests.shared.compose_ids import RunningServices

from ...base import ServicesTestCase


class OrchestratorTestCase(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _orch_setup(self, _services_setup) -> None:
        self.orch = self.orchestrator()

    def set_running(self, *services: str, orch=None) -> None:
        target = orch if orch is not None else self.orch
        target.docker.running_services.return_value = list(services)

    def set_edge_running(self, *apps: str, orch=None) -> None:
        self.set_running(*RunningServices.with_apps(*apps), orch=orch)

    def set_edge_only(self, orch=None) -> None:
        self.set_running(*RunningServices.edge(), orch=orch)

    @contextmanager
    def render_with_gate_stamp(
        self,
        *,
        fingerprint: str,
        read: Optional[str],
        patch_certs: bool = False,
    ) -> Iterator[MagicMock]:
        with patch("raft.services.deploy.orchestrator.GateNginxStamp") as stamp_cls:
            stamp = stamp_cls.return_value
            stamp.fingerprint.return_value = fingerprint
            stamp.read.return_value = read
            with self._render_patches(patch_certs):
                yield stamp

    @contextmanager
    def _render_patches(self, patch_certs: bool) -> Iterator[None]:
        with patch("raft.services.deploy.orchestrator.StackRenderer"):
            if patch_certs:
                with patch("raft.services.deploy.orchestrator.require_origin_certs"):
                    yield
            else:
                yield
