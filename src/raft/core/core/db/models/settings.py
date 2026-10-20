"""Singleton operator settings document row."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from raft.core.core.db.base import DbBase

SETTINGS_SINGLETON_ID = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SettingsRow(DbBase):
    """Full ``RaftConfig`` JSON document (serve camelCase keys)."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
