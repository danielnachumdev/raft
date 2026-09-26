"""CLI bootstrap, doctor-hint, and CPE coverage."""

from __future__ import annotations

import importlib
import logging
import runpy
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from raft import cli

from .base import CliTestCase


class TestCliBootstrap(CliTestCase):
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
                self.run_cli(["up"])
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
        with patch("raft.cli.run") as run:
            runpy.run_module("raft.__main__", run_name="__main__")
        run.assert_called_once_with()

        main_mod = importlib.import_module("raft.__main__")
        assert main_mod.run is cli.run

    def test_run_maps_called_process_error(self) -> None:
        err = subprocess.CalledProcessError(9, ["docker", "compose"], stderr="boom\n")
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 9

    def test_run_called_process_error_without_stderr(self) -> None:
        err = subprocess.CalledProcessError(3, ["true"], stderr=None)
        self.orch.sync.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["sync"])
        assert exc.value.code == 3
