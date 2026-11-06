"""RaftCLI prints InstalledVersion without loading the stack."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

from raft.services.cli.cli import RaftCLI


class TestCliVersion:
    def test_version_entry_does_not_import_serve(self, monkeypatch, capsys) -> None:
        self._assert_version_subprocess()
        self._assert_version_in_process(monkeypatch, capsys)

    def _assert_version_subprocess(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-c", self._version_probe_script()],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines()[0].startswith("raft ")

    def _assert_version_in_process(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(sys, "argv", ["raft", "version"])
        from raft.services.cli.__main__ import main

        main()
        assert capsys.readouterr().out.splitlines()[0].startswith("raft ")

    @staticmethod
    def _version_probe_script() -> str:
        return "\n".join(
            [
                "import sys",
                "sys.argv = ['raft', 'version']",
                "import raft.services.cli.__main__ as entry",
                "assert 'raft.services.serve' not in sys.modules",
                "assert 'sqlalchemy' not in sys.modules",
                "entry.main()",
                "assert 'raft.services.serve' not in sys.modules",
                "assert 'sqlalchemy' not in sys.modules",
            ]
        )

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
        assert capsys.readouterr().out.strip() == "raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)"
