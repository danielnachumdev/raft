"""Always-on control plane (health heal, scale-to-zero). Stub until implemented."""

from __future__ import annotations

import time

__all__ = ["main"]


def main() -> None:
    """Keep the container alive; real reconcile loops come later."""
    while True:
        time.sleep(3600)
