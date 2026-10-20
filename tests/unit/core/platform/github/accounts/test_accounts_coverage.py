"""Coverage edges for GithubAccountStore / account model / API select."""

from __future__ import annotations

import json
import time
from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.http.app import ServeAppFactory
from raft.core.platform.github.accounts import GithubAccount
from raft.core.platform.github.accounts import GithubPendingOauth
from raft.core.platform.github.accounts import GithubAccountStore
from raft.services.serve.github.api import ServeGithubApi
from raft.core.platform.github.oauth import GithubOauth

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestAccountsCoverage(RaftTestCase):
    def test_model_and_pending_edges(self) -> None:
        assert GithubAccount.from_raw(["x"]) is None
        assert GithubPendingOauth.from_raw(["x"]) is None
        assert GithubPendingOauth.from_raw({"state": "s"}) is None
        pending = GithubPendingOauth(state="s", expires_at=time.time() - 1)
        assert pending.is_expired() is True
        with pytest.raises(OperatorError, match="login"):
            GithubOauth._user_from_payload(["no"])

    def test_store_select_delete_edges(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        store.touch_active()
        store.delete_active()
        with pytest.raises(KeyError):
            store.select("missing")
        with pytest.raises(KeyError):
            store.delete("missing")
        a = store.upsert_account(self._acct("a", "alice", "t1", uid="1"))
        b = store.upsert_account(self._acct("b", "bob", "t2", uid="2"))
        store.select(a.id)
        store.delete(b.id)
        assert store.public_snapshot()["active_account_id"] == a.id
        store._unlink(self.tmp_path / "state" / "serve" / "missing.json")

    def test_store_upsert_match(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        a = store.upsert_account(self._acct("a", "alice", "t1", uid="1"))
        store.upsert_account(self._acct("b2", "bob", "t2b", uid="2"))
        store.delete_active()
        again = store.upsert_account(self._acct("a2", "alice", "t3", uid="1"))
        assert again.id == a.id and again.access_token == "t3"
        by_login = store.upsert_account(self._acct("c", "alice", "t4"))
        assert by_login.id == a.id
        store.set_pending("st", ttl_seconds=-1)
        assert store.get_pending() is None

    def test_legacy_mock_field_loads_without_mock_key(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        store.upsert_account(self._acct("a", "alice", "t1", uid="1"))
        raw_path = self.tmp_path / "state" / "serve" / "github-accounts.json"
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        data["accounts"].append(self._legacy_mock_row())
        raw_path.write_text(json.dumps(data), encoding="utf-8")
        snap = store.public_snapshot()
        assert any(a["login"] == "legacy-user" for a in snap["accounts"])
        assert all("mock" not in a for a in snap["accounts"])

    @staticmethod
    def _legacy_mock_row() -> dict:
        return {
            "id": "legacy",
            "login": "legacy-user",
            "access_token": "tok",
            "mock": True,
            "expires_at": time.time() + 60,
        }

    def test_orphan_active_falls_back(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        accounts = self.tmp_path / "state" / "serve" / "github-accounts.json"
        accounts.parent.mkdir(parents=True, exist_ok=True)
        accounts.write_text(json.dumps(self._orphan_payload()), encoding="utf-8")
        assert store.public_snapshot()["active_account_id"] == "alive"

    def test_api_select_delete_errors(self) -> None:
        client = self._client()
        assert client.post("/api/github/accounts/select", json={}).status_code == 400
        bad = client.post("/api/github/accounts/select", json={"account_id": "nope"})
        assert bad.status_code == 404
        assert client.delete("/api/github/accounts/nope").status_code == 404

    def _client(self) -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        (self.tmp_path / "settings.yaml").write_text(
            "github: {clientId: id, clientSecret: sec}\n", encoding="utf-8"
        )
        api = ServeGithubApi(stack, provider=MagicMock())
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
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
                    "expires_at": time.time() + 60,
                    "github_user_id": "  ",
                    "created_at": None,
                }
            ],
        }

    @staticmethod
    def _acct(
        account_id: str, login: str, token: str, *, uid: Optional[str] = None
    ) -> GithubAccount:
        return GithubAccount(
            id=account_id,
            login=login,
            access_token=token,
            expires_at=time.time() + 60,
            github_user_id=uid,
        )
