"""Deprecated ``raft gate recreate`` alias (prefer ``raft redeploy gate``)."""

from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from ..utils.deps import Orchestrator


class GateCLI:
    """Deprecated gate subcommands; use ``raft redeploy gate``."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def recreate(self) -> None:
        """Deprecated alias for ``raft redeploy gate`` (brief edge downtime)."""
        OperatorSay.say(
            "`raft gate recreate` is deprecated; use `raft redeploy gate` instead.",
            style="warn",
        )
        Orchestrator(self._stack).redeploy_gate()
