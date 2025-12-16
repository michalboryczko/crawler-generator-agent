"""Create sessions table.

Revision ID: 002
Revises: 001
Create Date: 2025-01-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("target_site", sa.Text(), nullable=False),
        sa.Column("init_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("output_dir", sa.String(512), nullable=True),
        sa.Column("agent_version", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_session_status", "sessions", ["status"])
    op.create_index("idx_session_init_at", "sessions", ["init_at"])


def downgrade() -> None:
    op.drop_index("idx_session_init_at", table_name="sessions")
    op.drop_index("idx_session_status", table_name="sessions")
    op.drop_table("sessions")
