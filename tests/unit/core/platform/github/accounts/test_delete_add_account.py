"""TDD: delete purges durable accounts; add-account login keeps peers + picker."""

import json
import time
from typing import Optional
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from raft.core.observe.ops.status.models import StatusSnapshot
from raft.core.platform.github.accounts import GithubAccountStore
from raft.services.serve.github.api import ServeGithubApi
from raft.services.serve.http.app import ServeAppFactory

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.core.platform.github import fixtures as github_fx


class TestDeleteAndAddAccount(RaftTestCase):
    def test_delete_expired_account_purged_from_disk(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        expired = store.upsert_account(self._expired_sample())
        out = self._client().delete(f"/api/github/accounts/{expired.id}").json()
        self._assert_empty_session(out)
        self._assert_empty_disk_ledger()
        assert store.public_snapshot()["accounts"] == []

    def test_delete_survives_new_store_instance(self) -> None:
        """Serve restart must not resurrect a deleted account (issue #200)."""
        store = GithubAccountStore(self.tmp_path)
        expired = store.upsert_account(self._expired_sample())
        self._client().delete(f"/api/github/accounts/{expired.id}")
        restarted = GithubAccountStore(self.tmp_path)
        snap = restarted.public_snapshot()
        assert snap["accounts"] == []
        assert snap["active_account_id"] is None
        assert restarted.active_usable() is None
        self._assert_empty_disk_ledger()

    def test_delete_one_of_two_falls_back_active(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        first = self._seed_two_accounts(store)
        out = self._client().delete(f"/api/github/accounts/{first.id}").json()
        assert [a["login"] for a in out["accounts"]] == ["demo-bob"]
        assert out["active_account_id"] == "a2"
        assert store.active_usable() is not None
        assert store.active_usable().login == "demo-bob"

    def test_add_login_uses_select_account_prompt(self) -> None:
        self._write_real_github_settings()
        login = self._client(settings=None).get(
            "/api/github/login?add=1", follow_redirects=False
        )
        assert login.status_code == 302
        query = parse_qs(urlparse(login.headers["location"]).query)
        assert "github.com/login/oauth/authorize" in login.headers["location"]
        assert query.get("prompt") == ["select_account"]
        assert "state" in query

    def test_add_login_when_accounts_exist_forces_picker(self) -> None:
        self._write_real_github_settings()
        GithubAccountStore(self.tmp_path).upsert_account(self._expired_kept())
        login = self._client(settings=None).get(
            "/api/github/login", follow_redirects=False
        )
        assert login.status_code == 302
        query = parse_qs(urlparse(login.headers["location"]).query)
        assert query.get("prompt") == ["select_account"]

    def test_oauth_add_callback_keeps_existing_and_appends(self) -> None:
        self._write_real_github_settings()
        store = GithubAccountStore(self.tmp_path)
        store.upsert_account(self._expired_kept())
        state = self._login_add_state()
        cb = self._callback_append_bob(store, state)
        assert cb.status_code == 302
        logins = {a["login"] for a in store.public_snapshot()["accounts"]}
        assert logins == {"demo-user", "demo-bob"}

    def _login_add_state(self) -> str:
        login = self._client(settings=None).get(
            "/api/github/login?add=1", follow_redirects=False
        )
        assert login.status_code == 302
        return parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    def _callback_append_bob(self, store: GithubAccountStore, state: str):
        api = ServeGithubApi(
            StackMakers.make_stack(self.tmp_path), provider=MagicMock(), port=8787
        )
        account = github_fx.sample_account(
            id="new", login="demo-bob", access_token="tok-b", github_user_id="2"
        )
        with patch.object(
            api._assist._oauth,
            "complete_oauth",
            return_value=store.append_account(account),
        ):
            return api.api_callback(MagicMock(), code="c", state=state)

    def _expired_sample(self):
        return github_fx.sample_account(
            id="demo-expired",
            login="demo-user",
            access_token="dead-token",
            expires_at=time.time() - 30,
            github_user_id="42",
        )

    def _expired_kept(self):
        return github_fx.sample_account(
            id="kept",
            login="demo-user",
            access_token="dead",
            expires_at=time.time() - 5,
            github_user_id="9",
        )

    def _seed_two_accounts(self, store: GithubAccountStore):
        first = store.upsert_account(
            github_fx.sample_account(
                id="a1",
                login="demo-alice",
                access_token="tok-a",
                github_user_id="1",
            )
        )
        store.upsert_account(
            github_fx.sample_account(
                id="a2",
                login="demo-bob",
                access_token="tok-b",
                github_user_id="2",
            )
        )
        return first

    def _assert_empty_session(self, out: dict) -> None:
        assert out["accounts"] == []
        assert out["active_account_id"] is None
        assert out["authenticated"] is False

    def _assert_empty_disk_ledger(self) -> None:
        disk = json.loads(
            (self.tmp_path / "state" / "serve" / "github-accounts.json").read_text(
                encoding="utf-8"
            )
        )
        assert disk["accounts"] == []
        assert disk["active_account_id"] is None

    def _write_real_github_settings(self) -> None:
        self.write_home_settings(
            "edge: {http: 80}\n"
            "github: {clientId: cid, clientSecret: csec}\n"
        )

    def _client(self, *, settings: Optional[str] = "") -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        if settings is not None:
            body = settings or (
                "edge: {http: 80, https: null}\n"
                "github: {clientId: cid, clientSecret: csec}\n"
            )
            self.write_home_settings(body)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        github = ServeGithubApi(stack, provider=MagicMock(), port=8787)
        return TestClient(ServeAppFactory(stack, status=status, github=github).create())
