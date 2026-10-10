"""Decide whether app deploy needs tmp dual-run cutover."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from raft.models.app import App
from raft.models.state.scaling_store import ScalingStore


class DualRunCutover:
    """Dual-run cutover only when a live replica is serving (not scaled idle)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def needed(self, app: App, running: Sequence[str]) -> bool:
        """True when ``*_tmp`` side-by-side cutover is required."""
        if app.compose_id not in running:
            return False
        return not ScalingStore(self._root).is_scaled_to_zero(app.name)
