"""Render an applied stack into generated/ for unit tests."""

from pathlib import Path
from typing import Any

from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.render import StackRenderer

from .orchestrator_root import OrchestratorRoot


class StackRender(OrchestratorRoot):
    @classmethod
    def render_stack(cls, root: Path, *, edge: Any = None) -> Path:
        stack = load_stack(root)
        cls.ensure_app_checkouts(root, *(app.name for app in stack.apps))
        kwargs: dict[str, Any] = {}
        if edge is not None:
            kwargs["edge"] = edge
        StackRenderer(stack, **kwargs).render()
        return root / "generated"
