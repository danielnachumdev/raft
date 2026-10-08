"""OAuth helpers + github settings parser."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from raft.config.settings_github import GithubSettingsParser
from raft.config.settings_types import GithubServeConfig
from raft.errors.cta import OperatorError
from raft.services.serve.github.oauth import GithubOauth
from raft.services.serve.github.session import GithubSessionStore

from ....base import RaftTestCase


class TestGithubSettingsParser(RaftTestCase):
    def test_parse_and_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        p = GithubSettingsParser()
        assert p.parse(None).mock is False
        cfg = p.parse({"mock": True, "sessionTtlSeconds": 120})
        assert cfg.mock is True and cfg.session_ttl_seconds == 120
        with pytest.raises(OperatorError):
            p.parse([])
        with pytest.raises(OperatorError):
            p.parse({"sessionTtlSeconds": 10})
        monkeypatch.setenv("RAFT_GITHUB_MOCK", "1")
        monkeypatch.setenv("RAFT_GITHUB_CLIENT_ID", "id")
        monkeypatch.setenv("RAFT_GITHUB_CLIENT_SECRET", "sec")
        monkeypatch.setenv("RAFT_GITHUB_SESSION_TTL_SECONDS", "90")
        env_cfg = p.parse({"mock": False})
        assert env_cfg.mock is True
        assert env_cfg.client_id == "id"
        assert env_cfg.session_ttl_seconds == 90


class TestGithubOauth(RaftTestCase):
    def test_mock_login_and_url(self) -> None:
        store = GithubSessionStore(self.tmp_path)
        oauth = GithubOauth(GithubServeConfig(mock=True), store)
        assert "callback?mock=1" in oauth.login_url(port=8787)
        session = oauth.complete_mock()
        assert session.login == "mock-operator" and session.mock is True

    def test_oauth_requires_creds_and_state(self) -> None:
        store = GithubSessionStore(self.tmp_path)
        bare = GithubOauth(GithubServeConfig(mock=False), store)
        with pytest.raises(OperatorError, match="not configured"):
            bare.login_url(port=8787)
        oauth = GithubOauth(
            GithubServeConfig(mock=False, client_id="id", client_secret="sec"),
            store,
        )
        assert "github.com/login/oauth/authorize" in oauth.login_url(port=8787)
        with pytest.raises(OperatorError, match="state mismatch"):
            oauth.complete_oauth(code="c", state="wrong")
        pending = store.load()
        assert pending is not None and pending.state
        with patch.object(oauth, "_exchange_code", return_value="tok"), patch.object(
            oauth, "_fetch_login", return_value="alice"
        ):
            done = oauth.complete_oauth(code="c", state=pending.state)
        assert done.login == "alice" and done.access_token == "tok"

    def test_token_from_payload(self) -> None:
        with pytest.raises(OperatorError, match="access_token"):
            GithubOauth._token_from_payload({})
        assert GithubOauth._token_from_payload({"access_token": "x"}) == "x"
