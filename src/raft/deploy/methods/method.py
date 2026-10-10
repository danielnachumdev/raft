"""DeploymentMethod ABC — subclass + register to add a transition strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from raft.models.app import App


@dataclass
class DeploymentContext:
    """Inputs for one deploy transition (up or down live-replica case)."""

    support: Any
    app: App
    ref_override: Optional[str] = None
    force_sync: bool = False
    done: str = "deployed"


class DeploymentMethod(ABC):
    """Open-closed deploy transition. Callers select via type_id, then dispatch."""

    @property
    @abstractmethod
    def type_id(self) -> str:
        """Stable discriminator matched by ``spec.deployment.method``."""

    @abstractmethod
    def deploy_when_up(self, ctx: DeploymentContext) -> None:
        """Replace a live serving replica (DualRunCutover.needed is true)."""

    @abstractmethod
    def deploy_when_down(self, ctx: DeploymentContext) -> None:
        """Deploy when idle / not running (single generation; no ``*_tmp``)."""
