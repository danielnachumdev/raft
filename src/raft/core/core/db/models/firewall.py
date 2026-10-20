"""Ordered firewall rules and dismissed recommendation ids."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from raft.core.core.db.base import DbBase


class FirewallRuleRow(DbBase):
    """One ordered edge-firewall rule (#211)."""

    __tablename__ = "firewall_rules"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(64), nullable=False)
    service: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class FirewallDismissedRow(DbBase):
    """Dismissed baseline firewall recommendation id."""

    __tablename__ = "firewall_dismissed_recommendations"

    recommendation_id: Mapped[str] = mapped_column(String(255), primary_key=True)
