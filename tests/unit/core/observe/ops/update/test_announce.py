"""UpdateAnnounce ``OK: prev → current`` operator lines."""

from __future__ import annotations

from unittest.mock import patch

from raft.core.observe.ops.update import UpdateAnnounce


class TestUpdateAnnounce:
    def test_already_current_with_version_line(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=True,
                before_line="raft 0.1.0 (git main@abc1234)",
                after_line="raft 0.1.0 (git main@abc1234)",
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts == [
            "raft is already up to date",
            "raft 0.1.0 (git main@abc1234)",
        ]

    def test_already_current_without_version_line(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=True, before_line=None, after_line=None
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts == ["raft is already up to date"]

    def test_transition_wheel(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False,
                before_line="raft 0.10.1 (wheel raft-0.10.1-py3-none-any.whl)",
                after_line="raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)",
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[0] == (
            "OK: raft 0.10.1 (wheel raft-0.10.1-py3-none-any.whl) → "
            "raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)"
        )
        assert texts[1].startswith("Next: align the running stack")
        assert "raft doctor" in texts[1]
        assert "PREVIOUS → CURRENT" not in texts

    def test_transition_git_refs(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False,
                before_line="raft 0.1.0 (git main@abc1234)",
                after_line="raft 0.1.0 (git feat/foo@def5678)",
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[0] == (
            "OK: raft 0.1.0 (git main@abc1234) → "
            "raft 0.1.0 (git feat/foo@def5678)"
        )
        assert texts[1].startswith("Next:")
        assert "PREVIOUS → CURRENT" not in texts

    def test_updated_without_version_lines_fallback(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False, before_line=None, after_line=None
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[0] == "OK: raft updated"
        assert texts[1].startswith("Next:")
        assert "PREVIOUS → CURRENT" not in texts

    def test_partial_version_uses_unknown(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False,
                before_line="raft 0.1.0 (git main@abc)",
                after_line=None,
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[0] == "OK: raft 0.1.0 (git main@abc) → (unknown)"
