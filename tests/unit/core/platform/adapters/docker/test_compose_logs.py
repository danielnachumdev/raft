"""Docker compose/container log helpers."""

from unittest.mock import MagicMock

from tests.shared.nginx import NginxEmerg

from tests.unit.core.platform.adapters.docker.base import DockerTestCase


class _RaisingIter:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def __iter__(self):
        return self

    def __next__(self):
        raise self._exc


class TestDockerComposeLogs(DockerTestCase):
    def test_compose_and_container_logs(self) -> None:
        self.shell.compose.return_value = self.ok(NginxEmerg.host_not_found() + "\n")
        assert "host not found" in self.docker.compose_logs("app")
        self.shell.compose.assert_any_call(
            "logs", "--no-color", "--tail", "40", "app", capture=True, check=False
        )
        assert self.docker.compose_logs() == ""
        self.shell.docker.return_value = self.ok(
            "", returncode=0, stderr="oauth missing CLIENT_ID\n"
        )
        assert "CLIENT_ID" in self.docker.container_logs("raft-app_tmp")
        assert self.docker.container_logs("") == ""

    def test_follow_compose_logs_streams(self) -> None:
        proc = MagicMock()
        proc.stdout = iter(["line-a\n", "line-b\n"])
        proc.poll.return_value = 0
        self.shell.popen.return_value = proc
        self.docker.follow_compose_logs("app", tail=20)
        self.shell.popen.assert_called_once()
        args = self.shell.popen.call_args.args[0]
        assert args[:6] == ["docker", "compose", "logs", "-f", "--no-color", "--tail"]
        assert args[6:] == ["20", "app"]

    def test_follow_compose_logs_noop_without_services(self) -> None:
        self.shell.popen.reset_mock()
        self.docker.follow_compose_logs()
        self.shell.popen.assert_not_called()

    def test_follow_compose_logs_swallows_keyboard_interrupt(self) -> None:
        proc = MagicMock()
        proc.stdout = _RaisingIter(KeyboardInterrupt)
        proc.poll.return_value = 0
        self.shell.popen.return_value = proc
        self.docker.follow_compose_logs("app")

    def test_iter_follow_compose_logs_yields_lines(self) -> None:
        proc = MagicMock()
        proc.stdout = iter(["one\n", "two\n"])
        proc.poll.return_value = 0
        self.shell.popen.return_value = proc
        assert list(self.docker.iter_follow_compose_logs("app", tail=5)) == [
            "one",
            "two",
        ]
