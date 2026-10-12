"""Shared Scaler arrange helpers for idle/wake unit tests."""

from pathlib import Path
from unittest.mock import MagicMock

from raft.services.controller.jobs.scale import Scaler

from tests.unit.base import AppliedInventory
from tests.unit.services.controller.base import ControllerTestCase


class ScalerTestCase(ControllerTestCase):
    def scaler(self, tmp_path: Path, *, docker=None, with_scaling: bool = True):
        extra = self.scaling_extra() if with_scaling else None
        home = self.applied_home(tmp_path, extra=extra)
        docker = docker or MagicMock()
        return Scaler(home, docker), docker

    def dep_scaler(self, tmp_path: Path):
        home = self.raft_home(tmp_path)
        AppliedInventory.write_applied_app(home, "api")
        AppliedInventory.write_applied_app(
            home,
            self.APP,
            extra={**self.scaling_extra(), "dependsOn": ["api"]},
        )
        docker = MagicMock()
        return home, docker, Scaler(home, docker)
