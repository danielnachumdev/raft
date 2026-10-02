"""Locate packaged serve templates and static assets."""

from __future__ import annotations

from pathlib import Path


class ServePaths:
    """Resolve ``share/serve`` next to the installed raft package."""

    @staticmethod
    def share_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "share" / "serve"

    @classmethod
    def templates_dir(cls) -> Path:
        return cls.share_dir() / "templates"

    @classmethod
    def static_dir(cls) -> Path:
        return cls.share_dir() / "static"
