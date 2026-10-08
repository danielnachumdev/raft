"""GitHub OAuth App helpers + mock login (localhost callback)."""

from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

from raft.config.settings_types import GithubServeConfig
from raft.errors.cta import OperatorError

from .session import GithubSession, GithubSessionStore

# Least privilege for private listing + Contents/PRs that add Actions workflows.
# Deploy keys stay manual (no admin:public_key). ``workflow`` is required to
# create or update ``.github/workflows/*`` via the API.
GITHUB_OAUTH_SCOPES = "read:user repo workflow"
_AUTHORIZE = "https://github.com/login/oauth/authorize"
_TOKEN = "https://github.com/login/oauth/access_token"
_USER = "https://api.github.com/user"
_UA = "raft-serve-github-v1"


class GithubOauth:
    """Build authorize URLs and exchange codes (or mint a mock session)."""

    def __init__(self, cfg: GithubServeConfig, store: GithubSessionStore) -> None:
        self._cfg = cfg
        self._store = store

    @property
    def mock_enabled(self) -> bool:
        return self._cfg.mock

    def login_url(self, *, port: int, redirect_path: str = "/api/github/callback") -> str:
        if self._cfg.mock:
            return f"http://127.0.0.1:{port}/api/github/callback?mock=1"
        self._require_oauth_creds()
        state = self._store.mint_oauth_state()
        pending = GithubSession(
            access_token="",
            login="",
            mock=False,
            expires_at=time.time() + 600,
            state=state,
        )
        self._store.save(pending)
        params = {
            "client_id": self._cfg.client_id,
            "redirect_uri": f"http://127.0.0.1:{port}{redirect_path}",
            "scope": GITHUB_OAUTH_SCOPES,
            "state": state,
        }
        return f"{_AUTHORIZE}?{urlencode(params)}"

    def complete_mock(self) -> GithubSession:
        if not self._cfg.mock:
            raise OperatorError(
                "mock GitHub login is disabled.\n"
                "Fix: set github.mock: true in settings.yaml or RAFT_GITHUB_MOCK=1",
                has_fix=False,
            )
        session = GithubSession(
            access_token=f"mock-{secrets.token_hex(8)}",
            login="mock-operator",
            mock=True,
            expires_at=time.time() + self._cfg.session_ttl_seconds,
        )
        self._store.save(session)
        return session

    def complete_oauth(self, *, code: str, state: str) -> GithubSession:
        self._require_oauth_creds()
        pending = self._store.load()
        if pending is None or not pending.state or pending.state != state:
            raise OperatorError(
                "OAuth state mismatch or expired.\n"
                "Fix: start login again from raft serve → Add new service",
                has_fix=False,
            )
        token = self._exchange_code(code)
        login = self._fetch_login(token)
        session = GithubSession(
            access_token=token,
            login=login,
            mock=False,
            expires_at=time.time() + self._cfg.session_ttl_seconds,
        )
        self._store.save(session)
        return session

    def _exchange_code(self, code: str) -> str:
        req = self._token_request(code)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise OperatorError(
                f"GitHub token exchange failed HTTP {exc.code}.\n"
                f"Fix: check clientId/clientSecret and callback URL",
                has_fix=False,
            ) from exc
        return self._token_from_payload(data)

    def _token_request(self, code: str) -> urllib.request.Request:
        body = urlencode(
            {
                "client_id": self._cfg.client_id,
                "client_secret": self._cfg.client_secret,
                "code": code,
            }
        ).encode("utf-8")
        return urllib.request.Request(
            _TOKEN,
            data=body,
            headers={
                "Accept": "application/json",
                "User-Agent": _UA,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

    @staticmethod
    def _token_from_payload(data: object) -> str:
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise OperatorError(
                "GitHub did not return an access_token.\n"
                "Fix: verify the OAuth App callback is "
                "http://127.0.0.1:<port>/api/github/callback",
                has_fix=False,
            )
        return str(token)

    def _fetch_login(self, token: str) -> str:
        req = urllib.request.Request(
            _USER,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": _UA,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        login = data.get("login") if isinstance(data, dict) else None
        if not login:
            raise OperatorError(
                "GitHub /user did not return login.\nFix: re-login from raft serve",
                has_fix=False,
            )
        return str(login)

    def _require_oauth_creds(self) -> None:
        if self._cfg.client_id and self._cfg.client_secret:
            return
        raise OperatorError(
            "GitHub OAuth is not configured.\n"
            "Fix: set github.clientId + github.clientSecret in ~/.raft/settings.yaml "
            "(or RAFT_GITHUB_CLIENT_ID / RAFT_GITHUB_CLIENT_SECRET), "
            "or enable mock mode (github.mock: true / RAFT_GITHUB_MOCK=1)",
            has_fix=False,
        )
