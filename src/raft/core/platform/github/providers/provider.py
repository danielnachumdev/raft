"""GithubProvider ABC — strategies implement list/fetch/resolve."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from .repo import GithubRepo


class GithubProvider(ABC):
    """Open-closed GitHub repo access for serve deploy assist."""

    @abstractmethod
    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        """Return repos visible to ``token``, optionally filtered by ``query``."""

    @abstractmethod
    def fetch_manifest(self, token: str, full_name: str, ref: str) -> str:
        """Return raw ``.raft/app.yaml`` text for ``full_name`` at ``ref``."""

    @abstractmethod
    def resolve_local_tree(self, full_name: str) -> Optional[Path]:
        """Return a local checkout path when the provider has one."""
