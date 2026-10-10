"""GitHub repo listing contract + shared types (strategies implement it)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class GithubRepo:
    full_name: str
    name: str
    owner: str
    private: bool
    default_branch: str
    clone_url: str
    ssh_url: str
    html_url: str


class GithubProvider(Protocol):
    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        ...

    def fetch_manifest(self, token: str, full_name: str, ref: str) -> str:
        ...

    def resolve_local_tree(self, full_name: str) -> Optional[Path]:
        ...


def filter_repos(repos: List[GithubRepo], query: str) -> List[GithubRepo]:
    q = query.strip().lower()
    if not q:
        return repos
    return [r for r in repos if q in r.full_name.lower()]
