"""Shared controller test helpers (locks, applied home, scaling extras)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
from unittest.mock import MagicMock, patch

from raft.config.paths import ensure_raft_home
from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer

from ..base import write_applied_app

LOCKS_HEAL = "raft.controller.heal.app_and_stack_locks"
LOCKS_SCALE_APPS = "raft.controller.scale.apps_and_stack_locks"
LOCKS_SCALE_DEPS = "raft.controller.scale_depends.apps_and_stack_locks"


class ControllerTestCase:
    """Declarative home + mocked flock for heal/scale unit tests."""

    APP = "web"

    def raft_home(self, tmp_path: Path) -> Path:
        return ensure_raft_home(tmp_path / "home")

    def applied_home(self, tmp_path: Path, **write_kwargs: Any) -> Path:
        home = self.raft_home(tmp_path)
        write_applied_app(home, self.APP, **write_kwargs)
        return home

    @staticmethod
    def scaling_extra() -> dict:
        return {
            "scaling": {
                "idleSeconds": 10,
                "wakeTimeoutSeconds": 30,
                "minUpSeconds": 5,
            }
        }

    @staticmethod
    @contextmanager
    def patched_locks(target: str) -> Iterator[MagicMock]:
        with patch(target) as locks:
            locks.return_value.__enter__ = MagicMock(return_value=None)
            locks.return_value.__exit__ = MagicMock(return_value=False)
            yield locks

    def with_heal_locks(self):
        return self.patched_locks(LOCKS_HEAL)

    def with_scale_locks(self):
        return self._patched_scale_locks()

    @contextmanager
    def _patched_scale_locks(self) -> Iterator[MagicMock]:
        with self.patched_locks(LOCKS_SCALE_APPS) as wake:
            with self.patched_locks(LOCKS_SCALE_DEPS) as idle:
                yield wake or idle

    def unhealthy_healer(
        self,
        tmp_path: Path,
        cfg: HealingConfig,
        *,
        deploy: Optional[Any] = None,
    ):
        home = self.applied_home(tmp_path)
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "unhealthy")
        return Healer(home, cfg, docker, deploy=deploy), docker, deploy
