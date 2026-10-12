"""Docker/compose command error classifiers, messages, and run_* helpers."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.errors.cta import CtaFormatter, OperatorError
from raft.core.core.errors.docker_msgs import DockerMessages

from tests.unit.cta_asserts import CtaAsserts


class TestCommandErrors:
    def test_daemon_and_port_detection(self) -> None:
        self._assert_daemon_detection()
        self._assert_port_detection()

    def _assert_daemon_detection(self) -> None:
        daemon = subprocess.CalledProcessError(
            1, ["docker"], stderr="Cannot connect to the Docker daemon"
        )
        assert DockerMessages.looks_like_docker_daemon_down(daemon)
        CtaAsserts.cta(
            DockerMessages.docker_daemon_message(detail="boom\nmore"),
            contains=("systemctl start docker", "raft doctor"),
            tag="docker",
        )
        CtaAsserts.cta(DockerMessages.docker_daemon_message(detail="   \n"), contains=("raft doctor",))

    def _assert_port_detection(self) -> None:
        port = subprocess.CalledProcessError(
            1, ["docker"], stderr="Bind for 0.0.0.0:80 failed: port is already allocated"
        )
        assert DockerMessages.looks_like_port_in_use(port)
        CtaAsserts.cta(
            DockerMessages.port_in_use_message(detail="addr in use"),
            contains=("gate recreate", "raft doctor"),
            tag="docker",
        )
        CtaAsserts.cta(DockerMessages.port_in_use_message(detail=""), contains=("gate recreate",))

    def test_compose_messages_and_raise(self) -> None:
        self._test_compose_messages_and_raise_p1()
        self._test_compose_messages_and_raise_p2()

    def _test_compose_messages_and_raise_p1(self) -> None:
        msg = DockerMessages.compose_failure_message("up", detail="oops\n", hint="check logs")
        CtaAsserts.cta(msg, contains=("hint: check logs", "raft doctor"), tag="docker")
        assert "(docker: oops)" in msg
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1, ["docker", "compose"], stderr="is the docker daemon running?"
                ),
                action="up",
            )
        CtaAsserts.operator(caught.value, contains=("systemctl start docker",))

    def _test_compose_messages_and_raise_p2(self) -> None:
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_compose_failure(
                subprocess.CalledProcessError(
                    1, ["docker", "compose"], stderr="address already in use"
                ),
                action="up",
            )
        CtaAsserts.operator(caught.value, contains=("gate recreate",))
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_compose_failure(RuntimeError("mystery"), action="up", hint="x")
        CtaAsserts.operator(caught.value, contains=("raft doctor", "hint: x"))

    def test_run_compose_checked(self) -> None:
        shell = MagicMock()
        self._assert_compose_ok_and_port(shell)
        self._assert_compose_stream_paths(shell)

    def _assert_compose_ok_and_port(self, shell) -> None:
        shell.compose.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert CheckedCommands.run_compose(shell, ("ps",), action="ps").returncode == 0
        shell.compose.return_value = MagicMock(
            returncode=1, stdout="", stderr="port is already allocated"
        )
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.run_compose(shell, ("up", "-d"), action="up")
        CtaAsserts.operator(caught.value, contains=("gate recreate",))

    def _assert_compose_stream_paths(self, shell) -> None:
        shell.compose.reset_mock()
        shell.compose.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert CheckedCommands.run_compose(shell, ("up", "-d"), action="up", stream=True).returncode == 0
        shell.compose.assert_called_with("up", "-d", capture=False, check=False)
        shell.compose.return_value = MagicMock(returncode=1, stdout="", stderr="")
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.run_compose(shell, ("down",), action="down", stream=True)
        CtaAsserts.operator(caught.value, contains=("raft doctor",))

    def test_image_missing_and_pull(self) -> None:
        self._assert_pull_messages()
        self._assert_pull_raises()

    def _assert_pull_messages(self) -> None:
        assert DockerMessages.looks_like_image_missing(
            subprocess.CalledProcessError(1, ["docker"], stderr="manifest unknown")
        )
        CtaAsserts.cta(
            DockerMessages.docker_pull_failure_message("img", detail="fail\n", app="web"),
            contains=("raft sync web", "raft doctor"),
            tag="docker",
        )
        CtaAsserts.cta(
            DockerMessages.docker_pull_failure_message("img", detail="  \n"),
            contains=("docker login", "raft doctor"),
        )

    def _assert_pull_raises(self) -> None:
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_docker_pull_failure("img", detail="unauthorized: authentication required")
        CtaAsserts.operator(
            caught.value,
            contains=("docker login",),
            fix_label="Fix (as the raft user):",
        )
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_docker_pull_failure(
                "img",
                detail="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            )
        CtaAsserts.operator(caught.value, contains=("systemctl start docker",))
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_docker_pull_failure("img", detail="no such host")
        CtaAsserts.operator(caught.value, contains=("raft sync",))

    def test_run_docker_checked(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(returncode=0, stdout="x", stderr="")
        assert CheckedCommands.run_docker(shell, ("ps",), action="ps").stdout == "x"
        self._assert_docker_daemon_error(shell)
        self._assert_docker_hint_and_empty(shell)

    def _assert_docker_daemon_error(self, shell) -> None:
        shell.docker.return_value = MagicMock(
            returncode=1, stdout="", stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.run_docker(shell, ("ps",), action="ps")
        CtaAsserts.operator(caught.value, contains=("systemctl start docker",))

    def _assert_docker_hint_and_empty(self, shell) -> None:
        shell.docker.return_value = MagicMock(
            returncode=1, stdout="", stderr="something broke\nmore"
        )
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.run_docker(shell, ("run", "x"), action="run tmp", hint="retry")
        CtaAsserts.operator(caught.value, contains=("hint: retry", "(docker: something broke)"))
        shell.docker.return_value = MagicMock(returncode=1, stdout="", stderr="   \n")
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.run_docker(shell, ("ps",), action="ps")
        CtaAsserts.operator(caught.value, contains=("raft doctor",))

    def test_run_checked_dispatch(self) -> None:
        shell = MagicMock()
        shell.compose.return_value = MagicMock(returncode=0, stdout="", stderr="")
        shell.docker.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert CheckedCommands.run(shell, ("ps",), kind="compose", action="ps").returncode == 0
        assert CheckedCommands.run(shell, ("ps",), kind="docker", action="ps").stdout == "ok"
        with pytest.raises(ValueError, match="unsupported run_checked kind"):
            CheckedCommands.run(shell, ("ps",), kind="git", action="ps")
