"""Local e2e: Fire sees deferred groups without loading serve."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
import pytest
from fire import helptext

from raft.services.cli.cli import RaftCLI
from raft.services.cli.commands.raft_commands import RaftCLICommands
from raft.services.cli.utils.lazy_import import FireLazyImportAdapter
from tests.unit.services.cli.base import CliTestCase


class TestFireLazyGroups(CliTestCase):
    def test_root_help_lists_group_docs_without_serve(self) -> None:
        with self.patched_deps():
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                with pytest.raises(SystemExit) as exc:
                    RaftCLI()._invoke_fire(["--help"])
            assert exc.value.code == 0
            text = buf.getvalue() + err.getvalue()
        assert "GROUPS" in text
        assert "alerts" in text
        assert "alert rules" in text
        assert "events" in text
        assert "status" in text
        assert "raft.services.serve" not in sys.modules

    def test_helptext_on_commands_keeps_alerts_unimported(self) -> None:
        sys.modules.pop("raft.services.cli.commands.alerts", None)
        with self.patched_deps():
            cmds = RaftCLICommands()
            text = helptext.HelpText(cmds, verbose=False)
            assert isinstance(cmds.alerts, FireLazyImportAdapter)
            assert "alert rules" in text
        assert "raft.services.cli.commands.alerts" not in sys.modules

    def test_alerts_help_lists_subcommands(self) -> None:
        with self.patched_deps():
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                with pytest.raises(SystemExit) as exc:
                    RaftCLI()._invoke_fire(["alerts", "--help"])
            assert exc.value.code == 0
            text = buf.getvalue() + err.getvalue()
        assert "Manage alert rules" in text
        assert "apply" in text
        assert "list" in text

    def test_events_help_exposes_call_flags(self) -> None:
        with self.patched_deps():
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                with pytest.raises(SystemExit) as exc:
                    RaftCLI()._invoke_fire(["events", "--help"])
            assert exc.value.code == 0
            text = buf.getvalue() + err.getvalue()
        assert "--hours" in text
        assert "--json" in text

    def test_alerts_list_dispatches_through_adapter(self) -> None:
        # Fire introspects the group; MagicMock hangs / exposes mock attrs.
        class _Alerts:
            def __init__(self) -> None:
                self.list_calls = 0

            def list(self) -> None:
                self.list_calls += 1

        alerts = _Alerts()
        with self.patched_deps(AlertsCLI=alerts) as deps:
            assert RaftCLI()._invoke_fire(["alerts", "list"]) == 0
        deps["AlertsCLI"].assert_called_with(self.stack)
        assert alerts.list_calls == 1
