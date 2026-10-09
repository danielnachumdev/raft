"""Shared fixtures for serve GitHub unit tests."""

from __future__ import annotations

import time

from raft.services.serve.github.account import GithubAccount
from raft.services.serve.github.provider import GithubRepo


def sample_repo() -> GithubRepo:
    return GithubRepo(
        "o/r",
        "r",
        "o",
        True,
        "main",
        "c",
        "git@github.com:o/r.git",
        "https://github.com/o/r",
    )


def sample_account(**kwargs) -> GithubAccount:
    base = dict(
        id="acct-1",
        access_token="t",
        login="u",
        mock=True,
        expires_at=time.time() + 60,
    )
    base.update(kwargs)
    return GithubAccount(**base)


# Compat alias used by older deploy tests.
sample_session = sample_account


def stub_auth(auth_cls) -> None:
    auth = auth_cls.return_value
    auth.show_pubkey.return_value = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI comment"
    auth_cls._pubkey_for_paste.return_value = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI"
