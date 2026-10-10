"""Purge service: lock, reclaim report, API payload."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from raft.services.ops.purge import Purge, PurgeResult

from ..base import ServicesTestCase


class TestPurge(ServicesTestCase):
    def _mgr(self, *, image: int = 0, builder: int = 0) -> Purge:
        prune = MagicMock()
        prune.unused_images.return_value = image
        prune.build_cache.return_value = builder
        return Purge(self.stack, shell=MagicMock(), docker_prune=prune)

    @staticmethod
    @contextmanager
    def _lock():
        with patch("raft.services.ops.purge.stack_lock") as lock:
            lock.return_value.__enter__ = MagicMock()
            lock.return_value.__exit__ = MagicMock(return_value=False)
            yield lock

    def test_execute_sums_reclaim_under_lock(self) -> None:
        mgr = self._mgr(image=1024, builder=2048)
        with self._lock() as lock:
            result = mgr.execute()
        lock.assert_called_once_with(self.stack.root)
        assert result.reclaimed_bytes == 3072
        assert result.image_bytes == 1024
        assert result.builder_bytes == 2048
        assert result.reclaimed_human == "3.0KiB"

    def test_run_prints_reclaim(self, capsys) -> None:
        mgr = self._mgr(image=1024 * 1024, builder=0)
        with self._lock():
            mgr.run()
        out = capsys.readouterr().out
        assert "Purging unused" in out
        assert "reclaimed 1.0MiB" in out
        assert "images 1.0MiB" in out

    def test_run_prints_nothing_to_reclaim(self, capsys) -> None:
        mgr = self._mgr()
        with self._lock():
            mgr.run()
        assert "nothing to reclaim" in capsys.readouterr().out

    def test_as_api_shape(self) -> None:
        payload = PurgeResult(3072, 1024, 2048).as_api()
        assert payload["ok"] is True
        assert payload["action"] == "purge"
        assert payload["reclaimed_bytes"] == 3072
        assert payload["reclaimed_human"] == "3.0KiB"
        assert payload["images_bytes"] == 1024
        assert payload["builder_bytes"] == 2048

    def test_default_shell_and_prune(self) -> None:
        with patch("raft.services.ops.purge.Shell") as shell_cls:
            with patch("raft.services.ops.purge.DockerPrune") as prune_cls:
                shell = MagicMock()
                prune = MagicMock()
                prune.unused_images.return_value = 0
                prune.build_cache.return_value = 0
                shell_cls.return_value = shell
                prune_cls.return_value = prune
                with self._lock():
                    Purge(self.stack).execute()
        shell_cls.assert_called_once_with(self.stack.root)
        prune_cls.assert_called_once_with(shell)
