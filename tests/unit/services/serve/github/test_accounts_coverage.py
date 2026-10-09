"""Coverage edges for GithubAccountStore / account model / API select."""

from __future__ import annotations

import json
import time
from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from raft.errors.cta import OperatorError
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory
from raft.services.serve.github.account import GithubAccount, GithubPendingOauth
from raft.services.serve.github.accounts import GithubAccountStore
from raft.services.serve.github.api import ServeGithubApi
from raft.services.serve.github.oauth import GithubOauth
from raft.services.serve.github.provider import MockGithubProvider
from raft.services.serve.paths import ServePaths

from ....base import RaftTestCase, make_stack
from ....services.ops.status.fixtures import StatusFixtures


class TestAccountsCoverage(RaftTestCase):
    def test_model_and_pending_edges(self) -> None:
        assert GithubAccount.from_raw(["x"]) is None
        assert GithubPendingOauth.from_raw(["x"]) is None
        assert GithubPendingOauth.from_raw({"state": "s"}) is None
        pending = GithubPendingOauth(state="s", expires_at=time.time() - 1)
        assert pending.is_expired() is True
        with pytest.raises(OperatorError, match="login"):
            GithubOauth._user_from_payload(["no"])

    def test_store_select_logout_edges(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        store.touch_active()
        store.logout_active()
        with pytest.raises(KeyError):
            store.select("missing")
        with pytest.raises(KeyError):
            store.logout("missing")
        a = store.upsert_account(self._acct("a", "alice", "t1", uid="1"))
        b = store.upsert_account(self._acct("b", "bob", "t2", uid="2"))
        store.select(a.id)
        store.logout(b.id)
        assert store.public_snapshot()["active_account_id"] == a.id
        store._unlink(self.tmp_path / "state" / "serve" / "missing.json")

    def test_store_upsert_match_and_mock(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        a = store.upsert_account(self._acct("a", "alice", "t1", uid="1"))
        store.upsert_account(self._acct("b2", "bob", "t2b", uid="2"))
        store.logout_active()
        again = store.upsert_account(self._acct("a2", "alice", "t3", uid="1"))
        assert again.id == a.id and again.access_token == "t3"
        by_login = store.upsert_account(self._acct("c", "alice", "t4"))
        assert by_login.id == a.id
        store.set_pending("st", ttl_seconds=-1)
        assert store.get_pending() is None
        store.upsert_account(self._mock("m1", "m"))
        store.upsert_account(self._mock("m2", "m2"))
        mocks = [x for x in store.public_snapshot()["accounts"] if x["mock"]]
        assert len(mocks) == 1

    def test_legacy_corrupt_and_empty(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        legacy = self.tmp_path / "state" / "serve" / "github-session.json"
        accounts = self.tmp_path / "state" / "serve" / "github-accounts.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("{bad", encoding="utf-8")
        assert store.public_snapshot()["accounts"] == []
        assert not legacy.exists()
        self._write_legacy(legacy, accounts, ["x"])
        assert store.public_snapshot()["accounts"] == []
        self._write_legacy(
            legacy, accounts, {"access_token": "", "login": "x", "expires_at": 1}
        )
        assert store.public_snapshot()["accounts"] == []

    def test_legacy_missing_expiry_and_orphan_active(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        legacy = self.tmp_path / "state" / "serve" / "github-session.json"
        accounts = self.tmp_path / "state" / "serve" / "github-accounts.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        self._write_legacy(legacy, accounts, {"access_token": "t", "login": "x"})
        assert store.public_snapshot()["accounts"] == []
        accounts.write_text(json.dumps(self._orphan_payload()), encoding="utf-8")
        assert store.public_snapshot()["active_account_id"] == "alive"

    def test_api_select_logout_errors(self) -> None:
        client = self._client()
        assert client.post("/api/github/accounts/select", json={}).status_code == 400
        bad = client.post("/api/github/accounts/select", json={"account_id": "nope"})
        assert bad.status_code == 404
        assert client.post("/api/github/accounts/nope/logout").status_code == 404

    def _client(self) -> TestClient:
        stack = make_stack(self.tmp_path)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {mock: true}\n", encoding="utf-8"
        )
        api = ServeGithubApi(
            stack,
            provider=MockGithubProvider(ServePaths.mock_github_dir()),
        )
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(), containers=()
        )
        return TestClient(ServeAppFactory(stack, status=status, github=api).create())

    @staticmethod
    def _orphan_payload() -> dict:
        return {
            "version": 1,
            "active_account_id": "gone",
            "accounts": [
                {
                    "id": "alive",
                    "login": "z",
                    "access_token": "tok",
                    "mock": False,
                    "expires_at": time.time() + 60,
                    "github_user_id": "  ",
                    "created_at": None,
                }
            ],
        }

    @staticmethod
    def _write_legacy(legacy, accounts, payload) -> None:
        if accounts.is_file():
            accounts.unlink()
        legacy.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _acct(
        account_id: str, login: str, token: str, *, uid: Optional[str] = None
    ) -> GithubAccount:
        return GithubAccount(
            id=account_id,
            login=login,
            access_token=token,
            mock=False,
            expires_at=time.time() + 60,
            github_user_id=uid,
        )

    @staticmethod
    def _mock(account_id: str, token: str) -> GithubAccount:
        return GithubAccount(
            id=account_id,
            login="mock-operator",
            access_token=token,
            mock=True,
            expires_at=time.time() + 60,
        )
