"""CLI command dispatch coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft import cli

from .base import CliTestCase


class TestCliDispatch(CliTestCase):
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

    def test_status_dispatches(self) -> None:
        status = MagicMock()
        status.report.return_value = 0
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Status", return_value=status) as ctor:
                assert cli.main(["status"]) == 0
                assert cli.main(["status", "--json"]) == 0
                assert cli.main(["status", "--live"]) == 0
        ctor.assert_called_with(self.stack)
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

    def test_status_unknown_flag_fails_before_report(self, capsys) -> None:
        status = MagicMock()
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Status", return_value=status):
                with pytest.raises(SystemExit) as exc:
                    cli.main(["status", "--leiv"])
        assert exc.value.code == 2
        status.report.assert_not_called()
        assert "Could not consume arg: --leiv" in capsys.readouterr().err

    def test_up_unknown_flag_fails_before_start(self, capsys) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator", return_value=self.orch):
                with pytest.raises(SystemExit) as exc:
                    cli.main(["up", "--bogus"])
        assert exc.value.code == 2
        self.orch.start.assert_not_called()
        assert "Could not consume arg: --bogus" in capsys.readouterr().err

    def test_update_dispatches(self) -> None:
        updater = MagicMock()
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.SelfUpdate", return_value=updater) as ctor:
                assert cli.main(["update"]) == 0
        ctor.assert_called_once_with(self.stack)
        updater.run.assert_called_once()

    def test_uninstall_dispatches(self) -> None:
        uninstaller = MagicMock()
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Uninstall", return_value=uninstaller) as ctor:
                assert cli.main(["uninstall", "--yes"]) == 0
        ctor.assert_called_once_with(self.stack)
        uninstaller.run.assert_called_once_with(yes=True, uv=False)

    def test_uninstall_dispatches_with_uv(self) -> None:
        uninstaller = MagicMock()
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Uninstall", return_value=uninstaller) as ctor:
                assert cli.main(["uninstall", "--yes", "--uv"]) == 0
        ctor.assert_called_once_with(self.stack)
        uninstaller.run.assert_called_once_with(yes=True, uv=True)

    def test_sync_dispatches_all(self) -> None:
        assert self.run_main(["sync"]) == 0
        self.orch.sync.assert_called_once_with(None, ref_override=None, force=False)

    def test_sync_dispatches_subset_and_flags(self) -> None:
        assert self.run_main(["sync", "app", "--ref", "abc", "--force"]) == 0
        self.orch.sync.assert_called_once_with(["app"], ref_override="abc", force=True)

    def test_sync_unknown_service(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(RuntimeError, match="unknown service"):
                cli.main(["sync", "nope"])

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
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(RuntimeError, match="unknown app"):
                cli.main(["redeploy", "gate"])

    def test_redeploy_requires_app(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(RuntimeError, match="redeploy requires APP"):
                cli.main(["redeploy"])

    def test_gate_recreate_dispatch(self) -> None:
        assert self.run_main(["gate", "recreate"]) == 0
        self.orch.recreate_gate.assert_called_once()

