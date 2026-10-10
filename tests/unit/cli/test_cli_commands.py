"""CLI RaftCLICommands coverage: dispatch, apply, get, delete."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.cli import RaftCLI

from ..base import make_app, make_stack, write_demo_inventory
from .base import CliTestCase


class TestCliApplyGetDelete(CliTestCase):
    def test_apply_merges_env_file_and_flags_into_single_env_map(self) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"),))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        env_path = self.tmp_path / "vars.env"
        env_path.write_text("FROM_FILE=yes\nA=from-file\n", encoding="utf-8")
        argv = self._merged_env_argv(env_path)
        with self.patched_deps(stack=stack, AppApply=applier):
            exit_code = RaftCLI()._invoke_fire(argv)
        self._assert_merged_env(applier, exit_code)

    @staticmethod
    def _merged_env_argv(env_path) -> list:
        return [
            "apply",
            "--file",
            "app.yaml",
            "--no-deploy",
            "--env-file",
            str(env_path),
            "--env",
            "A=1",
            "--env",
            "B=2",
        ]

    def _assert_merged_env(self, applier, exit_code) -> None:
        call_kwargs = applier.apply_file.call_args.kwargs
        apply_env = call_kwargs["env"]
        assert exit_code == 0
        assert "env_file" not in call_kwargs and "env_overrides" not in call_kwargs
        assert apply_env["FROM_FILE"] == "yes"
        assert apply_env["A"] == "1" and apply_env["B"] == "2"

    def test_apply_without_env_flags_still_passes_process_env_map(self) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"),))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        with self.patched_deps(stack=stack, AppApply=applier):
            exit_code = RaftCLI()._invoke_fire(["apply", "--file", "app.yaml", "--no-deploy"])
        call_kwargs = applier.apply_file.call_args.kwargs
        assert exit_code == 0 and isinstance(call_kwargs["env"], dict)
        assert "env_file" not in call_kwargs and "env_overrides" not in call_kwargs

    def test_apply_get_delete_dispatch(self, capsys) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"), make_app("other")))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        applier.apply_git.return_value = "hub"
        self._assert_apply_dispatch(stack, applier)
        self._assert_get_dispatch(stack, capsys)
        self._assert_delete_dispatch(stack, applier)

    def _assert_apply_dispatch(self, stack, applier) -> None:
        with self.patched_deps(stack=stack, AppApply=applier):
            assert RaftCLI()._invoke_fire(["apply", "--file", "app.yaml", "--no-deploy"]) == 0
            applier.apply_file.assert_called_once()
            assert (
                RaftCLI()._invoke_fire(
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
            with pytest.raises(RuntimeError, match="apply requires"):
                RaftCLI()._invoke_fire(["apply"])

    def _assert_get_dispatch(self, stack, capsys) -> None:
        empty = make_stack(self.tmp_path, ())
        with self.patched_deps(stack=empty):
            assert RaftCLI()._invoke_fire(["get", "apps"]) == 0
            assert "No apps applied" in capsys.readouterr().out
        with self.patched_deps(stack=stack):
            assert RaftCLI()._invoke_fire(["get", "apps"]) == 0
            assert "app" in capsys.readouterr().out
            assert RaftCLI()._invoke_fire(["get", "app", "app"]) == 0
            with pytest.raises(SystemExit):
                RaftCLI()._invoke_fire(["get", "app"])
            with pytest.raises(SystemExit):
                RaftCLI()._invoke_fire(["get", "nope"])

    def _assert_delete_dispatch(self, stack, applier) -> None:
        with self.patched_deps(stack=stack, AppApply=applier):
            assert RaftCLI()._invoke_fire(["delete", "app", "app"]) == 0
            applier.delete.assert_called_once_with("app")
            with pytest.raises(SystemExit):
                RaftCLI()._invoke_fire(["delete", "app"])
            with pytest.raises(SystemExit):
                RaftCLI()._invoke_fire(["delete", "nope"])


class TestCliDispatch(CliTestCase):
    def test_help_exits_zero(self) -> None:
        with self.patched_deps():
            with pytest.raises(SystemExit) as exc:
                RaftCLI()._invoke_fire(["--help"])
        assert exc.value.code == 0

    def test_doctor_dispatches(self) -> None:
        doctor = MagicMock()
        doctor.report.return_value = 0
        with self.patched_deps(Doctor=doctor):
            assert RaftCLI()._invoke_fire(["doctor"]) == 0
        doctor.report.assert_called_once()

    def test_status_dispatches(self) -> None:
        status = MagicMock()
        status.report.return_value = 0
        with self.patched_deps(Status=status) as deps:
            assert RaftCLI()._invoke_fire(["status"]) == 0
            assert RaftCLI()._invoke_fire(["status", "--json"]) == 0
            assert RaftCLI()._invoke_fire(["status", "--live"]) == 0
        deps["Status"].assert_called_with(self.stack)
        assert status.report.call_args_list[0].kwargs == {
            "as_json": False,
            "live": False,
        }
        assert status.report.call_args_list[1].kwargs == {
            "as_json": True,
            "live": False,
        }
        assert status.report.call_args_list[2].kwargs == {
            "as_json": False,
            "live": True,
        }

    def test_serve_dispatches_default_and_port(self) -> None:
        serve = MagicMock()
        with self.patched_deps(Serve=serve) as deps:
            assert RaftCLI()._invoke_fire(["serve"]) == 0
            assert RaftCLI()._invoke_fire(["serve", "--port", "9001"]) == 0
        deps["Serve"].assert_called_with(self.stack)
        assert serve.run.call_args_list[0].kwargs == {"port": 8787}
        assert serve.run.call_args_list[1].kwargs == {"port": 9001}

    def test_serve_dispatches_stop(self) -> None:
        serve = MagicMock()
        with self.patched_deps(Serve=serve) as deps:
            assert RaftCLI()._invoke_fire(["serve", "--stop"]) == 0
            assert RaftCLI()._invoke_fire(["serve", "--stop", "--port", "9001"]) == 0
        deps["Serve"].assert_called_with(self.stack)
        serve.run.assert_not_called()
        assert serve.stop.call_args_list[0].kwargs == {"port": 8787}
        assert serve.stop.call_args_list[1].kwargs == {"port": 9001}

    def test_logs_dispatches_snapshot_and_follow(self) -> None:
        logs = MagicMock()
        with self.patched_deps(Logs=logs) as deps:
            assert RaftCLI()._invoke_fire(["logs", "app", "--tail", "20"]) == 0
            assert RaftCLI()._invoke_fire(["logs", "gate", "--follow"]) == 0
            assert RaftCLI()._invoke_fire(["logs", "-f", "router"]) == 0
        deps["Logs"].assert_called_with(self.stack)
        assert logs.show.call_args_list[0].args == ("app",)
        assert logs.show.call_args_list[0].kwargs == {"tail": 20, "follow": False}
        assert logs.show.call_args_list[1].args == ("gate",)
        assert logs.show.call_args_list[1].kwargs == {"tail": 100, "follow": True}
        assert logs.show.call_args_list[2].args == ("router",)
        assert logs.show.call_args_list[2].kwargs["follow"] is True

    def test_status_unknown_flag_fails_before_report(self, capsys) -> None:
        status = MagicMock()
        with self.patched_deps(Status=status):
            with pytest.raises(SystemExit) as exc:
                RaftCLI()._invoke_fire(["status", "--leiv"])
        assert exc.value.code == 2
        status.report.assert_not_called()
        assert "Could not consume arg: --leiv" in capsys.readouterr().err

    def test_up_unknown_flag_fails_before_start(self, capsys) -> None:
        with self.patched_deps(Orchestrator=self.orch):
            with pytest.raises(SystemExit) as exc:
                RaftCLI()._invoke_fire(["up", "--bogus"])
        assert exc.value.code == 2
        self.orch.start.assert_not_called()
        assert "Could not consume arg: --bogus" in capsys.readouterr().err

    def test_purge_dispatches(self) -> None:
        purger = MagicMock()
        with self.patched_deps(Purge=purger) as deps:
            assert RaftCLI()._invoke_fire(["purge"]) == 0
        deps["Purge"].assert_called_once_with(self.stack)
        purger.run.assert_called_once()

    def test_update_dispatches(self) -> None:
        updater = MagicMock()
        with self.patched_deps(SelfUpdate=updater) as deps:
            assert RaftCLI()._invoke_fire(["update"]) == 0
        deps["SelfUpdate"].assert_called_once_with(self.stack)
        updater.run.assert_called_once()

    def test_uninstall_dispatches(self) -> None:
        uninstaller = MagicMock()
        with self.patched_deps(Uninstall=uninstaller) as deps:
            assert RaftCLI()._invoke_fire(["uninstall", "--yes"]) == 0
        deps["Uninstall"].assert_called_once_with(self.stack)
        uninstaller.run.assert_called_once_with(yes=True, uv=False)

    def test_uninstall_dispatches_with_uv(self) -> None:
        uninstaller = MagicMock()
        with self.patched_deps(Uninstall=uninstaller) as deps:
            assert RaftCLI()._invoke_fire(["uninstall", "--yes", "--uv"]) == 0
        deps["Uninstall"].assert_called_once_with(self.stack)
        uninstaller.run.assert_called_once_with(yes=True, uv=True)

    def test_sync_dispatches_all(self) -> None:
        assert self.run_main(["sync"]) == 0
        self.orch.sync.assert_called_once_with(None, ref_override=None, force=False)

    def test_sync_dispatches_subset_and_flags(self) -> None:
        assert self.run_main(["sync", "app", "--ref", "abc", "--force"]) == 0
        self.orch.sync.assert_called_once_with(["app"], ref_override="abc", force=True)

    def test_sync_unknown_service(self) -> None:
        with self.patched_deps():
            with pytest.raises(RuntimeError, match="unknown service"):
                RaftCLI()._invoke_fire(["sync", "nope"])

    def test_up_down_dispatch(self) -> None:
        assert self.run_main(["up"]) == 0
        assert self.run_main(["down"]) == 0
        self.orch.start.assert_called_once()
        self.orch.stop.assert_called_once()

    def test_render_dispatch(self) -> None:
        assert self.run_main(["render"]) == 0
        self.orch.render.assert_called_once()

    def test_redeploy_app_dispatch(self) -> None:
        assert self.run_main(["redeploy", "app", "--ref", "sha1", "--force-sync"]) == 0
        self.orch.redeploy_app.assert_called_once_with("app", ref_override="sha1", force_sync=True)

    def test_redeploy_router_dispatch(self) -> None:
        assert self.run_main(["redeploy", "router"]) == 0
        self.orch.redeploy_router.assert_called_once()

    def test_redeploy_gate_not_in_choices(self) -> None:
        with self.patched_deps():
            with pytest.raises(RuntimeError, match="unknown app"):
                RaftCLI()._invoke_fire(["redeploy", "gate"])

    def test_redeploy_requires_app(self) -> None:
        with self.patched_deps():
            with pytest.raises(RuntimeError, match="redeploy requires APP"):
                RaftCLI()._invoke_fire(["redeploy"])

    def test_gate_recreate_dispatch(self) -> None:
        assert self.run_main(["gate", "recreate"]) == 0
        self.orch.recreate_gate.assert_called_once()
