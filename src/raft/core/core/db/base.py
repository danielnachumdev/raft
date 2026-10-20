"""SQLAlchemy declarative base for raft durable-state tables."""

from sqlalchemy.orm import DeclarativeBase


class DbBase(DeclarativeBase):
    """Shared metadata root for Alembic and ORM models."""
