"""Shared volumes/groups test fixtures."""

from __future__ import annotations

from typing import Any

from ....base import RaftTestCase


class VolumesTestCase(RaftTestCase):
    @staticmethod
    def base_docker(*, name: str = "x") -> dict[str, Any]:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": {
                "source": "docker",
                "image": "redis",
                "path": f"apps/{name}",
                "ports": [
                    {
                        "name": "redis",
                        "containerPort": 6379,
                        "expose": "none",
                    }
                ],
                "readiness": {"type": "none"},
            },
        }
