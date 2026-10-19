"""Shared GitHub OAuth / accounts / deploy-assist (serve + CLI)."""

from typing import Any, Dict, Optional

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack

from .accounts import GithubAccountStore, GithubActiveResolver
from .deploy import DeployJobStore, GithubDeployRunner
from .oauth import GITHUB_OAUTH_SCOPES, GithubOauth, GithubSettingsWriter
from .providers import GithubProvider, GithubRepo, RealGithubProvider


class GithubAssistService:
    """Product rules for GitHub config, session, repos, and deploy jobs."""

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
        self._accounts = GithubAccountStore(stack.root)
        self._active = GithubActiveResolver(self._accounts)
        self._provider_override = provider
        self._jobs = jobs or DeployJobStore()
        self._cfg = SettingsLoader().load(stack.root).github
        self._oauth = GithubOauth(self._cfg, self._accounts)
        self._provider = provider or self._default_provider()
        self._runner = GithubDeployRunner(stack, self._provider, self._jobs)

    def session(self, *, port: Optional[int] = None) -> Dict[str, Any]:
        bind = self._port if port is None else port
        base = self._settings.public_status(port=bind)
        base["scopes"] = GITHUB_OAUTH_SCOPES
        base["hint"] = self._login_hint()
        base.update(self._accounts.public_snapshot())
        return base

    def config(self, *, port: Optional[int] = None) -> Dict[str, Any]:
        bind = self._port if port is None else port
        out = self._settings.public_status(port=bind)
        out["scopes"] = GITHUB_OAUTH_SCOPES
        return out

    def save_config(
        self,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        cfg = self._settings.save(client_id=client_id, client_secret=client_secret)
        self._reload(cfg)
        out = self.config()
        out["ok"] = True
        out["reloaded"] = True
        return out

    def login_url(self, *, port: Optional[int] = None, add: bool = False) -> str:
        bind = self._port if port is None else port
        select = add or bool(self._accounts.public_snapshot().get("accounts"))
        return self._oauth.login_url(port=bind, select_account=select)

    def complete_oauth(self, *, code: str, state: str) -> Dict[str, Any]:
        account = self._oauth.complete_oauth(code=code, state=state)
        return {"ok": True, "account": account.to_public()}

    def complete_callback(
        self,
        *,
        code: Optional[str] = None,
        state: Optional[str] = None,
    ) -> None:
        if not code or not state:
            raise OperatorError(
                "OAuth callback missing code/state.\nFix: start login again",
                has_fix=False,
            )
        self._oauth.complete_oauth(code=code, state=state)

    def logout_active(self) -> Dict[str, Any]:
        self._accounts.delete_active()
        return self.session()

    def select_account(self, account_id: str) -> Dict[str, Any]:
        self._accounts.select(account_id)
        return self.session()

    def delete_account(self, account_id: str) -> Dict[str, Any]:
        self._accounts.delete(account_id)
        return self.session()

    def repos(self, *, query: str = "") -> Dict[str, Any]:
        account = self._active.require()
        rows = self._provider.list_repos(account.access_token, query=query)
        return {"repos": [self._repo_row(r) for r in rows]}

    def start_deploy(
        self, *, full_name: str, ref: str = ""
    ) -> Dict[str, Any]:
        account = self._active.require()
        name = full_name.strip()
        if not name or "/" not in name:
            raise OperatorError(
                "full_name is required (owner/repo).\n"
                "Fix: raft github deploy owner/repo",
                has_fix=False,
            )
        repo = self._resolve_repo(account.access_token, name)
        job = self._runner.start(account, repo, ref.strip() or repo.default_branch)
        return job.to_dict()

    def deploy_status(self, job_id: str) -> Dict[str, Any]:
        self._active.require()
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job.to_dict()

    def _resolve_repo(self, token: str, full_name: str) -> GithubRepo:
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

    def _default_provider(self) -> GithubProvider:
        return RealGithubProvider()

    def _reload(self, cfg) -> None:
        self._cfg = cfg
        self._oauth = GithubOauth(cfg, self._accounts)
        self._provider = self._provider_override or self._default_provider()
        self._runner = GithubDeployRunner(self.stack, self._provider, self._jobs)

    def _login_hint(self) -> str:
        if not GithubSettingsWriter.oauth_ready(self._cfg):
            return (
                "GitHub OAuth is not configured. Create an OAuth App, save "
                "client id/secret (settings.yaml or raft github config save), "
                "then continue."
            )
        return (
            "Temporary GitHub login lists repos you own or belong to, then raft "
            "drives apply. Serve remains localhost/tunnel admin. "
            f"OAuth scopes: {GITHUB_OAUTH_SCOPES}."
        )

    @staticmethod
    def _repo_row(repo: GithubRepo) -> Dict[str, Any]:
        return {
            "full_name": repo.full_name,
            "name": repo.name,
            "owner": repo.owner,
            "private": repo.private,
            "default_branch": repo.default_branch,
            "html_url": repo.html_url,
        }
