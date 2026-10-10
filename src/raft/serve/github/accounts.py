"""Multi-account GitHub ledger under ``state/serve/`` (mode 0600)."""

from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Optional

from .account import GithubAccount, GithubPendingOauth

ACCOUNTS_FILENAME = "github-accounts.json"
LEGACY_SESSION_FILENAME = "github-session.json"
SESSION_DIR = Path("state") / "serve"
LEDGER_VERSION = 1


class GithubAccountStore:
    """Persists connected GitHub accounts + pending OAuth; never world-readable."""

    def __init__(self, data_home: Path) -> None:
        self._dir = data_home / SESSION_DIR
        self._path = self._dir / ACCOUNTS_FILENAME
        self._legacy = self._dir / LEGACY_SESSION_FILENAME

    def public_snapshot(self) -> dict[str, Any]:
        ledger = self._load_ledger()
        accounts = [a.to_public() for a in ledger["accounts"]]
        active = self._active_from(ledger)
        usable = active is not None and not active.is_expired() and bool(active.access_token)
        out: dict[str, Any] = {
            "authenticated": usable,
            "accounts": accounts,
            "active_account_id": ledger.get("active_account_id"),
        }
        if active is not None:
            out["login"] = active.login
            out["mock"] = active.mock
            out["expires_at"] = active.expires_at
        return out

    def active_usable(self) -> Optional[GithubAccount]:
        account = self._active_from(self._load_ledger())
        if account is None or account.is_expired() or not account.access_token:
            return None
        return account

    def touch_active(self) -> None:
        ledger = self._load_ledger()
        active = self._active_from(ledger)
        if active is None:
            return
        active.last_used_at = time.time()
        self._write_ledger(ledger)

    def set_pending(self, state: str, *, ttl_seconds: float = 600) -> None:
        ledger = self._load_ledger()
        ledger["pending"] = GithubPendingOauth(
            state=state,
            expires_at=time.time() + ttl_seconds,
        )
        self._write_ledger(ledger)

    def get_pending(self) -> Optional[GithubPendingOauth]:
        pending = self._load_ledger().get("pending")
        if pending is None or pending.is_expired():
            return None
        return pending

    def clear_pending(self) -> None:
        ledger = self._load_ledger()
        ledger["pending"] = None
        self._write_ledger(ledger)

    def upsert_account(self, account: GithubAccount) -> GithubAccount:
        ledger = self._load_ledger()
        existing = self._find_match(ledger["accounts"], account)
        if existing is not None:
            self._merge_into(existing, account)
            account = existing
        else:
            ledger["accounts"].append(account)
        ledger["active_account_id"] = account.id
        ledger["pending"] = None
        self._write_ledger(ledger)
        return account

    def select(self, account_id: str) -> GithubAccount:
        ledger = self._load_ledger()
        account = self._by_id(ledger["accounts"], account_id)
        if account is None:
            raise KeyError(account_id)
        ledger["active_account_id"] = account.id
        account.last_used_at = time.time()
        self._write_ledger(ledger)
        return account

    def logout(self, account_id: str) -> None:
        ledger = self._load_ledger()
        before = ledger["accounts"]
        ledger["accounts"] = [a for a in before if a.id != account_id]
        if len(ledger["accounts"]) == len(before):
            raise KeyError(account_id)
        if ledger.get("active_account_id") == account_id:
            ledger["active_account_id"] = self._fallback_active(ledger["accounts"])
        self._write_ledger(ledger)

    def logout_active(self) -> None:
        active_id = self._load_ledger().get("active_account_id")
        if not active_id:
            return
        self.logout(str(active_id))

    def mint_oauth_state(self) -> str:
        return secrets.token_urlsafe(24)

    def new_account_id(self) -> str:
        return secrets.token_urlsafe(12)

    def _load_ledger(self) -> dict[str, Any]:
        self._migrate_legacy()
        if not self._path.is_file():
            return self._empty_ledger()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._unlink(self._path)
            return self._empty_ledger()
        parsed = self._parse_ledger(raw)
        if parsed is None:
            self._unlink(self._path)
            return self._empty_ledger()
        return parsed

    def _migrate_legacy(self) -> None:
        if self._path.is_file() or not self._legacy.is_file():
            return
        try:
            raw = json.loads(self._legacy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._unlink(self._legacy)
            return
        account = self._account_from_legacy(raw)
        ledger = self._empty_ledger()
        if account is not None:
            ledger["accounts"] = [account]
            ledger["active_account_id"] = account.id
        self._write_ledger(ledger)
        self._unlink(self._legacy)

    def _account_from_legacy(self, raw: Any) -> Optional[GithubAccount]:
        if not isinstance(raw, dict):
            return None
        token = str(raw.get("access_token") or "")
        login = str(raw.get("login") or "")
        if not token or not login:
            return None
        try:
            return GithubAccount(
                id=self.new_account_id(),
                login=login,
                access_token=token,
                mock=bool(raw.get("mock", False)),
                expires_at=float(raw["expires_at"]),
                created_at=time.time(),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _write_ledger(self, ledger: dict[str, Any]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": LEDGER_VERSION,
            "active_account_id": ledger.get("active_account_id"),
            "pending": self._pending_payload(ledger.get("pending")),
            "accounts": [a.to_storage() for a in ledger["accounts"]],
        }
        text = json.dumps(payload, indent=2) + "\n"
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, self._path)
        os.chmod(self._path, 0o600)

    @staticmethod
    def _pending_payload(pending: Any) -> Optional[dict[str, Any]]:
        if isinstance(pending, GithubPendingOauth):
            return pending.to_storage()
        return None

    def _parse_ledger(self, raw: Any) -> Optional[dict[str, Any]]:
        if not isinstance(raw, dict) or raw.get("version") != LEDGER_VERSION:
            return None
        accounts: list[GithubAccount] = []
        for item in raw.get("accounts") or []:
            account = GithubAccount.from_raw(item)
            if account is not None:
                accounts.append(account)
        active_id = raw.get("active_account_id")
        if active_id is not None:
            active_id = str(active_id)
        if active_id and self._by_id(accounts, active_id) is None:
            active_id = self._fallback_active(accounts)
        return {
            "version": LEDGER_VERSION,
            "active_account_id": active_id,
            "pending": GithubPendingOauth.from_raw(raw.get("pending")),
            "accounts": accounts,
        }

    @staticmethod
    def _empty_ledger() -> dict[str, Any]:
        return {
            "version": LEDGER_VERSION,
            "active_account_id": None,
            "pending": None,
            "accounts": [],
        }

    @staticmethod
    def _active_from(ledger: dict[str, Any]) -> Optional[GithubAccount]:
        active_id = ledger.get("active_account_id")
        if not active_id:
            return None
        return GithubAccountStore._by_id(ledger["accounts"], str(active_id))

    @staticmethod
    def _by_id(accounts: list[GithubAccount], account_id: str) -> Optional[GithubAccount]:
        return next((a for a in accounts if a.id == account_id), None)

    @staticmethod
    def _fallback_active(accounts: list[GithubAccount]) -> Optional[str]:
        return accounts[0].id if accounts else None

    def _find_match(
        self, accounts: list[GithubAccount], incoming: GithubAccount
    ) -> Optional[GithubAccount]:
        if incoming.mock:
            return next((a for a in accounts if a.mock), None)
        if incoming.github_user_id:
            by_uid = next(
                (a for a in accounts if a.github_user_id == incoming.github_user_id),
                None,
            )
            if by_uid is not None:
                return by_uid
        return next((a for a in accounts if a.login == incoming.login and not a.mock), None)

    @staticmethod
    def _merge_into(existing: GithubAccount, incoming: GithubAccount) -> None:
        existing.login = incoming.login
        existing.access_token = incoming.access_token
        existing.mock = incoming.mock
        existing.expires_at = incoming.expires_at
        if incoming.github_user_id:
            existing.github_user_id = incoming.github_user_id
        existing.last_used_at = time.time()

    @staticmethod
    def _unlink(path: Path) -> None:
        if path.is_file():
            path.unlink(missing_ok=True)
