"""DashboardSessionStore create / expire / revoke."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from raft.core.core.db.dashboard_sessions import DashboardSessionStore
from raft.core.core.db.models.dashboard_session import DashboardSessionRow
from raft.core.core.db.session import DbSessionFactory
from tests.unit.base import RaftTestCase


class TestDashboardSessionStore(RaftTestCase):
    def test_create_subject_csrf_and_revoke(self) -> None:
        store = DashboardSessionStore(Path(self.tmp_path))
        minted = store.create("ops@example.com", auth_mode="password")
        assert store.subject_for(minted.id) == "ops@example.com"
        assert store.csrf_ok(minted.id, minted.csrf_token)
        assert not store.csrf_ok(minted.id, "wrong")
        store.revoke(minted.id)
        assert store.subject_for(minted.id) is None

    def test_expire_deletes_row(self) -> None:
        home = Path(self.tmp_path)
        store = DashboardSessionStore(home, ttl=timedelta(hours=1))
        minted = store.create("ops@example.com", auth_mode="oauth")
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        with DbSessionFactory(home).begin() as session:
            row = session.get(DashboardSessionRow, minted.id)
            assert row is not None
            row.expires_at = past
        assert store.subject_for(minted.id) is None
        assert store.subject_for(None) is None
        store.revoke(None)
