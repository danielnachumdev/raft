"""Docker/compose command error classifiers, messages, and run_* helpers."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from raft.errors import (
    OperatorError,
    compose_failure_message,
    docker_daemon_message,
    docker_pull_failure_message,
    looks_like_docker_daemon_down,
    looks_like_image_missing,
    looks_like_port_in_use,
    port_in_use_message,
    raise_for_compose_failure,
    raise_for_docker_pull_failure,
    run_checked,
    run_compose_checked,
    run_docker_checked,
)

from ...cta_asserts import assert_cta, assert_operator


class TestCommandErrors:
    def test_daemon_and_port_detection(self) -> None:
        self._assert_daemon_detection()
        self._assert_port_detection()

    def _assert_daemon_detection(self) -> None:
        daemon = subprocess.CalledProcessError(
            1, ["docker"], stderr="Cannot connect to the Docker daemon"
        )
        assert looks_like_docker_daemon_down(daemon)
        assert_cta(
            docker_daemon_message(detail="boom\nmore"),
            contains=("systemctl start docker", "raft doctor"),
            tag="docker",
        )
        assert_cta(docker_daemon_message(detail="   \n"), contains=("raft doctor",))

    def _assert_port_detection(self) -> None:
        port = subprocess.CalledProcessError(
            1, ["docker"], stderr="Bind for 0.0.0.0:80 failed: port is already allocated"
        )
        assert looks_like_port_in_use(port)
        assert_cta(
            port_in_use_message(detail="addr in use"),
            contains=("gate recreate", "raft doctor"),
            tag="docker",
        )
        assert_cta(port_in_use_message(detail=""), contains=("gate recreate",))

    def test_compose_messages_and_raise(self) -> None:
        self._test_compose_messages_and_raise_p1()
        self._test_compose_messages_and_raise_p2()

    def _test_compose_messages_and_raise_p1(self) -> None:
        msg = compose_failure_message("up", detail="oops\n", hint="check logs")
        assert_cta(msg, contains=("hint: check logs", "raft doctor"), tag="docker")
        assert "(docker: oops)" in msg
        with pytest.raises(OperatorError) as caught:
            raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1, ["docker", "compose"], stderr="is the docker daemon running?"
                ),
                action="up",
            )
        assert_operator(caught.value, contains=("systemctl start docker",))

    def _test_compose_messages_and_raise_p2(self) -> None:
        with pytest.raises(OperatorError) as caught:
            raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1, ["docker", "compose"], stderr="address already in use"
                ),
                action="up",
            )
        assert_operator(caught.value, contains=("gate recreate",))
        with pytest.raises(OperatorError) as caught:
            raise_for_compose_failure(RuntimeError("mystery"), action="up", hint="x")
        assert_operator(caught.value, contains=("raft doctor", "hint: x"))

    def test_run_compose_checked(self) -> None:
        shell = MagicMock()
        self._assert_compose_ok_and_port(shell)
        self._assert_compose_stream_paths(shell)

    def _assert_compose_ok_and_port(self, shell) -> None:
        shell.compose.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert run_compose_checked(shell, ("ps",), action="ps").returncode == 0
        shell.compose.return_value = MagicMock(
            returncode=1, stdout="", stderr="port is already allocated"
        )
        with pytest.raises(OperatorError) as caught:
            run_compose_checked(shell, ("up", "-d"), action="up")
        assert_operator(caught.value, contains=("gate recreate",))

    def _assert_compose_stream_paths(self, shell) -> None:
        shell.compose.reset_mock()
        shell.compose.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert run_compose_checked(
            shell, ("up", "-d"), action="up", stream=True
        ).returncode == 0
        shell.compose.assert_called_with("up", "-d", capture=False, check=False)
        shell.compose.return_value = MagicMock(returncode=1, stdout="", stderr="")
        with pytest.raises(OperatorError) as caught:
            run_compose_checked(shell, ("down",), action="down", stream=True)
        assert_operator(caught.value, contains=("raft doctor",))

    def test_image_missing_and_pull(self) -> None:
        self._assert_pull_messages()
        self._assert_pull_raises()

    def _assert_pull_messages(self) -> None:
        assert looks_like_image_missing(
            subprocess.CalledProcessError(1, ["docker"], stderr="manifest unknown")
        )
        assert_cta(
            docker_pull_failure_message("img", detail="fail\n", app="web"),
            contains=("raft sync web", "raft doctor"),
            tag="docker",
        )
        assert_cta(
            docker_pull_failure_message("img", detail="  \n"),
            contains=("docker login", "raft doctor"),
        )

    def _assert_pull_raises(self) -> None:
        with pytest.raises(OperatorError) as caught:
            raise_for_docker_pull_failure(
                "img", detail="unauthorized: authentication required"
            )
        assert_operator(
            caught.value,
            contains=("docker login",),
            fix_label="Fix (as the raft user):",
        )
        with pytest.raises(OperatorError) as caught:
            raise_for_docker_pull_failure(
                "img",
                detail="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            )
        assert_operator(caught.value, contains=("systemctl start docker",))
        with pytest.raises(OperatorError) as caught:
            raise_for_docker_pull_failure("img", detail="no such host")
        assert_operator(caught.value, contains=("raft sync",))

    def test_run_docker_checked(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(returncode=0, stdout="x", stderr="")
        assert run_docker_checked(shell, ("ps",), action="ps").stdout == "x"
        self._assert_docker_daemon_error(shell)
        self._assert_docker_hint_and_empty(shell)

    def _assert_docker_daemon_error(self, shell) -> None:
        shell.docker.return_value = MagicMock(
            returncode=1, stdout="", stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(OperatorError) as caught:
            run_docker_checked(shell, ("ps",), action="ps")
        assert_operator(caught.value, contains=("systemctl start docker",))

    def _assert_docker_hint_and_empty(self, shell) -> None:
        shell.docker.return_value = MagicMock(
            returncode=1, stdout="", stderr="something broke\nmore"
        )
        with pytest.raises(OperatorError) as caught:
            run_docker_checked(shell, ("run", "x"), action="run tmp", hint="retry")
        assert_operator(
            caught.value, contains=("hint: retry", "(docker: something broke)")
        )
        shell.docker.return_value = MagicMock(returncode=1, stdout="", stderr="   \n")
        with pytest.raises(OperatorError) as caught:
            run_docker_checked(shell, ("ps",), action="ps")
        assert_operator(caught.value, contains=("raft doctor",))

    def test_run_checked_dispatch(self) -> None:
        shell = MagicMock()
        shell.compose.return_value = MagicMock(returncode=0, stdout="", stderr="")
        shell.docker.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert run_checked(shell, ("ps",), kind="compose", action="ps").returncode == 0
        assert run_checked(shell, ("ps",), kind="docker", action="ps").stdout == "ok"
        with pytest.raises(ValueError, match="unsupported run_checked kind"):
            run_checked(shell, ("ps",), kind="git", action="ps")
