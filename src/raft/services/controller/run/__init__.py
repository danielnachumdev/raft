"""``raft-controller`` process entry (prereq smoke, then job orchestrator)."""

from .controller_loop import ControllerLoop
from .raft_controller import RaftController


def main() -> None:
    """Console / ``python -m raft.services.controller`` entry."""
    RaftController().run()


__all__ = ["ControllerLoop", "RaftController", "main"]
