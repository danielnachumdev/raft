"""GitHub repo listing + manifest fetch (real API + mock fixtures)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

from raft.errors.cta import OperatorError
from raft.models.manifest import CONTRACT_REL_PATH

from ..paths import ServePaths

_API = "https://api.github.com"
_UA = "raft-serve-github-v1"
# Owner + collaborator + org-member only (never global public search).
_USER_REPOS_AFFILIATION = "owner,collaborator,organization_member"


def _filter_repos(repos: List["GithubRepo"], query: str) -> List["GithubRepo"]:
    q = query.strip().lower()
    if not q:
        return repos
    return [r for r in repos if q in r.full_name.lower()]


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


class MockGithubProvider:
    """Local fixture repos under ``share/serve/mock-github/`` (no network)."""

    def __init__(self, fixture_root: Optional[Path] = None) -> None:
        self._root = fixture_root or ServePaths.mock_github_dir()

    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        del token
        repos = [self._repo("demo", "http-only-site"), self._repo("demo", "no-manifest")]
        return _filter_repos(repos, query)

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


class RealGithubProvider:
    """GitHub REST API (OAuth token). Lists only the signed-in user's repos."""

    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        return _filter_repos(self._list_user_repos(token), query)

    def fetch_manifest(self, token: str, full_name: str, ref: str) -> str:
        enc = urllib.parse.quote(CONTRACT_REL_PATH.as_posix())
        url = f"{_API}/repos/{full_name}/contents/{enc}?ref={urllib.parse.quote(ref)}"
        raw = self._request(token, url, accept="application/vnd.github.raw")
        if not raw.strip():
            raise OperatorError(
                f"empty {CONTRACT_REL_PATH.as_posix()} in {full_name}@{ref}\n"
                f"Fix: put a valid App manifest at that path",
                has_fix=False,
            )
        return raw

    def resolve_local_tree(self, full_name: str) -> Optional[Path]:
        del full_name
        return None

    def _list_user_repos(self, token: str) -> List[GithubRepo]:
        params = urllib.parse.urlencode(
            {
                "per_page": "100",
                "sort": "updated",
                "affiliation": _USER_REPOS_AFFILIATION,
            }
        )
        return self._paginate(token, f"{_API}/user/repos?{params}")

    def _paginate(self, token: str, url: str) -> List[GithubRepo]:
        out: List[GithubRepo] = []
        next_url: Optional[str] = url
        while next_url and len(out) < 200:
            body, next_url = self._request_page(token, next_url)
            rows = json.loads(body)
            if not isinstance(rows, list):
                break
            for item in rows:
                if isinstance(item, dict):
                    out.append(self._parse_repo(item))
        return out

    def _request_page(self, token: str, url: str) -> tuple[str, Optional[str]]:
        req = self._build_request(token, url)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                link = resp.headers.get("Link")
                return body, self._next_link(link)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from exc

    def _request(self, token: str, url: str, *, accept: str = "application/vnd.github+json") -> str:
        req = self._build_request(token, url, accept=accept)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise OperatorError(
                    f"no {CONTRACT_REL_PATH.as_posix()} at that ref (or repo not visible)\n"
                    f"Fix: add .raft/app.yaml on the selected ref",
                    has_fix=False,
                ) from exc
            raise self._http_error(exc) from exc

    @staticmethod
    def _build_request(
        token: str, url: str, *, accept: str = "application/vnd.github+json"
    ) -> urllib.request.Request:
        return urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": accept,
                "User-Agent": _UA,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    @staticmethod
    def _next_link(link: Optional[str]) -> Optional[str]:
        if not link:
            return None
        for part in link.split(","):
            piece = part.strip()
            if 'rel="next"' in piece:
                start = piece.find("<") + 1
                end = piece.find(">")
                if start > 0 and end > start:
                    return piece[start:end]
        return None

    @staticmethod
    def _parse_repo(item: dict) -> GithubRepo:
        full = str(item.get("full_name") or "")
        owner = full.split("/", 1)[0] if "/" in full else str(item.get("owner", {}).get("login", ""))
        return GithubRepo(
            full_name=full,
            name=str(item.get("name") or ""),
            owner=owner,
            private=bool(item.get("private")),
            default_branch=str(item.get("default_branch") or "main"),
            clone_url=str(item.get("clone_url") or ""),
            ssh_url=str(item.get("ssh_url") or ""),
            html_url=str(item.get("html_url") or ""),
        )

    @staticmethod
    def _http_error(exc: urllib.error.HTTPError) -> OperatorError:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        return OperatorError(
            f"GitHub API error HTTP {exc.code}: {detail}\n"
            f"Fix: re-login from raft serve, or check OAuth scopes (need repo for private)",
            has_fix=False,
        )
