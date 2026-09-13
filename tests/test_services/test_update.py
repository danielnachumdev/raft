"""Self-update / reinstall via remote install.sh (no lasting clone)."""

from __future__ import annotations

from unittest.mock import MagicMock

from .base import ServicesTestCase
from raft.services.update import DEFAULT_INSTALL_URL, SelfUpdate


class TestSelfUpdate(ServicesTestCase):
    def test_run_fetches_remote_install_script(self, capsys, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        shell = MagicMock()
        SelfUpdate(self.stack, shell).run()
        shell.run.assert_called_once()
        args = shell.run.call_args.args[0]
        assert args[0] == "bash"
        assert args[1] == "-c"
        assert "curl -fsSL" in args[2]
        assert args[4] == DEFAULT_INSTALL_URL
        out = capsys.readouterr().out
        assert "Updating raft" in out
        assert "reinstalled" in out

    def test_run_respects_install_url_env(self, monkeypatch) -> None:
        url = "https://example.test/install.sh"
        monkeypatch.setenv("RAFT_INSTALL_URL", url)
        shell = MagicMock()
        SelfUpdate(self.stack, shell).run()
        assert shell.run.call_args.args[0][4] == url

    def test_run_ignores_local_install_script(self, monkeypatch) -> None:
        """Local checkout install.sh must not short-circuit GitHub refresh."""
        script = self.tmp_path / "install.sh"
        script.write_text("#!/bin/bash\n", encoding="utf-8")
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        shell = MagicMock()
        SelfUpdate(self.stack, shell).run()
        args = shell.run.call_args.args[0]
        assert args[4] == DEFAULT_INSTALL_URL
        assert "bash" == args[0]
