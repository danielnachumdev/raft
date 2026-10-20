"""Dashboard app_server entry coverage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.services.dashboard import app_server
from tests.unit.base import RaftTestCase


class TestDashboardAppServer(RaftTestCase):
    def test_main_runs_uvicorn(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with patch("raft.services.dashboard.app_server.RaftHome") as home_cls:
            with patch("raft.services.dashboard.app_server.Stack.load_apps") as load:
                with patch(
                    "raft.services.dashboard.app_server.ServeAppFactory"
                ) as factory:
                    with patch(
                        "raft.services.dashboard.app_server.uvicorn.run"
                    ) as run:
                        home_cls.return_value.resolve.return_value = home
                        stack = MagicMock()
                        stack.root = home
                        load.return_value = stack
                        factory.return_value.create.return_value = MagicMock()
                        app_server.main(["19001"])
        run.assert_called_once()
        assert run.call_args.kwargs["port"] == 19001
        assert run.call_args.kwargs["host"] == "127.0.0.1"

    def test_env_port(self) -> None:
        with patch.dict("os.environ", {"RAFT_SERVE_PORT": "8801"}):
            assert app_server._env_port("RAFT_SERVE_PORT", 8787) == 8801
        with patch.dict("os.environ", {"RAFT_SERVE_PORT": "x"}):
            assert app_server._env_port("RAFT_SERVE_PORT", 8787) == 8787
