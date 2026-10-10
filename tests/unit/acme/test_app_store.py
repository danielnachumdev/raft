"""AcmeAppStore persistence."""

from __future__ import annotations

from raft.acme.app_store import AcmeAppState, AcmeAppStore

from tests.unit.base import RaftTestCase


class TestAcmeAppStore(RaftTestCase):
    def test_record_success_and_error(self) -> None:
        store = AcmeAppStore(self.tmp_path)
        store.record_success(
            "web",
            names=["web.test", "www.web.test"],
            not_after="2030-01-01T00:00:00Z",
            now=100.0,
        )
        state = store.load("web")
        assert state.names == ("web.test", "www.web.test")
        assert state.not_after == "2030-01-01T00:00:00Z"
        assert state.last_error is None
        assert state.last_success_ts == 100.0
        store.record_error("web", "DNS not ready")
        again = store.load("web")
        assert again.last_error == "DNS not ready"
        assert again.not_after == "2030-01-01T00:00:00Z"

    def test_corrupt_and_empty(self) -> None:
        store = AcmeAppStore(self.tmp_path)
        assert store.load("missing") == AcmeAppState()
        path = store._paths.app_state("bad")
        path.parent.mkdir(parents=True)
        path.write_text("not-json", encoding="utf-8")
        assert store.load("bad") == AcmeAppState()
        path.write_text("[]\n", encoding="utf-8")
        assert store.load("bad") == AcmeAppState()
