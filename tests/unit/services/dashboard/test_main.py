"""``python -m raft.services.dashboard`` entry coverage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.services.dashboard import __main__ as dash_main
from tests.unit.base import RaftTestCase


class TestDashboardMain(RaftTestCase):
    def test_port_from_env_and_settings(self) -> None:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text(
            "dashboard:\n  enabled: true\n  port: 8799\n",
            encoding="utf-8",
        )
        assert dash_main._port(home) == 8799
        with patch.dict("os.environ", {"RAFT_SERVE_PORT": "8801"}):
            assert dash_main._port(home) == 8801

    def test_main_runs_serve(self) -> None:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with patch("raft.services.dashboard.__main__.load_stack") as load:
            with patch("raft.services.dashboard.__main__.Serve") as serve_cls:
                stack = MagicMock()
                stack.root = home
                load.return_value = stack
                serve_cls.return_value.run = MagicMock()
                dash_main.main()
                serve_cls.return_value.run.assert_called_once()
