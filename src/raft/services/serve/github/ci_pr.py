"""Open a PR that adds a GitHub Actions workflow for ``raft apply`` (v1)."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote

from raft.errors.cta import OperatorError

from .ci_workflow import BRANCH_NAME, WORKFLOW_REL, RaftApplyWorkflow
from .provider import GithubRepo

_API = "https://api.github.com"
_UA = "raft-serve-github-v1"


@dataclass(frozen=True)
class CiPrResult:
    status: str
    detail: str
    pr_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"status": self.status, "detail": self.detail}
        if self.pr_url:
            out["pr_url"] = self.pr_url
        return out


class GithubCiPrSetup:
    """Ensure a raft-apply Actions workflow via Contents + Pulls API."""

    def __init__(self) -> None:
        self._workflow = RaftApplyWorkflow()

    def ensure(self, token: str, repo: GithubRepo, *, mock: bool = False) -> CiPrResult:
        if mock:
            return CiPrResult(
                status="opened",
                detail="mock CI PR (fixture; no GitHub write)",
                pr_url=f"{repo.html_url}/pull/1",
            )
        return self._ensure_or_wrap(token, repo)

    def _ensure_or_wrap(self, token: str, repo: GithubRepo) -> CiPrResult:
        try:
            return self._ensure_real(token, repo)
        except OperatorError:
            raise
        except Exception as exc:
            raise OperatorError(
                f"CI PR setup failed: {exc}\n"
                f"Fix: re-login with scopes that include repo + workflow, then retry",
                has_fix=False,
            ) from exc

    def _ensure_real(self, token: str, repo: GithubRepo) -> CiPrResult:
        base = repo.default_branch or "main"
        if self._workflow_on_ref(token, repo.full_name, base):
            return CiPrResult(status="exists", detail=f"{WORKFLOW_REL} already on {base}")
        sha = self._branch_sha(token, repo.full_name, base)
        self._ensure_branch(token, repo.full_name, sha)
        self._put_workflow(token, repo, base)
        url = self._open_pr(token, repo, base)
        return CiPrResult(status="opened", detail=f"PR opened with {WORKFLOW_REL}", pr_url=url)

    def _workflow_on_ref(self, token: str, full_name: str, ref: str) -> bool:
        path = quote(WORKFLOW_REL)
        url = f"{_API}/repos/{full_name}/contents/{path}?ref={quote(ref)}"
        try:
            self._request(token, url)
            return True
        except OperatorError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise

    def _branch_sha(self, token: str, full_name: str, branch: str) -> str:
        url = f"{_API}/repos/{full_name}/git/ref/heads/{quote(branch)}"
        data = json.loads(self._request(token, url))
        obj = data.get("object") if isinstance(data, dict) else None
        sha = obj.get("sha") if isinstance(obj, dict) else None
        if not sha:
            raise OperatorError(
                f"could not resolve default branch sha for {full_name}\n"
                f"Fix: check the repo default branch",
                has_fix=False,
            )
        return str(sha)

    def _ensure_branch(self, token: str, full_name: str, sha: str) -> None:
        url = f"{_API}/repos/{full_name}/git/refs"
        body = {"ref": f"refs/heads/{BRANCH_NAME}", "sha": sha}
        try:
            self._request(token, url, method="POST", payload=body)
        except OperatorError as exc:
            if "HTTP 422" in str(exc):
                return
            raise

    def _put_workflow(self, token: str, repo: GithubRepo, base: str) -> None:
        path = quote(WORKFLOW_REL)
        url = f"{_API}/repos/{repo.full_name}/contents/{path}"
        content = self._workflow.render(repo, base)
        payload = {
            "message": "ci: add raft apply workflow",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": BRANCH_NAME,
        }
        self._request(token, url, method="PUT", payload=payload)

    def _open_pr(self, token: str, repo: GithubRepo, base: str) -> str:
        url = f"{_API}/repos/{repo.full_name}/pulls"
        payload = {
            "title": "ci: raft apply on push",
            "head": BRANCH_NAME,
            "base": base,
            "body": self._workflow.pr_body(),
        }
        try:
            data = json.loads(self._request(token, url, method="POST", payload=payload))
        except OperatorError as exc:
            if "HTTP 422" in str(exc):
                return self._existing_pr_url(token, repo) or repo.html_url
            raise
        return self._pr_html(data)

    def _existing_pr_url(self, token: str, repo: GithubRepo) -> Optional[str]:
        owner = repo.full_name.split("/", 1)[0]
        head = quote(f"{owner}:{BRANCH_NAME}")
        url = f"{_API}/repos/{repo.full_name}/pulls?state=open&head={head}"
        data = json.loads(self._request(token, url))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            html = data[0].get("html_url")
            return str(html) if html else None
        return None

    @staticmethod
    def _pr_html(data: object) -> str:
        html = data.get("html_url") if isinstance(data, dict) else None
        if not html:
            raise OperatorError(
                "GitHub did not return a pull request URL.\nFix: open PRs manually",
                has_fix=False,
            )
        return str(html)

    def _request(
        self,
        token: str,
        url: str,
        *,
        method: str = "GET",
        payload: Optional[dict] = None,
    ) -> str:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": _UA,
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        return self._read(req)

    @staticmethod
    def _read(req: urllib.request.Request) -> str:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:240]
            raise OperatorError(
                f"GitHub API error HTTP {exc.code}: {detail}\n"
                f"Fix: re-login with scopes read:user repo workflow",
                has_fix=False,
            ) from exc
