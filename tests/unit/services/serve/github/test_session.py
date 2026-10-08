"""GithubSessionStore unit tests."""

from __future__ import annotations

import time

from raft.services.serve.github.session import GithubSession, GithubSessionStore

from ....base import RaftTestCase


class TestGithubSessionStore(RaftTestCase):
    def test_save_load_clear_and_expiry(self) -> None:
        store = GithubSessionStore(self.tmp_path)
        assert store.load() is None
        session = GithubSession(
            access_token="tok",
            login="alice",
            mock=True,
            expires_at=time.time() + 60,
        )
        store.save(session)
        path = self.tmp_path / "state" / "serve" / "github-session.json"
        assert path.is_file()
        assert oct(path.stat().st_mode & 0o777) == "0o600"
        loaded = store.load()
        assert loaded is not None
        assert loaded.login == "alice"
        assert loaded.to_public()["authenticated"] is True
        store.clear()
        assert store.load() is None

    def test_expired_and_corrupt_cleared(self) -> None:
        store = GithubSessionStore(self.tmp_path)
        store.save(
            GithubSession(
                access_token="x",
                login="bob",
                mock=False,
                expires_at=time.time() - 1,
            )
        )
        assert store.load() is None
        path = self.tmp_path / "state" / "serve" / "github-session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        assert store.load() is None
        assert store.mint_oauth_state()
