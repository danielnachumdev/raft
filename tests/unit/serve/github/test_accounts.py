"""GithubAccountStore unit tests."""

from __future__ import annotations

import json
import time
from typing import Optional

from raft.serve.github.account import GithubAccount
from raft.serve.github.accounts import GithubAccountStore

from tests.unit.base import RaftTestCase


class TestGithubAccountStore(RaftTestCase):
    def test_upsert_select_logout_and_public(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        first = store.upsert_account(self._acct("a1", "alice", "tok-a"))
        second = store.upsert_account(self._acct("a2", "bob", "tok-b", uid="2"))
        self._assert_ledger_mode(store)
        snap = store.public_snapshot()
        assert snap["authenticated"] is True and snap["login"] == "bob"
        assert snap["active_account_id"] == second.id
        assert len(snap["accounts"]) == 2
        assert "access_token" not in json.dumps(snap)
        store.select(first.id)
        assert store.active_usable().access_token == "tok-a"
        store.logout(first.id)
        assert store.public_snapshot()["active_account_id"] == second.id
        store.logout_active()
        assert store.public_snapshot()["accounts"] == []

    def test_pending_preserves_accounts(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        store.upsert_account(self._acct("a1", "alice", "tok-a"))
        store.set_pending("csrf-state")
        pending = store.get_pending()
        assert pending is not None and pending.state == "csrf-state"
        snap = store.public_snapshot()
        assert len(snap["accounts"]) == 1 and snap["login"] == "alice"
        store.clear_pending()
        assert store.get_pending() is None
        assert store.public_snapshot()["login"] == "alice"

    def test_migrate_legacy_session(self) -> None:
        legacy = self.tmp_path / "state" / "serve" / "github-session.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(self._legacy_payload()), encoding="utf-8")
        store = GithubAccountStore(self.tmp_path)
        snap = store.public_snapshot()
        assert snap["authenticated"] is True and snap["login"] == "carol"
        assert store.active_usable().access_token == "legacy-tok"
        assert not legacy.exists()
        assert (self.tmp_path / "state" / "serve" / "github-accounts.json").is_file()

    def test_expired_kept_not_usable(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        store.upsert_account(
            self._acct("a1", "dave", "tok", expires_at=time.time() - 1)
        )
        snap = store.public_snapshot()
        assert snap["authenticated"] is False
        assert len(snap["accounts"]) == 1
        assert snap["accounts"][0]["expired"] is True
        assert store.active_usable() is None
        assert "access_token" not in snap["accounts"][0]

    def test_corrupt_and_bad_raw(self) -> None:
        store = GithubAccountStore(self.tmp_path)
        path = self.tmp_path / "state" / "serve" / "github-accounts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        assert store.public_snapshot()["accounts"] == []
        path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        assert store.public_snapshot()["accounts"] == []
        assert store.mint_oauth_state()
        assert GithubAccount.from_raw({"access_token": 1}) is None

    def _assert_ledger_mode(self, store: GithubAccountStore) -> None:
        path = self.tmp_path / "state" / "serve" / "github-accounts.json"
        assert path.is_file()
        assert oct(path.stat().st_mode & 0o777) == "0o600"
        del store

    @staticmethod
    def _legacy_payload() -> dict:
        return {
            "access_token": "legacy-tok",
            "login": "carol",
            "mock": False,
            "expires_at": time.time() + 120,
        }

    @staticmethod
    def _acct(
        account_id: str,
        login: str,
        token: str,
        *,
        uid: Optional[str] = None,
        expires_at: Optional[float] = None,
    ) -> GithubAccount:
        return GithubAccount(
            id=account_id,
            login=login,
            access_token=token,
            mock=False,
            expires_at=expires_at if expires_at is not None else time.time() + 60,
            github_user_id=uid,
            created_at=time.time(),
        )
