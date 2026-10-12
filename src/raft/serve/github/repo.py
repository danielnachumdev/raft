"""GitHub repo DTO + local query filter for serve providers."""

from dataclasses import dataclass
from typing import List


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


def filter_repos(repos: List[GithubRepo], query: str) -> List[GithubRepo]:
    q = query.strip().lower()
    if not q:
        return repos
    return [r for r in repos if q in r.full_name.lower()]
