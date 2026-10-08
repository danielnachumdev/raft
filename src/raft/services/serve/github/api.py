"""FastAPI handlers for GitHub login / repos / deploy (serve v1)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import Body, HTTPException, Request
from fastapi.responses import RedirectResponse

from raft.config.settings import load_config
from raft.errors.cta import OperatorError

from ....models.stack import Stack
from .deploy_job import DeployJobStore, GithubDeployRunner
from .oauth import GITHUB_OAUTH_SCOPES, GithubOauth
from .provider import GithubProvider, MockGithubProvider, RealGithubProvider
from .session import GithubSessionStore
from .settings_write import GithubSettingsWriter


class ServeGithubApi:
    """GitHub OAuth + repo picker + deploy trigger for ``raft serve``."""

    def __init__(
        self,
        stack: Stack,
        *,
        provider: Optional[GithubProvider] = None,
        jobs: Optional[DeployJobStore] = None,
        port: int = 8787,
    ) -> None:
        self.stack = stack
        self._port = port
        self._settings = GithubSettingsWriter(stack.root)
        self._sessions = GithubSessionStore(stack.root)
        self._provider_override = provider
        self._jobs = jobs or DeployJobStore()
        self._cfg = load_config(stack.root).github
        self._oauth = GithubOauth(self._cfg, self._sessions)
        self._provider = provider or self._default_provider()
        self._runner = GithubDeployRunner(stack, self._provider, self._jobs)

    def register(self, app) -> None:
        app.get("/api/github/session")(self.api_session)
        app.get("/api/github/config")(self.api_config)
        app.post("/api/github/config")(self.api_save_config)
        app.get("/api/github/login")(self.api_login)
        app.get("/api/github/callback")(self.api_callback)
        app.post("/api/github/logout")(self.api_logout)
        app.get("/api/github/repos")(self.api_repos)
        app.post("/api/github/deploy")(self.api_deploy)
        app.get("/api/github/deploy/{job_id}")(self.api_deploy_status)

    def api_session(self) -> Dict[str, Any]:
        session = self._sessions.load()
        base = self._settings.public_status(port=self._port)
        base["scopes"] = GITHUB_OAUTH_SCOPES
        base["hint"] = self._login_hint()
        if session is None or not session.access_token:
            base["authenticated"] = False
            return base
        out = session.to_public()
        out.update(base)
        return out

    def api_config(self, request: Request) -> Dict[str, Any]:
        port = self._request_port(request)
        out = self._settings.public_status(port=port)
        out["scopes"] = GITHUB_OAUTH_SCOPES
        return out

    def api_save_config(
        self, request: Request, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        del request
        try:
            cfg = self._settings.save(
                client_id=body.get("clientId") or body.get("client_id"),
                client_secret=body.get("clientSecret") or body.get("client_secret"),
                mock=self._optional_bool(body.get("mock")),
            )
        except OperatorError as exc:
            raise self._http(exc) from exc
        self._reload_github(cfg)
        out = self._settings.public_status(port=self._port)
        out["scopes"] = GITHUB_OAUTH_SCOPES
        out["ok"] = True
        out["reloaded"] = True
        return out

    def api_login(self, request: Request) -> RedirectResponse:
        port = self._request_port(request)
        try:
            url = self._oauth.login_url(port=port)
        except OperatorError as exc:
            return self._oauth_error_redirect(str(exc))
        return RedirectResponse(url, status_code=302)

    def api_callback(
        self,
        request: Request,
        code: Optional[str] = None,
        state: Optional[str] = None,
        mock: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
    ) -> RedirectResponse:
        del request
        if error:
            msg = error_description or error
            return self._oauth_error_redirect(f"GitHub authorization failed: {msg}")
        try:
            self._complete_callback(code=code, state=state, mock=mock)
        except OperatorError as exc:
            return self._oauth_error_redirect(str(exc))
        return RedirectResponse("/deploy", status_code=302)

    def _complete_callback(
        self,
        *,
        code: Optional[str],
        state: Optional[str],
        mock: Optional[str],
    ) -> None:
        if mock == "1" or (self._cfg.mock and not code):
            self._oauth.complete_mock()
            return
        if not code or not state:
            raise OperatorError(
                "OAuth callback missing code/state.\nFix: start login again",
                has_fix=False,
            )
        self._oauth.complete_oauth(code=code, state=state)

    def api_logout(self) -> Dict[str, Any]:
        self._sessions.clear()
        return {"ok": True, "authenticated": False}

    def api_repos(self, q: str = "") -> Dict[str, Any]:
        session = self._require_session()
        try:
            repos = self._provider.list_repos(session.access_token, query=q)
        except OperatorError as exc:
            raise self._http(exc) from exc
        return {
            "repos": [
                {
                    "full_name": r.full_name,
                    "name": r.name,
                    "owner": r.owner,
                    "private": r.private,
                    "default_branch": r.default_branch,
                    "html_url": r.html_url,
                }
                for r in repos
            ]
        }

    def api_deploy(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        session = self._require_session()
        full_name, ref = self._parse_deploy_body(body)
        try:
            repo = self._resolve_repo(session.access_token, full_name)
            job = self._runner.start(session, repo, ref or repo.default_branch)
        except OperatorError as exc:
            raise self._http(exc) from exc
        return job.to_dict()

    @staticmethod
    def _parse_deploy_body(body: Dict[str, Any]) -> tuple[str, str]:
        full_name = str(body.get("full_name") or "").strip()
        ref = str(body.get("ref") or "").strip()
        if not full_name or "/" not in full_name:
            raise HTTPException(
                status_code=400,
                detail="full_name is required (owner/repo)",
            )
        return full_name, ref

    def _resolve_repo(self, token: str, full_name: str):
        repos = self._provider.list_repos(token, query=full_name)
        repo = next((r for r in repos if r.full_name == full_name), None)
        if repo is None:
            repos = self._provider.list_repos(token)
            repo = next((r for r in repos if r.full_name == full_name), None)
        if repo is None:
            raise OperatorError(
                f"repo {full_name!r} not visible to this GitHub session.\n"
                f"Fix: pick a repo from the list, or re-login",
                has_fix=False,
            )
        return repo

    def api_deploy_status(self, job_id: str) -> Dict[str, Any]:
        self._require_session()
        job = self._jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"deploy job '{job_id}' not found")
        return job.to_dict()

    def _require_session(self):
        session = self._sessions.load()
        if session is None or not session.access_token:
            raise HTTPException(
                status_code=401,
                detail="GitHub session required. Open Add new service and sign in.",
            )
        return session

    def _default_provider(self) -> GithubProvider:
        if self._cfg.mock:
            return MockGithubProvider()
        return RealGithubProvider()

    def _reload_github(self, cfg) -> None:
        self._cfg = cfg
        self._oauth = GithubOauth(cfg, self._sessions)
        self._provider = self._provider_override or self._default_provider()
        self._runner = GithubDeployRunner(self.stack, self._provider, self._jobs)

    @staticmethod
    def _optional_bool(raw: Any) -> Optional[bool]:
        if raw is None:
            return None
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _login_hint(self) -> str:
        if not GithubSettingsWriter.oauth_ready(self._cfg):
            return (
                "GitHub OAuth is not configured. Create an OAuth App, paste "
                "client id/secret below (saved to settings.yaml), then continue."
            )
        if self._cfg.mock:
            return (
                "Mock GitHub mode is on — login is local and lists fixture repos. "
                "Serve stays on localhost/tunnel; this login is only for repo pick/deploy."
            )
        return (
            "Temporary GitHub login lists repos you can access, then raft drives apply "
            "and opens a CI workflow PR when needed. "
            "Serve remains localhost/tunnel admin — not a public multi-user console. "
            f"OAuth scopes: {GITHUB_OAUTH_SCOPES}."
        )

    def _request_port(self, request: Request) -> int:
        host = request.headers.get("host") or ""
        if ":" in host:
            try:
                return int(host.rsplit(":", 1)[-1])
            except ValueError:
                pass
        return self._port

    @staticmethod
    def _oauth_error_redirect(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"/deploy?oauth_error={quote(message, safe='')}",
            status_code=302,
        )

    @staticmethod
    def _http(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
