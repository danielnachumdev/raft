"""DashboardProcess nginx + app orchestration coverage."""

import socket
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.services.dashboard.process import DashboardProcess
from tests.unit.base import RaftTestCase, StackMakers


class TestDashboardProcess(RaftTestCase):
    def test_run_starts_app_then_nginx(self) -> None:
        proc, conf = self._proc_with_conf()
        app, nginx = MagicMock(), MagicMock()
        app.poll.side_effect = [None, 0, 0]
        nginx.poll.return_value = None
        self._run_mocked(proc, app, nginx, conf)
        text = conf.read_text(encoding="utf-8")
        assert "listen" in text and "absolute_redirect off" in text

    def test_wait_ready_ok_and_timeout(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            DashboardProcess._wait_ready(sock.getsockname()[1], timeout=1.0)
        with pytest.raises(RuntimeError, match="did not listen"):
            DashboardProcess._wait_ready(1, timeout=0.05)

    def test_start_helpers_and_ports(self) -> None:
        proc, _ = self._proc_with_conf()
        with patch("raft.services.dashboard.process.subprocess.Popen") as popen:
            popen.return_value = MagicMock()
            proc._start_app(app_port=18787)
            proc._start_nginx()
        assert popen.call_count == 2
        with patch.dict("os.environ", {"RAFT_SERVE_PORT": "8801"}):
            assert DashboardProcess._listen_port(8787) == 8801
        with patch.dict("os.environ", {"RAFT_DASHBOARD_APP_PORT": "bad"}):
            assert DashboardProcess._app_port() == 18787

    def test_nginx_exit_shutdown_and_signals(self) -> None:
        proc, _ = self._proc_with_conf()
        app, nginx = MagicMock(), MagicMock()
        app.poll.return_value = None
        nginx.poll.side_effect = [None, 3]
        proc._app, proc._nginx = app, nginx
        assert proc._wait_either() == 3
        self._assert_shutdown_kill(proc)
        with patch.object(proc, "_shutdown") as shut:
            proc._install_signals()
            with pytest.raises(SystemExit):
                # invoke the installed SIGTERM handler
                import signal

                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            shut.assert_called_once()

    def _assert_shutdown_kill(self, proc: DashboardProcess) -> None:
        done = MagicMock()
        done.poll.return_value = 0
        alive = MagicMock()
        alive.poll.return_value = None
        alive.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=1)
        proc._nginx, proc._app = done, alive
        proc._shutdown()
        done.terminate.assert_not_called()
        alive.kill.assert_called_once()

    def _proc_with_conf(self):
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text(
            "dashboard:\n  auth:\n    mode: none\n", encoding="utf-8"
        )
        return DashboardProcess(StackMakers.make_stack(home)), home / "nginx.conf"

    def _run_mocked(self, proc, app, nginx, conf) -> None:
        with patch("raft.services.dashboard.process._CONF", conf):
            with patch.object(proc, "_start_app", return_value=app):
                with patch.object(proc, "_wait_ready"):
                    with patch.object(proc, "_start_nginx", return_value=nginx):
                        with patch.object(proc, "_install_signals"):
                            with patch.object(proc, "_shutdown"):
                                with pytest.raises(SystemExit) as exited:
                                    proc.run()
        assert exited.value.code == 0
