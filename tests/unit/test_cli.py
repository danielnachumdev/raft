"""CLI argument parsing and command dispatch."""

from __future__ import annotations

import importlib
import logging
import runpy
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft import cli

from .base import RaftTestCase, make_app, make_git_app, make_stack, write_applied_app, write_demo_inventory


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
        assert self._run_main(["sync"]) == 0
        self.orch.sync.assert_called_once_with(None, ref_override=None, force=False)

    def test_sync_dispatches_subset_and_flags(self) -> None:
        assert self._run_main(["sync", "app", "--ref", "abc", "--force"]) == 0
        self.orch.sync.assert_called_once_with(["app"], ref_override="abc", force=True)

    def test_sync_unknown_service(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with pytest.raises(RuntimeError, match="unknown service"):
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
        assert self._run_main(["redeploy", "app", "--ref", "sha1", "--force-sync"]) == 0
        self.orch.redeploy_app.assert_called_once_with("app", ref_override="sha1", force_sync=True)

    def test_redeploy_router_dispatch(self) -> None:
        assert self._run_main(["redeploy", "router"]) == 0
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
        assert self._run_main(["gate", "recreate"]) == 0
        self.orch.recreate_gate.assert_called_once()

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
        err = subprocess.CalledProcessError(9, ["true"], stderr="boom\n")
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["down"])
        assert exc.value.code == 9
        out = capsys.readouterr().err
        assert "boom" in out
        assert "raft doctor" in out

    def test_run_rewrites_docker_daemon_and_port(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1, ["docker", "ps"], stderr="Cannot connect to the Docker daemon\n"
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit):
            self._run_cli(["down"])
        assert "Docker daemon" in capsys.readouterr().err

        err2 = subprocess.CalledProcessError(
            1, ["docker", "run"], stderr="port is already allocated\n"
        )
        self.orch.stop.side_effect = err2
        with pytest.raises(SystemExit):
            self._run_cli(["down"])
        assert "already in use" in capsys.readouterr().err

    def test_run_rewrites_compose_and_git_and_pull(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1, ["docker", "compose", "up"], stderr="explode\n"
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit):
            self._run_cli(["down"])
        assert "docker compose failed" in capsys.readouterr().err

        auth = subprocess.CalledProcessError(
            1,
            ["git", "ls-remote", "git@github.com:org/x.git"],
            stderr="Permission denied (publickey)\n",
        )
        self.orch.sync.side_effect = auth
        with pytest.raises(SystemExit):
            self._run_cli(["sync"])
        assert "git auth failed" in capsys.readouterr().err

        net = subprocess.CalledProcessError(
            1,
            ["git", "fetch"],
            stderr="Could not resolve host: github.com\n",
        )
        self.orch.sync.side_effect = net
        with pytest.raises(SystemExit):
            self._run_cli(["sync"])
        assert "cannot reach git host" in capsys.readouterr().err

        generic = subprocess.CalledProcessError(
            1, ["git", "status"], stderr="index.lock\n"
        )
        self.orch.sync.side_effect = generic
        with pytest.raises(SystemExit):
            self._run_cli(["sync"])
        assert "git command failed" in capsys.readouterr().err

        pull = subprocess.CalledProcessError(
            1, ["docker", "pull", "ghcr.io/x:y"], stderr="no such host\n"
        )
        self.orch.stop.side_effect = pull
        with pytest.raises(SystemExit):
            self._run_cli(["down"])
        assert "docker pull failed" in capsys.readouterr().err

    def test_run_maps_oserror_and_yaml(self, capsys) -> None:
        self.orch.start.side_effect = OSError("permission denied")
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["up"])
        assert exc.value.code == 1
        assert "filesystem error" in capsys.readouterr().err

        self.orch.start.side_effect = yaml.YAMLError("bad indent")
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["up"])
        assert exc.value.code == 1
        assert "invalid YAML" in capsys.readouterr().err

    def test_run_rewrites_missing_origin_cert_errors(self, capsys) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
        from raft.models.stack import load_stack

        stack = load_stack(self.tmp_path)
        err = subprocess.CalledProcessError(
            1,
            ["docker", "compose", "exec", "-T", "raft-gate", "nginx", "-t"],
            stderr=(
                'cannot load certificate "/etc/nginx/certs/web/origin.pem": '
                "BIO_new_file() failed (SSL: error:80000002:system library::No such file)\n"
            ),
        )
        self.orch.stop.side_effect = err
        with patch("raft.cli.entry.load_stack", return_value=stack):
            with pytest.raises(SystemExit) as exc:
                self._run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "Origin certs missing" in err_out
        assert "certs/web/" in err_out
        assert "command failed" not in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_rewrites_docker_pull_unauthorized(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1,
            ["docker", "pull", "ghcr.io/playloft-studio/playcrate:main"],
            stderr="Error response from daemon: unauthorized\nunauthorized\n",
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "cannot pull ghcr.io/playloft-studio/playcrate:main" in err_out
        assert "docker login ghcr.io" in err_out
        assert "command failed" not in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_runtime_error_with_fix_skips_doctor_hint(self, capsys) -> None:
        self.orch.start.side_effect = RuntimeError(
            "cannot pull img: registry unauthorized.\n\nfix (as the raft user):\n  1. login"
        )
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["up"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "cannot pull img" in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_operator_error_handler(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["sync", "nope"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "unknown service(s)" in err_out
        assert "Fix: raft get apps" in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_cert_error_fallback_when_stack_load_fails(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1,
            ["docker", "compose", "exec", "-T", "raft-gate", "nginx", "-t"],
            stderr='cannot load certificate "/etc/nginx/certs/web/origin.pem"\n',
        )
        self.orch.stop.side_effect = err
        with patch("raft.cli.entry.load_stack", side_effect=RuntimeError("no home")):
            with pytest.raises(SystemExit) as exc:
                self._run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "could not load Origin TLS certificates" in err_out
        assert "origin.pem" in err_out

    def test_run_cert_error_fallback_when_no_missing_listed(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1,
            ["docker", "compose", "exec", "-T", "raft-gate", "nginx", "-t"],
            stderr='cannot load certificate "/etc/nginx/certs/web/origin.pem"\n',
        )
        self.orch.stop.side_effect = err
        with patch("raft.cli.entry.load_stack", return_value=self.stack):
            with patch("raft.cli.entry.missing_origin_certs", return_value=[]):
                with pytest.raises(SystemExit) as exc:
                    self._run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "could not load Origin TLS certificates" in err_out

    def test_run_cert_error_fallback_without_detail(self, capsys) -> None:
        # Match via argv text so stderr can be empty (covers detail-absent branch).
        err = subprocess.CalledProcessError(
            1,
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "gate",
                "nginx",
                "-t",
                'cannot load certificate "/etc/nginx/certs/web/origin.pem"',
            ],
            stderr="",
        )
        self.orch.stop.side_effect = err
        with patch("raft.cli.entry.load_stack", return_value=self.stack):
            with patch("raft.cli.entry.missing_origin_certs", return_value=[]):
                with pytest.raises(SystemExit) as exc:
                    self._run_cli(["down"])
        assert exc.value.code == 1
        assert "could not load Origin TLS certificates" in capsys.readouterr().err

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
        with patch("raft.cli.run") as run:
            runpy.run_module("raft.__main__", run_name="__main__")
        run.assert_called_once_with()

        main_mod = importlib.import_module("raft.__main__")
        assert main_mod.run is cli.run

    def test_run_maps_called_process_error(self) -> None:
        err = subprocess.CalledProcessError(9, ["docker", "compose"], stderr="boom\n")
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["down"])
        assert exc.value.code == 9

    def test_run_called_process_error_without_stderr(self) -> None:
        err = subprocess.CalledProcessError(3, ["true"], stderr=None)
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
        self.auth.setup.assert_called_once_with("svc", force=True, repo=None)
        assert self._auth_main(["auth", "list"]) == 0
        assert self._auth_main(["auth", "show", "svc"]) == 0
        self.auth.show.assert_called_once_with("svc", repo=None)
        assert (
            self._auth_main(
                [
                    "auth",
                    "setup",
                    "newsvc",
                    "--repo",
                    "git@github.com:org/new.git",
                ]
            )
            == 0
        )
        self.auth.setup.assert_called_with(
            "newsvc", force=False, repo="git@github.com:org/new.git"
        )
        assert self._auth_main(["auth", "test", "svc"]) == 0
        self.auth.test.assert_called_with("svc", repo=None)
        assert self._auth_main(["auth", "remove", "svc", "--keep-key"]) == 0
        self.auth.remove.assert_called_once_with("svc", remove_files=False)

    def test_auth_requires_service(self) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator"):
                with patch("raft.cli.deps.GitAuthManager", return_value=self.auth):
                    with pytest.raises(RuntimeError, match="auth setup requires SERVICE"):
                        cli.main(["auth", "setup"])
                    with pytest.raises(RuntimeError, match="auth show requires SERVICE"):
                        cli.main(["auth", "show"])
                    with pytest.raises(RuntimeError, match="auth test requires SERVICE"):
                        cli.main(["auth", "test"])
                    with pytest.raises(RuntimeError, match="auth remove requires SERVICE"):
                        cli.main(["auth", "remove"])

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
    def test_apply_passes_env_file_and_env_overrides_to_apply_file(self) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"),))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        argv = [
            "apply",
            "--file",
            "app.yaml",
            "--no-deploy",
            "--env-file",
            "vars.env",
            "--env",
            "A=1",
            "--env",
            "B=2",
        ]

        with patch("raft.cli.deps.load_stack", return_value=stack):
            with patch("raft.cli.deps.AppApply", return_value=applier):
                exit_code = cli.main(argv)

        call_kwargs = applier.apply_file.call_args.kwargs
        assert exit_code == 0
        assert call_kwargs["env_file"] == Path("vars.env")
        # Fire may pass repeated --env as a tuple/list.
        assert list(call_kwargs["env_overrides"]) == ["A=1", "B=2"]

    def test_apply_without_env_flags_passes_none(self) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"),))
        applier = MagicMock()
        applier.apply_file.return_value = "web"

        with patch("raft.cli.deps.load_stack", return_value=stack):
            with patch("raft.cli.deps.AppApply", return_value=applier):
                exit_code = cli.main(["apply", "--file", "app.yaml", "--no-deploy"])

        call_kwargs = applier.apply_file.call_args.kwargs
        assert exit_code == 0
        assert call_kwargs.get("env_file") is None
        assert call_kwargs.get("env_overrides") is None

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
                with pytest.raises(RuntimeError, match="apply requires"):
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
