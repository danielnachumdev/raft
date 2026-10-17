"""Open a PR that adds a GitHub Actions workflow for ``raft apply`` (v1)."""

import base64
import json
from typing import Optional
from urllib.parse import quote

from raft.core.core.errors.cta import OperatorError
from ..gateway import GithubApiGateway, GithubHttpError
from ..providers import GithubRepo
from .ci_pr_result import CiPrResult
from .ci_workflow import BRANCH_NAME, WORKFLOW_REL, RaftApplyWorkflow

_API = "https://api.github.com"


class GithubCiPrSetup:
    """Ensure a raft-apply Actions workflow via Contents + Pulls API."""

    def __init__(self, *, gateway: Optional[GithubApiGateway] = None) -> None:
        self._workflow = RaftApplyWorkflow()
        self._http = gateway or GithubApiGateway()

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
        headers = self._http.bearer_headers(token)
        headers["Content-Type"] = "application/json"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        try:
            if method == "GET":
                return self._http.get(url, headers=headers).body
            if method == "POST":
                return self._http.post(url, headers=headers, body=body).body
            if method == "PUT":
                return self._http.put(url, headers=headers, body=body).body
            raise OperatorError(
                f"unsupported GitHub HTTP method {method!r}\nFix: report a raft bug",
                has_fix=False,
            )
        except GithubHttpError as exc:
            raise OperatorError(
                f"GitHub API error HTTP {exc.code}: {exc.body}\n"
                f"Fix: re-login with scopes read:user repo workflow",
                has_fix=False,
            ) from exc
