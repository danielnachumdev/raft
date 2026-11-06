"""Dashboard auth sessions table (runtime; wipe revokes all).

Revision ID: 20261105_0002
Revises: 20261020_0001
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261105_0002"
down_revision: Union[str, None] = "20261020_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("subject", sa.String(length=320), nullable=False),
        sa.Column("auth_mode", sa.String(length=32), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_dashboard_sessions_subject",
        "dashboard_sessions",
        ["subject"],
    )
    op.create_index(
        "ix_dashboard_sessions_expires_at",
        "dashboard_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_sessions_expires_at", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_subject", table_name="dashboard_sessions")
    op.drop_table("dashboard_sessions")
