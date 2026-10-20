"""Initial durable-state tables (settings, apps, firewall, migrate stamp).

Revision ID: 20261020_0001
Revises:
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _create_settings()
    _create_apps()
    _create_deploy_pins()
    _create_firewall_rules()
    _create_firewall_dismissed()
    _create_migrate_stamp()


def downgrade() -> None:
    op.drop_table("raft_migrate_from_files")
    op.drop_table("firewall_dismissed_recommendations")
    op.drop_table("firewall_rules")
    op.drop_table("deploy_pins")
    op.drop_index("ix_apps_source_identity", table_name="apps")
    op.drop_index("ix_apps_group", table_name="apps")
    op.drop_table("apps")
    op.drop_table("settings")


def _create_settings() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_apps() -> None:
    op.create_table(
        "apps",
        sa.Column("name", sa.String(length=255), primary_key=True),
        sa.Column("api_version", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("manifest_yaml", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_identity", sa.String(length=1024), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_apps_group", "apps", ["group_name"])
    op.create_index("ix_apps_source_identity", "apps", ["source_identity"])


def _create_deploy_pins() -> None:
    op.create_table(
        "deploy_pins",
        sa.Column("app_name", sa.String(length=255), primary_key=True),
        sa.Column("ref_text", sa.Text(), nullable=True),
        sa.Column("image_text", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_firewall_rules() -> None:
    op.create_table(
        "firewall_rules",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=64), nullable=False),
        sa.Column("service", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
    )


def _create_firewall_dismissed() -> None:
    op.create_table(
        "firewall_dismissed_recommendations",
        sa.Column("recommendation_id", sa.String(length=255), primary_key=True),
    )


def _create_migrate_stamp() -> None:
    op.create_table(
        "raft_migrate_from_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_backup_path", sa.Text(), nullable=True),
        sa.Column("tables_json", sa.Text(), nullable=False),
        sa.Column("note", sa.String(length=512), nullable=True),
    )
