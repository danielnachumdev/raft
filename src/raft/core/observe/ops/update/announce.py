"""Operator messages after ``raft update`` finishes."""

from __future__ import annotations

from typing import Optional

from raft.core.core.ui import OperatorSay


class UpdateAnnounce:
    """Print ``OK: prev → current`` (or already-current) after reinstall."""

    _NEXT = (
        "Next: align the running stack with this release — templates and "
        "Compose ids can change. Typical path: `raft render`, then "
        "`raft redeploy <app|router>` for targeted updates, or "
        "`raft down && raft up` when edge/service names or schemas shifted. "
        "Finish with `raft doctor`."
    )

    def say(
        self,
        *,
        already_current: bool,
        before_line: Optional[str],
        after_line: Optional[str],
    ) -> None:
        if already_current:
            self._already_current(after_line or before_line)
            return
        self._ok_transition(before_line, after_line)
        OperatorSay.say(self._NEXT, style="info")

    @staticmethod
    def _already_current(line: Optional[str]) -> None:
        OperatorSay.say("raft is already up to date", style="info")
        if line:
            OperatorSay.say(line, style="info")

    @staticmethod
    def _ok_transition(before: Optional[str], after: Optional[str]) -> None:
        if not before and not after:
            OperatorSay.say("OK: raft updated", style="ok")
            return
        left = before or "(unknown)"
        right = after or "(unknown)"
        OperatorSay.say(f"OK: {left} → {right}", style="ok")
