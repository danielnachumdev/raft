"""Shared Orchestrator test case."""

from __future__ import annotations

import pytest

from ...base import ServicesTestCase


class OrchestratorTestCase(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _orch_setup(self, _services_setup) -> None:
        self.orch = self.orchestrator()
