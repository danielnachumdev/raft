"""UpdateOutcome + SelfUpdate announce=False return path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.core.observe.ops import update as update_mod
from raft.core.observe.ops.update import SelfUpdate, UpdateOutcome
from raft.core.core.ui.progress import TerminalProgress

from tests.unit.domain_case import DomainTestCase


class TestUpdateOutcome(DomainTestCase):
    def setup_method(self) -> None:
        TerminalProgress._active = None

    def teardown_method(self) -> None:
        TerminalProgress._active = None

    def test_run_returns_outcome_without_announce(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: "same")
        monkeypatch.setattr(
            update_mod.SelfUpdate,
            "_version_line",
            lambda self: "raft 0.1.0",
        )
        shell = MagicMock()
        gate = MagicMock()
        gate.ensure = MagicMock()
        gate.uses_host_docker.return_value = False
        upd = SelfUpdate(self.stack, host_gate=gate)
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            outcome = upd.run(announce=False)
        assert outcome.already_current is True
        assert outcome.after_line == "raft 0.1.0"
        assert say.call_count == 0

    def test_as_public_and_next_steps(self) -> None:
        changed = UpdateOutcome(
            already_current=False,
            before_line="raft 0.10.0",
            after_line="raft 0.11.0",
        )
        public = changed.as_public()
        assert public["alreadyCurrent"] is False
        assert "raft render" in (public["nextSteps"] or "")
        assert "raft dashboard disable" in (public["nextSteps"] or "")
        same = UpdateOutcome(
            already_current=True, before_line="raft 0.11.0", after_line="raft 0.11.0"
        )
        assert same.next_steps() is None
