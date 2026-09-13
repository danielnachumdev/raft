"""CLI argument parsing and command dispatch."""

from __future__ import annotations

import logging
import runpy
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .base import RaftTestCase, make_app, make_git_app, make_stack, write_demo_inventory
from raft import cli


class TestCli(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _cli_setup(self, _raft_base) -> None:
        write_demo_inventory(self.tmp_path)
        self.stack = make_stack(
            self.tmp_path,
            (
                make_app("app"),
                make_app("other"),
            ),
        )
        self.orch = MagicMock()

    def _run_main(self, argv: list[str]) -> int:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator", return_value=self.orch):
                return cli.main(argv)

    def _run_cli(self, argv: list[str]) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator", return_value=self.orch):
                cli.run(argv)

    def test_help_exits_zero(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(SystemExit) as exc:
                cli.main(["--help"])
        assert exc.value.code == 0

    def test_doctor_dispatches(self) -> None:
        doctor = MagicMock()
        doctor.report.return_value = 0
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Doctor", return_value=doctor):
                assert cli.main(["doctor"]) == 0
        doctor.report.assert_called_once()

    def test_sync_dispatches_all(self) -> None:
        assert self._run_main(["sync"]) == 0
        self.orch.sync.assert_called_once_with(None, ref_override=None, force=False)

    def test_sync_dispatches_subset_and_flags(self) -> None:
        assert self._run_main(["sync", "app", "--ref", "abc", "--force"]) == 0
        self.orch.sync.assert_called_once_with(
            ["app"], ref_override="abc", force=True
        )

    def test_sync_unknown_service(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(SystemExit):
                cli.main(["sync", "nope"])

    def test_up_down_dispatch(self) -> None:
        assert self._run_main(["up"]) == 0
        assert self._run_main(["down"]) == 0
        self.orch.start.assert_called_once()
        self.orch.stop.assert_called_once()

    def test_render_dispatch(self) -> None:
        assert self._run_main(["render"]) == 0
        self.orch.render.assert_called_once()

    def test_redeploy_app_dispatch(self) -> None:
        assert (
            self._run_main(["redeploy", "app", "--ref", "sha1", "--force-sync"]) == 0
        )
        self.orch.redeploy_app.assert_called_once_with(
            "app", ref_override="sha1", force_sync=True
        )

    def test_redeploy_router_dispatch(self) -> None:
        assert self._run_main(["redeploy", "router"]) == 0
        self.orch.redeploy_router.assert_called_once()

    def test_redeploy_gate_not_in_choices(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(SystemExit):
                cli.main(["redeploy", "gate"])

    def test_run_success_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["down"])
        assert exc.value.code == 0

    def test_run_maps_runtime_error(self, capsys) -> None:
        self.orch.start.side_effect = RuntimeError("already running")
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["up"])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "already running" in err
        assert "raft doctor" in err

    def test_run_called_process_error_suggests_doctor(self, capsys) -> None:
        err = subprocess.CalledProcessError(9, ["docker", "compose"], stderr="boom\n")
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["down"])
        assert exc.value.code == 9
        out = capsys.readouterr().err
        assert "boom" in out
        assert "raft doctor" in out

    def test_doctor_failure_does_not_suggest_doctor(self, capsys) -> None:
        doctor = MagicMock()
        doctor.report.return_value = 1
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Doctor", return_value=doctor):
                with pytest.raises(SystemExit) as exc:
                    cli.run(["doctor"])
        assert exc.value.code == 1
        assert "Hint:" not in capsys.readouterr().err

    def test_suggest_doctor_skips_when_already_running_doctor(self, capsys) -> None:
        cli._suggest_doctor(["doctor"])
        assert capsys.readouterr().err == ""

    def test_run_skips_bootstrap_when_handlers_exist(self) -> None:
        root = logging.getLogger("raft")
        root.handlers.clear()
        existing = logging.NullHandler()
        root.addHandler(existing)
        root.setLevel(logging.INFO)
        try:
            before = list(root.handlers)
            cli._ensure_logging_bootstrap()
            assert root.handlers == before
            self.orch.start.side_effect = RuntimeError("already running")
            with pytest.raises(SystemExit) as exc:
                self._run_cli(["up"])
            assert exc.value.code == 1
        finally:
            root.handlers.clear()

    def test_ensure_logging_bootstrap_when_empty(self) -> None:
        root = logging.getLogger("raft")
        root.handlers.clear()
        try:
            cli._ensure_logging_bootstrap()
            assert root.handlers
            assert root.propagate is False
        finally:
            root.handlers.clear()

    def test_main_module_entry(self) -> None:
        # runpy before any import so __name__ == "__main__" is covered without a
        # RuntimeWarning (pre-import leaves raft.__main__ in sys.modules).
        with patch("raft.cli.run") as run:
            runpy.run_module("raft.__main__", run_name="__main__")
        run.assert_called_once_with()

        import raft.__main__ as main_mod

        assert main_mod.run is cli.run

    def test_run_maps_called_process_error(self) -> None:
        err = subprocess.CalledProcessError(
            9, ["docker", "compose"], stderr="boom\n"
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["down"])
        assert exc.value.code == 9

    def test_run_called_process_error_without_stderr(self) -> None:
        err = subprocess.CalledProcessError(3, ["git"], stderr=None)
        self.orch.sync.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["sync"])
        assert exc.value.code == 3


