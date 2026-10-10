"""Locate packaged serve SPA assets (Vite build output)."""

from __future__ import annotations

from pathlib import Path


class ServePaths:
    """Resolve ``share/serve`` next to the installed raft package."""

    @staticmethod
    def share_dir() -> Path:
        return Path(__file__).resolve().parents[1] / "share" / "serve"

    @classmethod
    def spa_dir(cls) -> Path:
        return cls.share_dir() / "spa"

    @classmethod
    def spa_index(cls) -> Path:
        return cls.spa_dir() / "index.html"

    @classmethod
    def spa_assets_dir(cls) -> Path:
        return cls.spa_dir() / "assets"

    @classmethod
    def mock_github_dir(cls) -> Path:
        return cls.share_dir() / "mock-github"
