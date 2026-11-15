"""Edge branches for ``AppDelete`` (compose/auth/tree/lock failures)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.models.stack import Stack, load_stack
from raft.core.lifecycle.apply import AppDelete

from tests.unit.base import AppliedInventory
from .base import ApplyTestCase


class TestAppDeleteEdges(ApplyTestCase):
    def test_compose_failure_warns_and_continues(self, capsys) -> None:
        self._seed_web()
        docker = MagicMock()
        docker.remove_service.side_effect = RuntimeError("compose down")
        self._run_delete(docker=docker, auth=self._auth_off())
        out = capsys.readouterr().out
        assert "could not remove Compose service web" in out
        assert "deleted web" in out

    def test_auth_remove_failure_warns(self, capsys) -> None:
        self._seed_web(scaffold=True)
        auth = MagicMock()
        auth.is_configured.return_value = True
        auth.remove.side_effect = RuntimeError("key busy")
        self._run_delete(docker=MagicMock(), auth=auth)
        assert "local deploy key for web not removed" in capsys.readouterr().out

    def test_yaml_present_but_not_in_stack_still_deletes(self) -> None:
        path = self._write_orphan_yaml("ghost")
        stack = Stack(root=self.tmp_path, apps=())
        docker = MagicMock()
        with patch("raft.core.lifecycle.apply.delete.Orchestrator"):
            with patch(
                "raft.core.lifecycle.apply.delete.load_stack",
                return_value=stack,
            ):
                AppDelete(stack, docker=docker).run("ghost")
        docker.remove_service.assert_called_once_with("ghost")
        assert not path.exists()

    def test_rmtree_leaves_tree_warns(self, capsys) -> None:
        self._seed_web(scaffold=True)
        with patch("raft.core.lifecycle.apply.delete.shutil.rmtree"):
            self._run_delete(docker=MagicMock(), auth=self._auth_off())
        assert "could not fully remove" in capsys.readouterr().out

    def test_registry_delete_race_raises(self) -> None:
        self._seed_web()
        with patch(
            "raft.core.lifecycle.apply.delete.AppRegistry.delete",
            return_value=False,
        ):
            with pytest.raises(RuntimeError, match="not applied"):
                AppDelete(load_stack(self.tmp_path), docker=MagicMock()).run(
                    "web"
                )

    def test_default_docker_stack_and_announce_remaining(self, capsys) -> None:
        self._seed_web()
        AppliedInventory.write_applied_app(
            self.tmp_path, "other", public_host="other.test"
        )
        docker = MagicMock()
        with patch("raft.core.lifecycle.apply.delete.Orchestrator"):
            with patch(
                "raft.core.lifecycle.apply.delete.DockerStack",
                return_value=docker,
            ) as docker_cls:
                AppDelete(load_stack(self.tmp_path)).run("web")
        docker_cls.assert_called_once()
        docker.remove_service.assert_called_once_with("web")
        assert "after deleting web" in capsys.readouterr().out

    def test_default_auth_manager_when_configured(self) -> None:
        self._seed_web(scaffold=True)
        auth = MagicMock()
        auth.is_configured.return_value = True
        with patch(
            "raft.core.lifecycle.apply.delete.GitAuthManager",
            return_value=auth,
        ):
            with patch("raft.core.lifecycle.apply.delete.Orchestrator"):
                with patch(
                    "raft.core.lifecycle.apply.delete.load_stack",
                    return_value=load_stack(self.tmp_path),
                ):
                    AppDelete(
                        load_stack(self.tmp_path), docker=MagicMock()
                    ).run("web")
        auth.remove.assert_called_once_with("web", remove_files=True)

    def test_unlink_oserror_is_swallowed(self) -> None:
        with patch.object(Path, "unlink", side_effect=OSError("busy")):
            AppDelete._unlink(self.tmp_path / "missing.lock")

    def test_missing_durable_tree_is_noop(self) -> None:
        AppDelete(
            load_stack(self.tmp_path), docker=MagicMock()
        )._remove_durable_tree("no-such")

    def _seed_web(self, *, scaffold: bool = False) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "web", public_host="web.test"
        )
        if scaffold:
            ServicePaths(self.tmp_path, "web").ensure_scaffold()

    @staticmethod
    def _auth_off() -> MagicMock:
        auth = MagicMock()
        auth.is_configured.return_value = False
        return auth

    def _write_orphan_yaml(self, name: str) -> Path:
        path = ServicePaths(self.tmp_path, name).app_yaml()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": name},
                    "spec": {
                        "source": "local",
                        "path": f"services/{name}/checkout",
                        "ports": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def _run_delete(self, *, docker: MagicMock, auth: MagicMock) -> None:
        with patch("raft.core.lifecycle.apply.delete.Orchestrator"):
            with patch(
                "raft.core.lifecycle.apply.delete.load_stack",
                return_value=load_stack(self.tmp_path),
            ):
                AppDelete(
                    load_stack(self.tmp_path), docker=docker, auth=auth
                ).run("web")
