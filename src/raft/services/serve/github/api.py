"""FastAPI handlers for GitHub login / repos / deploy (thin over assist)."""

from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import Body, HTTPException, Request
from fastapi.responses import RedirectResponse

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.platform.github import (
    DeployJobStore,
    GithubAssistService,
    GithubProvider,
)


class ServeGithubApi:
    """HTTP adapter over ``GithubAssistService`` (redirects stay here)."""

    def __init__(
        self,
        stack: Stack,
        *,
        provider: Optional[GithubProvider] = None,
        jobs: Optional[DeployJobStore] = None,
        port: int = 8787,
        assist: Optional[GithubAssistService] = None,
    ) -> None:
        self.stack = stack
        self._port = port
        self._assist = assist or GithubAssistService(
            stack, provider=provider, jobs=jobs, port=port
        )

    def register(self, app) -> None:
        app.get("/api/github/session")(self.api_session)
        app.get("/api/github/config")(self.api_config)
        app.post("/api/github/config")(self.api_save_config)
        app.get("/api/github/login")(self.api_login)
        app.get("/api/github/callback")(self.api_callback)
        app.post("/api/github/logout")(self.api_logout)
        app.post("/api/github/accounts/select")(self.api_select_account)
        app.delete("/api/github/accounts/{account_id}")(self.api_delete_account)
        app.post("/api/github/accounts/{account_id}/delete")(self.api_delete_account)
        app.post("/api/github/accounts/{account_id}/logout")(self.api_delete_account)
        app.get("/api/github/repos")(self.api_repos)
        app.post("/api/github/deploy")(self.api_deploy)
        app.get("/api/github/deploy/{job_id}")(self.api_deploy_status)

    def api_session(self) -> Dict[str, Any]:
        return self._assist.session(port=self._port)

    def api_config(self, request: Request) -> Dict[str, Any]:
        return self._assist.config(port=self._request_port(request))

    def api_save_config(
        self, request: Request, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        del request
        try:
            return self._assist.save_config(
                client_id=body.get("clientId") or body.get("client_id"),
                client_secret=body.get("clientSecret") or body.get("client_secret"),
            )
        except OperatorError as exc:
            raise self._http(exc) from exc

    def api_login(
        self, request: Request, add: Optional[str] = None
    ) -> RedirectResponse:
        port = self._request_port(request)
        try:
            url = self._assist.login_url(port=port, add=self._truthy(add))
        except OperatorError as exc:
            return self._oauth_error_redirect(str(exc))
        return RedirectResponse(url, status_code=302)

    def api_callback(
        self,
        request: Request,
        code: Optional[str] = None,
        state: Optional[str] = None,
        mock: Optional[str] = None,
        add: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
    ) -> RedirectResponse:
        del request
        if error:
            msg = error_description or error
            return self._oauth_error_redirect(f"GitHub authorization failed: {msg}")
        try:
            self._assist.complete_callback(
                code=code, state=state, mock=mock, add=add
            )
        except OperatorError as exc:
            return self._oauth_error_redirect(str(exc))
        return RedirectResponse("/deploy", status_code=302)

    def api_logout(self) -> Dict[str, Any]:
        return self._assist.logout_active()

    def api_select_account(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        account_id = str(body.get("account_id") or "").strip()
        if not account_id:
            raise HTTPException(status_code=400, detail="account_id is required")
        try:
            return self._assist.select_account(account_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"GitHub account '{account_id}' not found"
            ) from exc

    def api_delete_account(self, account_id: str) -> Dict[str, Any]:
        try:
            return self._assist.delete_account(account_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"GitHub account '{account_id}' not found"
            ) from exc

    def api_repos(self, q: str = "") -> Dict[str, Any]:
        try:
            return self._assist.repos(query=q)
        except OperatorError as exc:
            raise self._http(exc) from exc

    def api_deploy(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        full_name = str(body.get("full_name") or "").strip()
        ref = str(body.get("ref") or "").strip()
        try:
            return self._assist.start_deploy(full_name=full_name, ref=ref)
        except OperatorError as exc:
            raise self._http(exc) from exc

    def api_deploy_status(self, job_id: str) -> Dict[str, Any]:
        try:
            return self._assist.deploy_status(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"deploy job '{job_id}' not found"
            ) from exc
        except OperatorError as exc:
            raise self._http(exc) from exc

    def _request_port(self, request: Request) -> int:
        host = request.headers.get("host") or ""
        if ":" in host:
            try:
                return int(host.rsplit(":", 1)[-1])
            except ValueError:
                pass
        return self._port

    @staticmethod
    def _truthy(value: Optional[str]) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes"}

    @staticmethod
    def _oauth_error_redirect(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"/deploy?oauth_error={quote(message, safe='')}",
            status_code=302,
        )

    @staticmethod
    def _http(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
