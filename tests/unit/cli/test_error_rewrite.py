"""CLI error rewriting coverage."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
import yaml

from raft.models.stack import load_stack

from ..base import write_applied_app
from .base import CliTestCase


class TestCliErrorRewrite(CliTestCase):
    def test_run_success_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 0

    def test_run_maps_runtime_error(self, capsys) -> None:
        self.orch.start.side_effect = RuntimeError("already running")
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["up"])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "already running" in err
        assert "raft doctor" in err

    def test_run_called_process_error_suggests_doctor(self, capsys) -> None:
        err = subprocess.CalledProcessError(9, ["true"], stderr="boom\n")
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 9
        out = capsys.readouterr().err
        assert "boom" in out
        assert "raft doctor" in out

    def test_run_rewrites_docker_daemon_and_port(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1, ["docker", "ps"], stderr="Cannot connect to the Docker daemon\n"
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 1
        assert "systemctl start docker" in capsys.readouterr().err

        err2 = subprocess.CalledProcessError(
            1, ["docker", "run"], stderr="port is already allocated\n"
        )
        self.orch.stop.side_effect = err2
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 1
        assert "gate recreate" in capsys.readouterr().err

    def test_run_rewrites_compose_and_git_and_pull(self, capsys) -> None:
        self._assert_compose_fail(capsys)
        self._assert_git_auth(capsys)
        self._assert_git_net_and_generic(capsys)
        self._assert_pull_fail(capsys)

    def _assert_compose_fail(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1, ["docker", "compose", "up"], stderr="explode\n"
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 1
        assert "raft doctor" in capsys.readouterr().err

    def _assert_git_auth(self, capsys) -> None:
        auth = subprocess.CalledProcessError(
            1, ["git", "ls-remote", "git@github.com:org/x.git"],
            stderr="Permission denied (publickey)\n",
        )
        self.orch.sync.side_effect = auth
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["sync"])
        assert exc.value.code == 1
        assert "auth setup" in capsys.readouterr().err

    def _assert_git_net_and_generic(self, capsys) -> None:
        net = subprocess.CalledProcessError(
            1, ["git", "fetch"], stderr="Could not resolve host: github.com\n"
        )
        self.orch.sync.side_effect = net
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["sync"])
        assert exc.value.code == 1
        assert "auth test" in capsys.readouterr().err
        generic = subprocess.CalledProcessError(1, ["git", "status"], stderr="index.lock\n")
        self.orch.sync.side_effect = generic
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["sync"])
        assert exc.value.code == 1
        assert "auth test" in capsys.readouterr().err

    def _assert_pull_fail(self, capsys) -> None:
        pull = subprocess.CalledProcessError(
            1, ["docker", "pull", "ghcr.io/x:y"], stderr="no such host\n"
        )
        self.orch.stop.side_effect = pull
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "raft sync" in err or "docker login" in err

    def test_run_maps_oserror_and_yaml(self, capsys) -> None:
        self.orch.start.side_effect = OSError("read-only filesystem")
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["up"])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "chown" not in err

        self.orch.start.side_effect = OSError(13, "Permission denied")
        with pytest.raises(SystemExit):
            self.run_cli(["up"])
        err = capsys.readouterr().err
        assert "chown" in err

        self.orch.start.side_effect = yaml.YAMLError("bad indent")
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["up"])
        assert exc.value.code == 1
        assert "YAML" in capsys.readouterr().err

    def test_run_rewrites_missing_origin_cert_errors(self, capsys) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
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
                self.run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "certs/web/" in err_out
        assert "command failed" not in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_rewrites_docker_pull_unauthorized(self, capsys) -> None:
        err = subprocess.CalledProcessError(
            1,
            ["docker", "pull", "ghcr.io/example/app:main"],
            stderr="Error response from daemon: unauthorized\nunauthorized\n",
        )
        self.orch.stop.side_effect = err
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "ghcr.io/example/app:main" in err_out
        assert "docker login ghcr.io" in err_out
        assert "command failed" not in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_runtime_error_with_fix_skips_doctor_hint(self, capsys) -> None:
        self.orch.start.side_effect = RuntimeError(
            "cannot pull img: registry unauthorized.\n\nFix (as the raft user):\n  1. login"
        )
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["up"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "cannot pull img" in err_out
        assert "Hint: run `raft doctor`" not in err_out

    def test_run_operator_error_handler(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            self.run_cli(["sync", "nope"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
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
                self.run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
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
                    self.run_cli(["down"])
        assert exc.value.code == 1
        assert "origin.pem" in capsys.readouterr().err

    def test_run_cert_error_fallback_without_detail(self, capsys) -> None:
        # Match via argv text so stderr can be empty (covers detail-absent branch).
        err = subprocess.CalledProcessError(
            1,
            [
                "docker", "compose", "exec", "-T", "gate", "nginx", "-t",
                'cannot load certificate "/etc/nginx/certs/web/origin.pem"',
            ],
            stderr="",
        )
        self.orch.stop.side_effect = err
        with patch("raft.cli.entry.load_stack", return_value=self.stack):
            with patch("raft.cli.entry.missing_origin_certs", return_value=[]):
                with pytest.raises(SystemExit) as exc:
                    self.run_cli(["down"])
        assert exc.value.code == 1
        err_out = capsys.readouterr().err
        assert "origin.pem" in err_out or "Origin" in err_out
