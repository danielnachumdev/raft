"""Concrete GithubProvider implementations (mock / real API)."""

from .mock import MockGithubProvider
from .real import RealGithubProvider

__all__ = ["MockGithubProvider", "RealGithubProvider"]
