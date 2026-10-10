"""OAuth helpers + github settings parser."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from raft.config.settings_github import GithubSettingsParser
from raft.config.settings_types import GithubServeConfig
from raft.errors.cta import OperatorError
from raft.serve.github.account import GithubAccount
from raft.serve.github.accounts import GithubAccountStore
from raft.serve.github.oauth import GithubOauth

from tests.unit.base import RaftTestCase


class TestGithubSettingsParser(RaftTestCase):
    def test_parse_and_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._clear_github_env(monkeypatch)
        p = GithubSettingsParser()
        assert p.parse(None).mock is False
        cfg = p.parse({"mock": True, "sessionTtlSeconds": 120})
        assert cfg.mock is True and cfg.session_ttl_seconds == 120
        with pytest.raises(OperatorError):
            p.parse([])
        with pytest.raises(OperatorError):
            p.parse({"sessionTtlSeconds": 10})
        self._set_github_env(monkeypatch)
        env_cfg = p.parse({"mock": False})
        assert env_cfg.mock is True
        assert env_cfg.client_id == "id"
        assert env_cfg.session_ttl_seconds == 90

    @staticmethod
    def _clear_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "RAFT_GITHUB_MOCK",
            "RAFT_GITHUB_CLIENT_ID",
            "RAFT_GITHUB_CLIENT_SECRET",
            "RAFT_GITHUB_SESSION_TTL_SECONDS",
        ):
            monkeypatch.delenv(key, raising=False)

    @staticmethod
    def _set_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_GITHUB_MOCK", "1")
        monkeypatch.setenv("RAFT_GITHUB_CLIENT_ID", "id")
        monkeypatch.setenv("RAFT_GITHUB_CLIENT_SECRET", "sec")
        monkeypatch.setenv("RAFT_GITHUB_SESSION_TTL_SECONDS", "90")


class TestGithubOauth(RaftTestCase):
    def test_mock_login_and_url(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        oauth = GithubOauth(GithubServeConfig(mock=True), store)
        assert "callback?mock=1" in oauth.login_url(port=8787)
        account = oauth.complete_mock()
        assert account.login == "mock-operator" and account.mock is True

    def test_oauth_requires_creds(self) -> None:
        store = self._store_with_kept()
        bare = GithubOauth(GithubServeConfig(mock=False), store)
        with pytest.raises(OperatorError, match="not configured"):
            bare.login_url(port=8787)

    def test_oauth_preserves_accounts_on_add(self) -> None:
        store = self._store_with_kept()
        oauth = GithubOauth(
            GithubServeConfig(mock=False, client_id="id", client_secret="sec"),
            store,
        )
        assert "github.com/login/oauth/authorize" in oauth.login_url(port=8787)
        assert store.public_snapshot()["login"] == "kept"
        with pytest.raises(OperatorError, match="state mismatch"):
            oauth.complete_oauth(code="c", state="wrong")
        done = self._complete(oauth, store.get_pending().state)
        snap = store.public_snapshot()
        assert {a["login"] for a in snap["accounts"]} == {"kept", "alice"}
        assert snap["active_account_id"] == done.id

    def test_token_from_payload(self) -> None:
        with pytest.raises(OperatorError, match="access_token"):
            GithubOauth._token_from_payload({})
        assert GithubOauth._token_from_payload({"access_token": "x"}) == "x"

    def _store_with_kept(self) -> GithubAccountStore:
        store = GithubAccountStore(self.tmp_path)
        store.upsert_account(
            GithubAccount(
                id="keep",
                login="kept",
                access_token="keep-tok",
                mock=False,
                expires_at=9_999_999_999,
                github_user_id="9",
            )
        )
        return store

    @staticmethod
    def _complete(oauth: GithubOauth, state: str):
        with patch.object(oauth, "_exchange_code", return_value="tok"), patch.object(
            oauth, "_fetch_user", return_value=("alice", "42")
        ):
            done = oauth.complete_oauth(code="c", state=state)
        assert done.login == "alice" and done.access_token == "tok"
        return done
