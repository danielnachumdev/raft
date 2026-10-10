"""GitHub OAuth App helpers + mock login (localhost callback)."""

from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple
from urllib.parse import urlencode

from raft.config.settings_types import GithubServeConfig
from raft.errors.cta import OperatorError

from .account import GithubAccount
from .accounts import GithubAccountStore

# Least privilege for private listing + Contents/PRs that add Actions workflows.
# Deploy keys stay manual (no admin:public_key). ``workflow`` is required to
# create or update ``.github/workflows/*`` via the API.
GITHUB_OAUTH_SCOPES = "read:user repo workflow"
_AUTHORIZE = "https://github.com/login/oauth/authorize"
_TOKEN = "https://github.com/login/oauth/access_token"
_USER = "https://api.github.com/user"
_UA = "raft-serve-github-v1"


class GithubOauth:
    """Build authorize URLs and exchange codes (or mint a mock account)."""

    def __init__(self, cfg: GithubServeConfig, store: GithubAccountStore) -> None:
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
        self._store.set_pending(state)
        params = {
            "client_id": self._cfg.client_id,
            "redirect_uri": f"http://127.0.0.1:{port}{redirect_path}",
            "scope": GITHUB_OAUTH_SCOPES,
            "state": state,
        }
        return f"{_AUTHORIZE}?{urlencode(params)}"

    def complete_mock(self) -> GithubAccount:
        if not self._cfg.mock:
            raise OperatorError(
                "mock GitHub login is disabled.\n"
                "Fix: set github.mock: true in settings.yaml or RAFT_GITHUB_MOCK=1",
                has_fix=False,
            )
        return self._store.upsert_account(
            self._new_account(
                "mock-operator",
                f"mock-{secrets.token_hex(8)}",
                mock=True,
            )
        )

    def complete_oauth(self, *, code: str, state: str) -> GithubAccount:
        self._require_oauth_creds()
        self._require_pending_state(state)
        token = self._exchange_code(code)
        login, github_user_id = self._fetch_user(token)
        return self._store.upsert_account(
            self._new_account(login, token, github_user_id=github_user_id)
        )

    def _require_pending_state(self, state: str) -> None:
        pending = self._store.get_pending()
        if pending is None or pending.state != state:
            raise OperatorError(
                "OAuth state mismatch or expired.\n"
                "Fix: start login again from raft serve → Add new service",
                has_fix=False,
            )

    def _new_account(
        self,
        login: str,
        token: str,
        *,
        github_user_id: Optional[str] = None,
        mock: bool = False,
    ) -> GithubAccount:
        now = time.time()
        return GithubAccount(
            id=self._store.new_account_id(),
            login=login,
            access_token=token,
            mock=mock,
            expires_at=now + self._cfg.session_ttl_seconds,
            github_user_id=github_user_id,
            created_at=now,
            last_used_at=now,
        )

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

    def _fetch_user(self, token: str) -> Tuple[str, Optional[str]]:
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
        return self._user_from_payload(data)

    @staticmethod
    def _user_from_payload(data: object) -> Tuple[str, Optional[str]]:
        if not isinstance(data, dict):
            raise OperatorError(
                "GitHub /user did not return login.\nFix: re-login from raft serve",
                has_fix=False,
            )
        login = data.get("login")
        if not login:
            raise OperatorError(
                "GitHub /user did not return login.\nFix: re-login from raft serve",
                has_fix=False,
            )
        uid = data.get("id")
        return str(login), str(uid) if uid is not None else None

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
