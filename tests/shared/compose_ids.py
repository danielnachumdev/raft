"""Compose service id lists for docker.running_services mocks."""

from __future__ import annotations

from typing import List


class RunningServices:
    """Declarative edge / app service id lists for orchestrator + doctor tests."""

    EDGE = ("raft-gate", "raft-router", "raft-controller")

    @classmethod
    def edge(cls) -> List[str]:
        return list(cls.EDGE)

    @classmethod
    def with_apps(cls, *apps: str) -> List[str]:
        return [*cls.EDGE, *apps]

    @classmethod
    def gate_only(cls) -> List[str]:
        return ["raft-gate"]

    @classmethod
    def router_only(cls) -> List[str]:
        return ["raft-router"]
