"""Applied App registry rows (manifest documents)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from raft.core.core.db.base import DbBase


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AppRow(DbBase):
    """One applied App; ``manifest_yaml`` is the lossless registry document."""

    __tablename__ = "apps"
    __table_args__ = (
        Index("ix_apps_group", "group_name"),
        Index("ix_apps_source_identity", "source_identity"),
    )

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    api_version: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(1024), nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class DeployPinRow(DbBase):
    """Deploy pin text from ``deploy/<app>.ref`` / ``deploy/<app>.image``."""

    __tablename__ = "deploy_pins"

    app_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    ref_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
