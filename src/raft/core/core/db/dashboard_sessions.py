"""Create / load / revoke dashboard auth sessions in ``raft.sqlite``."""

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from raft.core.core.db.models.dashboard_session import DashboardSessionRow
from raft.core.core.db.schema import SchemaUpgrade
from raft.core.core.db.session import DbSessionFactory

COOKIE_NAME = "raft_dash_session"
CSRF_COOKIE_NAME = "raft_dash_csrf"
DEFAULT_TTL = timedelta(hours=12)


@dataclass(frozen=True)
class MintedSession:
    """Opaque session id + CSRF token for Set-Cookie after authN."""

    id: str
    csrf_token: str


class DashboardSessionStore:
    """Opaque cookie id → subject; deleting the DB revokes every session."""

    def __init__(self, home: Path, *, ttl: timedelta = DEFAULT_TTL) -> None:
        self._home = home
        self._ttl = ttl
        SchemaUpgrade(home).upgrade_head()
        self._db = DbSessionFactory(home)

    def create(self, subject: str, *, auth_mode: str) -> MintedSession:
        session_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        row = DashboardSessionRow(
            id=session_id,
            subject=subject,
            auth_mode=auth_mode,
            csrf_token=csrf,
            created_at=now,
            expires_at=now + self._ttl,
            last_seen_at=now,
        )
        with self._db.begin() as session:
            session.add(row)
        return MintedSession(id=session_id, csrf_token=csrf)

    def subject_for(self, session_id: Optional[str]) -> Optional[str]:
        row = self._touch(session_id)
        return None if row is None else row.subject

    def csrf_ok(self, session_id: Optional[str], header: Optional[str]) -> bool:
        if not session_id or not header:
            return False
        row = self._touch(session_id)
        if row is None:
            return False
        return hmac.compare_digest(row.csrf_token, header)

    def revoke(self, session_id: Optional[str]) -> None:
        if not session_id:
            return
        with self._db.begin() as session:
            row = session.get(DashboardSessionRow, session_id)
            if row is not None:
                session.delete(row)

    def _touch(self, session_id: Optional[str]) -> Optional[DashboardSessionRow]:
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._db.begin() as session:
            row = session.get(DashboardSessionRow, session_id)
            if row is None:
                return None
            if self._expired(row.expires_at, now):
                session.delete(row)
                return None
            row.last_seen_at = now
            row.expires_at = now + self._ttl
            session.expunge(row)
            return row

    @staticmethod
    def _expired(expires_at: datetime, now: datetime) -> bool:
        expires = expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= now
