"""Reusable App ``spec`` fragments for applied YAML / manifests."""

from typing import Any


class AppSpecExtras:
    @classmethod
    def worker_ports(cls) -> dict[str, Any]:
        """No listeners: empty ports + readiness none (worker Apps)."""
        return {"ports": [], "readiness": {"type": "none"}}

    @classmethod
    def readiness_none(cls) -> dict[str, Any]:
        return {"readiness": {"type": "none"}}
