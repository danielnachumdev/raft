"""DashboardProcess nginx + app orchestration coverage."""

import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.services.dashboard.process import DashboardProcess
from tests.unit.base import RaftTestCase, StackMakers


class TestDashboardProcess(RaftTestCase):
    def test_write_nginx_and_run_exits(self) -> None:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text(
            "dashboard:\n  auth:\n    mode: none\n", encoding="utf-8"
        )
        proc = DashboardProcess(StackMakers.make_stack(home))
        server = MagicMock()
        conf = home / "nginx.conf"
        with patch.object(proc, "_start_app", return_value=server):
            with patch.object(proc, "_wait_ready"):
                with patch.object(proc, "_run_nginx", return_value=0):
                    with patch("raft.services.dashboard.process._CONF", conf):
                        with pytest.raises(SystemExit) as exited:
                            proc.run()
        assert exited.value.code == 0
        assert "listen" in conf.read_text(encoding="utf-8")
        assert server.should_exit is True

    def test_wait_ready_ok_and_timeout(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            DashboardProcess._wait_ready(sock.getsockname()[1], timeout=1.0)
        with pytest.raises(RuntimeError, match="did not listen"):
            DashboardProcess._wait_ready(1, timeout=0.05)

    def test_start_app_and_run_nginx(self) -> None:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text("{}\n", encoding="utf-8")
        proc = DashboardProcess(StackMakers.make_stack(home))
        server = MagicMock()
        with patch("raft.services.dashboard.process.ServeAppFactory") as factory:
            with patch("raft.services.dashboard.process.uvicorn.Config"):
                with patch(
                    "raft.services.dashboard.process.uvicorn.Server",
                    return_value=server,
                ):
                    with patch(
                        "raft.services.dashboard.process.threading.Thread"
                    ) as thread:
                        out = proc._start_app(listen=8787, app_port=18787)
        assert out is server
        factory.assert_called_once()
        thread.assert_called_once()
        with patch("raft.services.dashboard.process.subprocess.Popen") as popen:
            popen.return_value.wait.return_value = 0
            assert DashboardProcess._run_nginx() == 0

