"""Shared DockerStack test case."""

from __future__ import annotations

import pytest

from ..base import AdapterTestCase


class DockerTestCase(AdapterTestCase):
    @pytest.fixture(autouse=True)
    def _docker_setup(self, _adapter_setup) -> None:
        self.docker = self.docker_stack()
