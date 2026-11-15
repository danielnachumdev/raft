"""``raft delete app`` removes durable tree + Compose unit + auth leftovers."""

from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.apply import AppApply, AppDelete
from raft.core.platform.locking.paths import LockPaths

from tests.unit.base import AppliedInventory
from .base import ApplyTestCase


class TestAppDelete(ApplyTestCase):
    def test_delete_removes_tree_compose_and_job_locks(self, capsys) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "web", public_host="web.test"
        )
        paths = ServicePaths(self.tmp_path, "web")
        paths.ensure_scaffold()
        (paths.checkout() / "README.md").write_text("demo", encoding="utf-8")
        (paths.secrets() / "env").write_text("X=1\n", encoding="utf-8")
        locks = LockPaths(self.tmp_path)
        locks.directory().mkdir(parents=True, exist_ok=True)
        locks.host_job_flight("redeploy-web").write_text("{}", encoding="utf-8")
        locks.fifo("redeploy-web").mkdir(parents=True, exist_ok=True)

        docker = MagicMock()
        auth = MagicMock()
        auth.is_configured.return_value = False
        with patch(
            "raft.core.lifecycle.apply.delete.Orchestrator"
        ) as orch_cls:
            with patch(
                "raft.core.lifecycle.apply.delete.load_stack",
                return_value=load_stack(self.tmp_path),
            ):
                AppDelete(
                    load_stack(self.tmp_path), docker=docker, auth=auth
                ).run("web")
            orch_cls.return_value.render.assert_called_once()

        docker.remove_service.assert_called_once_with("web")
        assert not paths.root().exists()
        assert not locks.host_job_flight("redeploy-web").exists()
        assert not locks.fifo("redeploy-web").exists()
        assert "deleted web" in capsys.readouterr().out

    def test_app_apply_delete_delegates(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "web", public_host="web.test"
        )
        with patch(
            "raft.core.lifecycle.apply.service.AppDelete"
        ) as delete_cls:
            delete_cls.return_value = MagicMock()
            AppApply(load_stack(self.tmp_path)).delete("web")
        delete_cls.assert_called_once()
        delete_cls.return_value.run.assert_called_once_with("web")

    def test_delete_unknown_raises(self) -> None:
        with pytest.raises(RuntimeError, match="not applied"):
            AppDelete(load_stack(self.tmp_path), docker=MagicMock()).run("ghost")

    def test_delete_removes_local_auth_when_configured(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "web", public_host="web.test"
        )
        ServicePaths(self.tmp_path, "web").ensure_scaffold()
        auth = MagicMock()
        auth.is_configured.return_value = True
        with patch("raft.core.lifecycle.apply.delete.Orchestrator"):
            with patch(
                "raft.core.lifecycle.apply.delete.load_stack",
                return_value=load_stack(self.tmp_path),
            ):
                AppDelete(
                    load_stack(self.tmp_path), docker=MagicMock(), auth=auth
                ).run("web")
        auth.remove.assert_called_once_with("web", remove_files=True)
