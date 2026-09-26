"""Controller process (prereq smoke + idle)."""

from __future__ import annotations

import logging
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.paths import ensure_raft_home
from raft.config.settings_types import default_config
from raft.controller import main, run_prereq_smoke
from raft.controller.logging import setup_controller_logging
from raft.controller.run import main as main_impl
from raft.controller.smoke import run_prereq_smoke as smoke_impl
from raft.errors import OperatorError


class TestControllerPrereq:
    def test_public_exports(self) -> None:
        assert main is main_impl
        assert run_prereq_smoke is smoke_impl

    def test_setup_controller_logging_stdout_only(self) -> None:
        setup_controller_logging(default_config())
        root = logging.getLogger("raft")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_run_prereq_smoke_ok(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        sh = MagicMock()
        version = MagicMock(returncode=0, stdout="27.3.1\n", stderr="")
        compose = MagicMock(returncode=0, stdout="Docker Compose version v2.29.7\n")
        sh.docker.return_value = version
        sh.compose.return_value = compose

        with patch("raft.controller.smoke.AppRegistry") as registry_cls:
            registry_cls.return_value.load.return_value = ()
            run_prereq_smoke(home, sh)

        sh.docker.assert_called_once_with(
            "version", "--format", "{{.Server.Version}}", capture=True
        )
        sh.compose.assert_called_once_with("version", capture=True, check=False)

    def test_run_prereq_smoke_unknown_docker_version(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        sh = MagicMock()
        sh.docker.return_value = MagicMock(returncode=0, stdout="  \n")
        sh.compose.return_value = MagicMock(returncode=0, stdout="ok")

        run_prereq_smoke(home, sh)

    def test_run_prereq_smoke_compose_missing(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        sh = MagicMock()
        sh.docker.return_value = MagicMock(returncode=0, stdout="27.0.0\n")
        sh.compose.return_value = MagicMock(returncode=1, stdout="", stderr="missing")

        with pytest.raises(RuntimeError, match="docker compose plugin"):
            run_prereq_smoke(home, sh)

    def test_main_smokes_then_heals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("RAFT_DATA_HOME", str(home))
        with patch("raft.controller.run.run_prereq_smoke") as smoke:
            with patch("raft.controller.run.run_heal_forever", side_effect=StopIteration):
                with pytest.raises(StopIteration):
                    main()
        smoke.assert_called_once()

    def test_main_requires_data_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "nope"
        monkeypatch.setenv("RAFT_DATA_HOME", str(missing))
        with pytest.raises(OperatorError, match="data home missing"):
            main()

    def test_module_entrypoint(self) -> None:
        with patch("raft.controller.run.main", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                runpy.run_module("raft.controller", run_name="__main__")

    def test_main_module_import_does_not_run(self) -> None:
        import raft.controller.__main__ as controller_main

        assert controller_main.main is main
