"""RaftCLI prints InstalledVersion without loading the stack."""

from unittest.mock import MagicMock, patch

from raft.services.cli.cli import RaftCLI


class TestCliVersion:
    def test_version_flag_prints_and_skips_fire(self, capsys) -> None:
        fire = MagicMock()
        cli = RaftCLI()
        cli._fire = fire
        with patch(
            "raft.services.cli.cli.InstalledVersion.line",
            return_value="raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)",
        ):
            code = cli._invoke_fire(["--version"])
        assert code == 0
        fire.run.assert_not_called()
        assert (
            capsys.readouterr().out.strip()
            == "raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)"
        )
