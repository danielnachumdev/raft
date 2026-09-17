"""Unit tests for git/command error helpers and related validation CTAs."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raft.config.paths import raft_home
from raft.config.settings import load_config
from raft.models.ports import parse_ports
from raft.errors import (
    compose_failure_message,
    docker_daemon_message,
    docker_pull_failure_message,
    git_auth_failure_message,
    git_generic_failure_message,
    git_network_failure_message,
    looks_like_docker_daemon_down,
    looks_like_git_auth_failure,
    looks_like_git_network_failure,
    looks_like_image_missing,
    looks_like_port_in_use,
    port_in_use_message,
    raise_for_compose_failure,
    raise_for_docker_pull_failure,
    raise_for_git_failure,
    run_checked,
    run_compose_checked,
    run_docker_checked,
)
from raft.services.cutover import wait_until
from raft.services.update import SelfUpdate

from ..base import RaftTestCase, make_stack


class TestCommandErrors:
    def test_daemon_and_port_detection(self) -> None:
        daemon = subprocess.CalledProcessError(
            1, ["docker"], stderr="Cannot connect to the Docker daemon"
        )
        assert looks_like_docker_daemon_down(daemon)
        assert "systemctl start docker" in docker_daemon_message(detail="boom\nmore")
        assert "cannot talk" in docker_daemon_message(detail="   \n")

        port = subprocess.CalledProcessError(
            1, ["docker"], stderr="Bind for 0.0.0.0:80 failed: port is already allocated"
        )
        assert looks_like_port_in_use(port)
        assert "gate recreate" in port_in_use_message(detail="addr in use")
        assert "already in use" in port_in_use_message(detail="")

    def test_compose_messages_and_raise(self) -> None:
        msg = compose_failure_message("up", detail="oops\n", hint="check logs")
        assert "hint: check logs" in msg
        assert "(docker: oops)" in msg
        assert "raft doctor" in compose_failure_message("up")

        with pytest.raises(RuntimeError, match="Docker daemon"):
            raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1, ["docker", "compose"], stderr="is the docker daemon running?"
                ),
                action="up",
            )
        with pytest.raises(RuntimeError, match="already in use"):
            raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1, ["docker", "compose"], stderr="address already in use"
                ),
                action="up",
            )
        with pytest.raises(RuntimeError, match="docker compose failed"):
            raise_for_compose_failure(RuntimeError("mystery"), action="up", hint="x")

    def test_run_compose_checked(self) -> None:
        shell = MagicMock()
        shell.compose.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert run_compose_checked(shell, ("ps",), action="ps").returncode == 0

        shell.compose.return_value = MagicMock(
            returncode=1, stdout="", stderr="port is already allocated"
        )
        with pytest.raises(RuntimeError, match="already in use"):
            run_compose_checked(shell, ("up", "-d"), action="up")

    def test_image_missing_and_pull(self) -> None:
        assert looks_like_image_missing(
            subprocess.CalledProcessError(1, ["docker"], stderr="manifest unknown")
        )
        assert "raft sync web" in docker_pull_failure_message(
            "img", detail="fail\n", app="web"
        )
        assert "docker pull failed" in docker_pull_failure_message("img", detail="  \n")

        with pytest.raises(RuntimeError, match="docker login"):
            raise_for_docker_pull_failure("img", detail="unauthorized: authentication required")
        with pytest.raises(RuntimeError, match="Docker daemon"):
            raise_for_docker_pull_failure(
                "img",
                detail="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            )
        with pytest.raises(RuntimeError, match="docker pull failed"):
            raise_for_docker_pull_failure("img", detail="no such host")

    def test_run_docker_checked(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(returncode=0, stdout="x", stderr="")
        assert run_docker_checked(shell, ("ps",), action="ps").stdout == "x"

        shell.docker.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon",
        )
        with pytest.raises(RuntimeError, match="Docker daemon"):
            run_docker_checked(shell, ("ps",), action="ps")

        shell.docker.return_value = MagicMock(
            returncode=1, stdout="", stderr="something broke\nmore"
        )
        with pytest.raises(RuntimeError, match="hint: retry") as exc:
            run_docker_checked(shell, ("run", "x"), action="run tmp", hint="retry")
        assert "(docker: something broke)" in str(exc.value)

        shell.docker.return_value = MagicMock(returncode=1, stdout="", stderr="   \n")
        with pytest.raises(RuntimeError, match="docker failed"):
            run_docker_checked(shell, ("ps",), action="ps")


class TestGitErrors:
    def test_classifiers_and_messages(self) -> None:
        auth = subprocess.CalledProcessError(
            1, ["git"], stderr="Permission denied (publickey)"
        )
        assert looks_like_git_auth_failure(auth)
        assert "auth setup" in git_auth_failure_message(
            "git@h:o/r.git", app="web", detail="nope\n"
        )
        assert "git auth failed" in git_auth_failure_message("r", detail="  ")
        assert "git auth failed" in git_auth_failure_message("r", detail="\n\n")

        net = RuntimeError("Could not resolve host: github.com")
        assert looks_like_git_network_failure(net)
        assert "cannot reach" in git_network_failure_message("r", detail="dns\nfail")
        assert "cannot reach" in git_network_failure_message("r", detail="")
        assert "cannot reach" in git_network_failure_message("r", detail="\n  \n")

        assert "auth test" in git_generic_failure_message("r", app="web", detail="x\n")
        assert "git command failed" in git_generic_failure_message("r", detail="  ")

    def test_raise_for_git_failure(self) -> None:
        with pytest.raises(RuntimeError, match="git auth failed"):
            raise_for_git_failure(
                subprocess.CalledProcessError(
                    1, ["git"], stderr="Could not read from remote repository"
                ),
                "git@h:o/r.git",
                app="web",
            )
        with pytest.raises(RuntimeError, match="cannot reach"):
            raise_for_git_failure(RuntimeError("connection timed out"), "r")
        raise_for_git_failure(RuntimeError("weird"), "r")  # no raise when always=False
        with pytest.raises(RuntimeError, match="git command failed"):
            raise_for_git_failure(RuntimeError("weird"), "r", always=True)


class TestValidationCTAs(RaftTestCase):
    def test_empty_raft_data_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_DATA_HOME", "   ")
        with pytest.raises(RuntimeError, match="empty"):
            raft_home()

    def test_settings_bad_ports_and_shapes(self) -> None:
        path = self.tmp_path / "settings.yaml"
        path.write_text("edge:\n  http: eighty\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="integer port"):
            load_config(self.tmp_path)

        path.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="YAML mapping"):
            load_config(self.tmp_path)

        path.write_text("logging:\n  level: NOPE\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="logging.level"):
            load_config(self.tmp_path)

        bad_dir = self.tmp_path / "settings-as-dir"
        bad_dir.mkdir()
        with pytest.raises(RuntimeError, match="not a file"):
            load_config(self.tmp_path, path=bad_dir)

        path.write_text("edge:\n  streams:\n    - {name: s, port: nope}\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="streams\\['s'\\].port"):
            load_config(self.tmp_path)

        path.write_text("{{{{invalid", encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid YAML"):
            load_config(self.tmp_path)

    def test_ports_require_int_and_bool(self) -> None:
        with pytest.raises(RuntimeError, match="containerPort must be an integer"):
            parse_ports(
                {"ports": [{"name": "http", "containerPort": "eighty", "expose": "http"}]},
                Path("app.yaml"),
            )
        with pytest.raises(RuntimeError, match="proxyProtocol must be a boolean"):
            parse_ports(
                {
                    "ports": [
                        {
                            "name": "s",
                            "containerPort": 25,
                            "expose": "stream",
                            "publicPort": 25,
                            "proxyProtocol": "yes",
                        }
                    ]
                },
                Path("app.yaml"),
            )

    def test_wait_until_fix_cta(self) -> None:
        with pytest.raises(RuntimeError, match="Fix: retry"):
            wait_until("never", lambda: False, timeout=0.05, interval=0.01, fix="retry")

    def test_update_failure_cta(self) -> None:
        stack = make_stack(self.tmp_path, ())
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("curl failed")
        with pytest.raises(RuntimeError, match="raft update failed"):
            SelfUpdate(stack, shell=shell).run()

    def test_settings_unreadable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        path = self.tmp_path / "settings.yaml"
        path.write_text("logging:\n  level: INFO\n", encoding="utf-8")
        monkeypatch.setattr(
            Path,
            "read_text",
            lambda self, *a, **k: (_ for _ in ()).throw(OSError("EACCES")),
        )
        with pytest.raises(RuntimeError, match="cannot read settings.yaml"):
            load_config(self.tmp_path)

    def test_run_checked_dispatch(self) -> None:
        shell = MagicMock()
        shell.compose.return_value = MagicMock(returncode=0, stdout="", stderr="")
        shell.docker.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert run_checked(shell, ("ps",), kind="compose", action="ps").returncode == 0
        assert run_checked(shell, ("ps",), kind="docker", action="ps").stdout == "ok"
        with pytest.raises(ValueError, match="unsupported run_checked kind"):
            run_checked(shell, ("ps",), kind="git", action="ps")

    def test_cta_helpers_and_validation(self) -> None:
        from raft.errors import (
            format_cta,
            operator,
            require_bool,
            require_mapping,
            subprocess_detail,
        )

        assert subprocess_detail(RuntimeError("plain")) == "plain"
        assert "plain detail" in format_cta("head", ("step",), detail="plain detail")
        err = operator("headline", ("do this",), detail="more")
        assert "headline" in str(err)
        assert err.has_fix is True
        assert require_bool(None, label="flag", default=True) is True
        assert require_mapping({"a": 1}, label="doc") == {"a": 1}
        with pytest.raises(RuntimeError, match="YAML mapping"):
            require_mapping([], label="doc", path="x.yaml")
