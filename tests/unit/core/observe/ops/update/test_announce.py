"""UpdateAnnounce PREVIOUS → CURRENT operator lines."""

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

    def test_transition_wheel(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False,
                before_line="raft 0.10.1 (wheel raft-0.10.1-py3-none-any.whl)",
                after_line="raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)",
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[0] == "OK: raft updated"
        assert texts[1] == "PREVIOUS → CURRENT"
        assert texts[2] == (
            "raft 0.10.1 (wheel raft-0.10.1-py3-none-any.whl) → "
            "raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)"
        )
        assert "raft doctor" in texts[3]

    def test_transition_git_refs(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False,
                before_line="raft 0.1.0 (git main@abc1234)",
                after_line="raft 0.1.0 (git feat/foo@def5678)",
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[1] == "PREVIOUS → CURRENT"
        assert texts[2] == (
            "raft 0.1.0 (git main@abc1234) → raft 0.1.0 (git feat/foo@def5678)"
        )

    def test_updated_without_version_lines_skips_transition(self) -> None:
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            UpdateAnnounce().say(
                already_current=False, before_line=None, after_line=None
            )
        texts = [c.args[0] for c in say.call_args_list]
        assert texts[0] == "OK: raft updated"
        assert "PREVIOUS → CURRENT" not in texts
