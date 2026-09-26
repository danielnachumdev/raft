"""Allocated Compose resource ceilings for status rows."""

from __future__ import annotations

from ....errors import OperatorError
from ....models.app import App
from ....models.stack import Stack
from .models import (
    CONTROLLER_CPUS_LIMIT,
    CONTROLLER_CPUS_RESERVATION,
    CONTROLLER_MEMORY_LIMIT,
    CONTROLLER_MEMORY_RESERVATION,
    EDGE_CPUS_LIMIT,
    EDGE_CPUS_RESERVATION,
    EDGE_MEMORY_LIMIT,
    EDGE_MEMORY_RESERVATION,
    AllocatedResources,
)


class StatusAllocated:
    """Map edge / controller / app contracts to ``AllocatedResources``."""

    @staticmethod
    def edge() -> AllocatedResources:
        return AllocatedResources(
            cpus_limit=EDGE_CPUS_LIMIT,
            memory_limit=EDGE_MEMORY_LIMIT,
            cpus_reservation=EDGE_CPUS_RESERVATION,
            memory_reservation=EDGE_MEMORY_RESERVATION,
        )

    @staticmethod
    def controller() -> AllocatedResources:
        return AllocatedResources(
            cpus_limit=CONTROLLER_CPUS_LIMIT,
            memory_limit=CONTROLLER_MEMORY_LIMIT,
            cpus_reservation=CONTROLLER_CPUS_RESERVATION,
            memory_reservation=CONTROLLER_MEMORY_RESERVATION,
        )

    @staticmethod
    def app(stack: Stack, app: App) -> AllocatedResources:
        try:
            spec = stack.spec_for(app)
        except (OSError, ValueError, KeyError, OperatorError):
            return AllocatedResources(
                cpus_limit="0.50",
                memory_limit="128M",
                cpus_reservation="0.10",
                memory_reservation="32M",
            )
        return AllocatedResources(
            cpus_limit=spec.cpus_limit,
            memory_limit=spec.memory_limit,
            cpus_reservation=spec.cpus_reservation,
            memory_reservation=spec.memory_reservation,
        )
