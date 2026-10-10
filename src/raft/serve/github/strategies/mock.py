"""MockGithubProvider — local fixture repos (no network)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from raft.errors.cta import OperatorError
from raft.models.manifest import CONTRACT_REL_PATH

from ...paths import ServePaths
from ..provider import GithubRepo, filter_repos


class MockGithubProvider:
    """Local fixture repos under ``share/serve/mock-github/`` (no network)."""

    def __init__(self, fixture_root: Optional[Path] = None) -> None:
        self._root = fixture_root or ServePaths.mock_github_dir()

    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        del token
        repos = [self._repo("demo", "http-only-site"), self._repo("demo", "no-manifest")]
        return filter_repos(repos, query)

    def fetch_manifest(self, token: str, full_name: str, ref: str) -> str:
        del token, ref
        tree = self.resolve_local_tree(full_name)
        if tree is None:
            raise OperatorError(
                f"unknown mock repo {full_name!r}\n"
                f"Fix: pick a repo from the list returned by /api/github/repos",
                has_fix=False,
            )
        path = tree / CONTRACT_REL_PATH
        if not path.is_file():
            raise OperatorError(
                f"no {CONTRACT_REL_PATH.as_posix()} in {full_name}\n"
                f"Fix: add that file on the default branch (canonical path only in v1)",
                has_fix=False,
            )
        return path.read_text(encoding="utf-8")

    def resolve_local_tree(self, full_name: str) -> Optional[Path]:
        if "/" not in full_name:
            return None
        owner, name = full_name.split("/", 1)
        if owner != "demo":
            return None
        path = self._root / name
        return path if path.is_dir() else None

    def _repo(self, owner: str, name: str) -> GithubRepo:
        full = f"{owner}/{name}"
        return GithubRepo(
            full_name=full,
            name=name,
            owner=owner,
            private=False,
            default_branch="main",
            clone_url=f"https://github.com/{full}.git",
            ssh_url=f"git@github.com:{full}.git",
            html_url=f"https://github.com/{full}",
        )