class TestCliAuth(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _cli_auth_setup(self, _raft_base) -> None:
        write_demo_inventory(self.tmp_path)
        self.stack = make_stack(
            self.tmp_path,
            (make_git_app("svc"),),
        )
        self.auth = MagicMock()
        self.auth.list_services.return_value = ["svc"]
        self.auth.key_path.return_value = Path("/tmp/key")
        self.auth.show_pubkey.return_value = "ssh-ed25519 AAAA"

    def _auth_main(self, argv: list[str]) -> int:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator"):
                with patch("raft.cli.deps.GitAuthManager", return_value=self.auth):
                    return cli.main(argv)

    def test_auth_setup_list_show_test_remove(self, capsys) -> None:
        assert self._auth_main(["auth", "setup", "svc", "--force"]) == 0
        self.auth.setup.assert_called_once_with("svc", force=True)
        assert self._auth_main(["auth", "list"]) == 0
        assert self._auth_main(["auth", "show", "svc"]) == 0
        self.auth.show.assert_called_once_with("svc")
        assert self._auth_main(["auth", "test", "svc"]) == 0
        assert self._auth_main(["auth", "remove", "svc", "--keep-key"]) == 0
        self.auth.remove.assert_called_once_with("svc", remove_files=False)

    def test_auth_list_empty(self, capsys) -> None:
        self.auth.list_services.return_value = []
        assert self._auth_main(["auth", "list"]) == 0
        assert "No local raft deploy keys" in capsys.readouterr().out

    def test_auth_list_marks_unknown_inventory(self, capsys) -> None:
        self.auth.list_services.return_value = ["ghost"]
        self.auth.key_path.return_value = Path("/tmp/ghost")
        assert self._auth_main(["auth", "list"]) == 0
        assert "not applied" in capsys.readouterr().out


class TestCliApplyGetDelete(RaftTestCase):
    def test_apply_get_delete_dispatch(self, capsys) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(
            self.tmp_path,
            (make_app("app"), make_app("other")),
        )
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        applier.apply_git.return_value = "hub"
        with patch("raft.cli.deps.load_stack", return_value=stack):
            with patch("raft.cli.deps.AppApply", return_value=applier):
                assert cli.main(["apply", "--file", "app.yaml", "--no-deploy"]) == 0
                applier.apply_file.assert_called_once()
                assert (
                    cli.main(
                        [
                            "apply",
                            "--git",
                            "git@github.com:org/hub.git",
                            "--ref",
                            "main",
                            "--force-sync",
                        ]
                    )
                    == 0
                )
                applier.apply_git.assert_called_once()
                with pytest.raises(SystemExit):
                    cli.main(["apply"])

        empty = make_stack(self.tmp_path, ())
        with patch("raft.cli.deps.load_stack", return_value=empty):
            assert cli.main(["get", "apps"]) == 0
            assert "No apps applied" in capsys.readouterr().out

        with patch("raft.cli.deps.load_stack", return_value=stack):
            assert cli.main(["get", "apps"]) == 0
            out = capsys.readouterr().out
            assert "app" in out
            assert cli.main(["get", "app", "app"]) == 0
            with pytest.raises(SystemExit):
                cli.main(["get", "app"])
            with pytest.raises(SystemExit):
                cli.main(["get", "nope"])
            with patch("raft.cli.deps.AppApply", return_value=applier):
                assert cli.main(["delete", "app", "app"]) == 0
                applier.delete.assert_called_once_with("app")
                with pytest.raises(SystemExit):
                    cli.main(["delete", "app"])
                with pytest.raises(SystemExit):
                    cli.main(["delete", "nope"])
