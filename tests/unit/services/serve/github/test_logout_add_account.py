"""TDD: logout removes accounts; add-account login keeps peers + shows picker."""

from __future__ import annotations

import json
import time
from typing import Optional
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory
from raft.services.serve.github.accounts import GithubAccountStore
from raft.services.serve.github.api import ServeGithubApi
from raft.services.serve.github.strategies.mock import MockGithubProvider
from raft.services.serve.paths import ServePaths

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.services.serve.github import fixtures as github_fx


class TestLogoutAndAddAccount(RaftTestCase):
    def test_logout_expired_account_removed_from_disk(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        expired = store.upsert_account(
            github_fx.sample_account(
                id="demo-expired",
                login="demo-user",
                access_token="dead-token",
                mock=False,
                expires_at=time.time() - 30,
                github_user_id="42",
            )
        )
        client = self._client()
        out = client.post(f"/api/github/accounts/{expired.id}/logout").json()
        assert out["accounts"] == []
        assert out["active_account_id"] is None
        assert out["authenticated"] is False
        disk = json.loads(
            (self.tmp_path / "state" / "serve" / "github-accounts.json").read_text(
                encoding="utf-8"
            )
        )
        assert disk["accounts"] == []
        assert disk["active_account_id"] is None
        assert store.public_snapshot()["accounts"] == []

    def test_logout_one_of_two_falls_back_active(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        first = store.upsert_account(
            github_fx.sample_account(
                id="a1",
                login="demo-alice",
                access_token="tok-a",
                mock=False,
                github_user_id="1",
            )
        )
        store.upsert_account(
            github_fx.sample_account(
                id="a2",
                login="demo-bob",
                access_token="tok-b",
                mock=False,
                github_user_id="2",
            )
        )
        client = self._client()
        out = client.post(f"/api/github/accounts/{first.id}/logout").json()
        assert [a["login"] for a in out["accounts"]] == ["demo-bob"]
        assert out["active_account_id"] == "a2"
        assert store.active_usable() is not None
        assert store.active_usable().login == "demo-bob"

    def test_add_login_uses_select_account_prompt(self) -> None:
        self.write_home_settings(
            "edge: {http: 80}\n"
            "github: {mock: false, clientId: cid, clientSecret: csec}\n"
        )
        client = self._client(settings=None)
        login = client.get("/api/github/login?add=1", follow_redirects=False)
        assert login.status_code == 302
        loc = login.headers["location"]
        assert "github.com/login/oauth/authorize" in loc
        query = parse_qs(urlparse(loc).query)
        assert query.get("prompt") == ["select_account"]
        assert "state" in query

    def test_add_login_when_accounts_exist_forces_picker(self) -> None:
        self.write_home_settings(
            "edge: {http: 80}\n"
            "github: {mock: false, clientId: cid, clientSecret: csec}\n"
        )
        GithubAccountStore(self.tmp_path).upsert_account(
            github_fx.sample_account(
                id="kept",
                login="demo-user",
                access_token="dead",
                mock=False,
                expires_at=time.time() - 5,
                github_user_id="9",
            )
        )
        client = self._client(settings=None)
        login = client.get("/api/github/login", follow_redirects=False)
        assert login.status_code == 302
        query = parse_qs(urlparse(login.headers["location"]).query)
        assert query.get("prompt") == ["select_account"]

    def test_mock_add_callback_keeps_existing_and_appends(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        store.upsert_account(
            github_fx.sample_account(
                id="kept",
                login="demo-user",
                access_token="dead",
                mock=False,
                expires_at=time.time() - 5,
                github_user_id="9",
            )
        )
        client = self._client()
        login = client.get("/api/github/login?add=1", follow_redirects=False)
        assert login.status_code == 302
        assert "add=1" in login.headers["location"]
        parsed = urlparse(login.headers["location"])
        cb = client.get(f"{parsed.path}?{parsed.query}", follow_redirects=False)
        assert cb.status_code == 302 and cb.headers["location"] == "/deploy"
        session = client.get("/api/github/session").json()
        logins = {a["login"] for a in session["accounts"]}
        assert "demo-user" in logins
        assert any(name.startswith("mock-operator") for name in logins)
        assert len(session["accounts"]) == 2
        assert len(store.public_snapshot()["accounts"]) == 2

    def _client(self, *, settings: Optional[str] = "") -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        if settings is not None:
            body = settings or (
                "edge: {http: 80, https: null}\ngithub: {mock: true}\n"
            )
            self.write_home_settings(body)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        github = ServeGithubApi(
            stack,
            provider=MockGithubProvider(ServePaths.mock_github_dir()),
            port=8787,
        )
        return TestClient(ServeAppFactory(stack, status=status, github=github).create())
