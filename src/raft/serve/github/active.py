"""Resolve the active usable GitHub account token for repos/deploy."""

from __future__ import annotations

from fastapi import HTTPException

from .account import GithubAccount
from .accounts import GithubAccountStore


class GithubActiveResolver:
    """Active-account lookup shared by session-gated serve GitHub routes."""

    def __init__(self, store: GithubAccountStore) -> None:
        self._store = store

    def require(self) -> GithubAccount:
        account = self._store.active_usable()
        if account is None:
            raise HTTPException(
                status_code=401,
                detail="GitHub session required. Open Add new service and sign in.",
            )
        self._store.touch_active()
        return account
