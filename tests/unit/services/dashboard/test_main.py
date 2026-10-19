"""``python -m raft.services.dashboard`` entry coverage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.services.dashboard import __main__ as dash_main
from raft.services.dashboard.process import DashboardProcess
from tests.unit.base import RaftTestCase


class TestDashboardMain(RaftTestCase):
    def test_main_runs_process_without_bootstrap(self) -> None:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with patch("raft.services.dashboard.__main__.RaftHome") as home_cls:
            with patch("raft.services.dashboard.__main__.Stack.load_apps") as load:
                with patch(
                    "raft.services.dashboard.__main__.DashboardProcess"
                ) as proc_cls:
                    home_cls.return_value.resolve.return_value = home
                    stack = MagicMock()
                    stack.root = home
                    load.return_value = stack
                    proc_cls.return_value.run = MagicMock()
                    dash_main.main()
                    load.assert_called_once_with(home)
                    proc_cls.assert_called_once_with(stack)
                    proc_cls.return_value.run.assert_called_once()

    def test_listen_and_app_ports(self) -> None:
        with patch.dict("os.environ", {"RAFT_SERVE_PORT": ""}):
            assert DashboardProcess._listen_port(8787) == 8787
        with patch.dict("os.environ", {"RAFT_SERVE_PORT": "8801"}):
            assert DashboardProcess._listen_port(8787) == 8801
        with patch.dict("os.environ", {"RAFT_DASHBOARD_APP_PORT": "bad"}):
            assert DashboardProcess._app_port() == 18787
        with patch.dict("os.environ", {"RAFT_DASHBOARD_APP_PORT": "19001"}):
            assert DashboardProcess._app_port() == 19001
