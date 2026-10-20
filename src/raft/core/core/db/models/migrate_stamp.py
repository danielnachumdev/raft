"""Stamp recording a completed files→SQLite import."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from raft.core.core.db.base import DbBase

MIGRATE_STAMP_ID = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MigrateFromFilesStamp(DbBase):
    """Singleton row: migrate-from-files completed (idempotent re-runs)."""

    __tablename__ = "raft_migrate_from_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    source_backup_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tables_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
