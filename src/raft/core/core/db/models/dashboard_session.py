"""Runtime dashboard auth sessions (opaque cookie → subject)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from raft.core.core.db.base import DbBase


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DashboardSessionRow(DbBase):
    """One row per active dashboard session; wipe DB → all sessions revoked."""

    __tablename__ = "dashboard_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(320), nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
