"""RealGithubProvider — GitHub REST API via gateway (OAuth token)."""

import json
import urllib.parse
from pathlib import Path
from typing import List, Optional

from ....errors.cta import OperatorError
from ....models.manifest import CONTRACT_REL_PATH
from ..gateway import GithubApiGateway, GithubHttpError
from ..provider import GithubProvider
from ..repo import GithubRepo, filter_repos

_API = "https://api.github.com"
# Owner + collaborator + org-member only (never global public search).
_USER_REPOS_AFFILIATION = "owner,collaborator,organization_member"


class RealGithubProvider(GithubProvider):
    """GitHub REST API (OAuth token). Lists only the signed-in user's repos."""

    def __init__(self, *, gateway: Optional[GithubApiGateway] = None) -> None:
        self._http = gateway or GithubApiGateway()

    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        return filter_repos(self._list_user_repos(token), query)

    def fetch_manifest(self, token: str, full_name: str, ref: str) -> str:
        raw = self._manifest_body(token, full_name, ref)
        if not raw.strip():
            raise OperatorError(
                f"empty {CONTRACT_REL_PATH.as_posix()} in {full_name}@{ref}\n"
                f"Fix: put a valid App manifest at that path",
                has_fix=False,
            )
        return raw

    def _manifest_body(self, token: str, full_name: str, ref: str) -> str:
        enc = urllib.parse.quote(CONTRACT_REL_PATH.as_posix())
        url = f"{_API}/repos/{full_name}/contents/{enc}?ref={urllib.parse.quote(ref)}"
        try:
            return self._http.get(
                url,
                headers=self._http.bearer_headers(
                    token, accept="application/vnd.github.raw"
                ),
            ).body
        except GithubHttpError as exc:
            if exc.code == 404:
                raise OperatorError(
                    f"no {CONTRACT_REL_PATH.as_posix()} at that ref (or repo not visible)\n"
                    f"Fix: add .raft/app.yaml on the selected ref",
                    has_fix=False,
                ) from exc
            raise self._api_error(exc) from exc

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
        try:
            resp = self._http.get(url, headers=self._http.bearer_headers(token))
        except GithubHttpError as exc:
            raise self._api_error(exc) from exc
        return resp.body, self._next_link(resp.headers.get("Link"))

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
        owner = (
            full.split("/", 1)[0]
            if "/" in full
            else str(item.get("owner", {}).get("login", ""))
        )
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
    def _api_error(exc: GithubHttpError) -> OperatorError:
        return OperatorError(
            f"GitHub API error HTTP {exc.code}: {exc.body}\n"
            f"Fix: re-login from raft serve, or check OAuth scopes (need repo for private)",
            has_fix=False,
        )
