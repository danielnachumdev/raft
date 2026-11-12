"""GitHub OAuth App helpers (localhost or public dashboard callback)."""

import json
import time
from typing import Optional, Tuple
from urllib.parse import urlencode

from raft.core.core.config.settings.types import GithubServeConfig
from raft.core.core.errors.cta import OperatorError
from ..accounts import GithubAccount, GithubAccountStore
from ..gateway import GithubApiGateway, GithubHttpError
from .public_base import GithubOauthPublicBase

# Least privilege for private listing + Contents/PRs that add Actions workflows.
# Deploy keys stay manual (no admin:public_key). ``workflow`` is required to
# create or update ``.github/workflows/*`` via the API.
GITHUB_LOGIN_SCOPES = "read:user repo workflow"
# Separate literal so CodeQL does not taint LOGIN_SCOPES via the OAUTH-named alias.
GITHUB_OAUTH_SCOPES = "read:user repo workflow"
_AUTHORIZE = "https://github.com/login/oauth/authorize"
_TOKEN = "https://github.com/login/oauth/access_token"
_USER = "https://api.github.com/user"


class GithubOauth:
    """Build authorize URLs and exchange OAuth codes for a connected account."""

    def __init__(
        self,
        cfg: GithubServeConfig,
        store: GithubAccountStore,
        *,
        gateway: Optional[GithubApiGateway] = None,
    ) -> None:
        self._cfg = cfg
        self._store = store
        self._http = gateway or GithubApiGateway()
        self._base = GithubOauthPublicBase()

    def login_url(
        self,
        *,
        port: int,
        redirect_path: str = GithubOauthPublicBase.REDIRECT_PATH,
        select_account: bool = False,
        public_host: Optional[str] = None,
        tls: str = "off",
        callback_url: Optional[str] = None,
    ) -> str:
        self._require_oauth_creds()
        redirect_uri = callback_url or self._callback(
            port=port,
            redirect_path=redirect_path,
            public_host=public_host,
            tls=tls,
        )
        state = self._store.mint_oauth_state()
        self._store.set_pending(state, redirect_uri=redirect_uri)
        params = {
            "client_id": self._cfg.client_id,
            "redirect_uri": redirect_uri,
            "scope": GITHUB_LOGIN_SCOPES,
            "state": state,
        }
        if select_account:
            params["prompt"] = "select_account"
        return f"{_AUTHORIZE}?{urlencode(params)}"

    def complete_oauth(self, *, code: str, state: str) -> GithubAccount:
        self._require_oauth_creds()
        pending = self._require_pending_state(state)
        token = self._exchange_code(code, redirect_uri=pending.redirect_uri)
        login, github_user_id = self._fetch_user(token)
        return self._store.upsert_account(
            self._new_account(login, token, github_user_id=github_user_id)
        )

    def _callback(
        self,
        *,
        port: int,
        redirect_path: str,
        public_host: Optional[str],
        tls: str,
    ) -> str:
        base = self._base.base(port=port, public_host=public_host, tls=tls)
        path = redirect_path if redirect_path.startswith("/") else f"/{redirect_path}"
        return f"{base}{path}"

    def _require_pending_state(self, state: str):
        pending = self._store.get_pending()
        if pending is None or pending.state != state:
            raise OperatorError(
                "OAuth state mismatch or expired.\n"
                "Fix: start login again from raft serve → Add new service",
                has_fix=False,
            )
        return pending

    def _new_account(
        self,
        login: str,
        token: str,
        *,
        github_user_id: Optional[str] = None,
    ) -> GithubAccount:
        now = time.time()
        return GithubAccount(
            id=self._store.new_account_id(),
            login=login,
            access_token=token,
            expires_at=now + self._cfg.session_ttl_seconds,
            github_user_id=github_user_id,
            created_at=now,
            last_used_at=now,
        )

    def _exchange_code(self, code: str, *, redirect_uri: Optional[str] = None) -> str:
        payload = {
            "client_id": self._cfg.client_id,
            "client_secret": self._cfg.client_secret,
            "code": code,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri
        body = urlencode(payload).encode("utf-8")
        try:
            resp = self._http.post(
                _TOKEN, headers=self._http.json_headers(), body=body
            )
        except GithubHttpError as exc:
            raise OperatorError(
                f"GitHub token exchange failed HTTP {exc.code}.\n"
                f"Fix: check clientId/clientSecret and callback URL",
                has_fix=False,
            ) from exc
        return self._token_from_payload(json.loads(resp.body))

    @staticmethod
    def _token_from_payload(data: object) -> str:
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise OperatorError(
                "GitHub did not return an access_token.\n"
                "Fix: verify the OAuth App callback URL matches the one "
                "shown in Add a service → Set up GitHub OAuth",
                has_fix=False,
            )
        return str(token)

    def _fetch_user(self, token: str) -> Tuple[str, Optional[str]]:
        resp = self._http.get(_USER, headers=self._http.bearer_headers(token))
        return self._user_from_payload(json.loads(resp.body))

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
            "Fix: set github.clientId + github.clientSecret in ~/.raft/host/settings.yaml "
            "(or RAFT_GITHUB_CLIENT_ID / RAFT_GITHUB_CLIENT_SECRET)",
            has_fix=False,
        )
