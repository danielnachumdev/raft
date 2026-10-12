"""Fully remove raft from this machine (`raft uninstall --yes`)."""

from .service import Uninstall

__all__ = ["Uninstall"]
