"""Controller process (prereq smoke + idle)."""

from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.paths import ensure_raft_home
from raft.controller import main, run_prereq_smoke
from raft.controller.run import main as main_impl
from raft.controller.smoke import run_prereq_smoke as smoke_impl


class TestControllerPrereq:
    def test_public_exports(self) -> None:
        assert main is main_impl
        assert run_prereq_smoke is smoke_impl

    def test_run_prereq_smoke_ok(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        sh = MagicMock()
        version = MagicMock(returncode=0, stdout="27.3.1\n", stderr="")
        compose = MagicMock(returncode=0, stdout="Docker Compose version v2.29.7\n")
        sh.docker.return_value = version
        sh.compose.return_value = compose

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

    def test_main_smokes_then_idles(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAFT_DATA_HOME", str(tmp_path / "home"))
        with patch("raft.controller.run.run_prereq_smoke") as smoke:
            with patch("raft.controller.run.time.sleep", side_effect=StopIteration):
                with pytest.raises(StopIteration):
                    main()
        smoke.assert_called_once()
        home_arg, sh_arg = smoke.call_args.args
        assert home_arg == (tmp_path / "home").resolve()
        assert sh_arg.cwd == home_arg

    def test_module_entrypoint(self) -> None:
        with patch("raft.controller.run.main", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                runpy.run_module("raft.controller", run_name="__main__")

    def test_main_module_import_does_not_run(self) -> None:
        import raft.controller.__main__ as controller_main

        assert controller_main.main is main
