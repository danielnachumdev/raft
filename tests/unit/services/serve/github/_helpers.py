"""Shared fixtures for serve GitHub unit tests."""

from __future__ import annotations

import time

from raft.services.serve.github.provider import GithubRepo
from raft.services.serve.github.session import GithubSession


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


def sample_session(**kwargs) -> GithubSession:
    base = dict(access_token="t", login="u", mock=True, expires_at=time.time() + 60)
    base.update(kwargs)
    return GithubSession(**base)


def stub_auth(auth_cls) -> None:
    auth = auth_cls.return_value
    auth.show_pubkey.return_value = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI comment"
    auth_cls._pubkey_for_paste.return_value = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI"
