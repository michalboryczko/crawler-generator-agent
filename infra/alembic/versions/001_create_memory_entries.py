"""Create memory_entries table.

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_entries_session_id", "memory_entries", ["session_id"])
    op.create_index("ix_memory_entries_agent_name", "memory_entries", ["agent_name"])
    op.create_index("ix_memory_entries_key", "memory_entries", ["key"])
    op.create_index("idx_session_agent", "memory_entries", ["session_id", "agent_name"])
    op.create_index(
        "idx_unique_entry",
        "memory_entries",
        ["session_id", "agent_name", "key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_unique_entry", table_name="memory_entries")
    op.drop_index("idx_session_agent", table_name="memory_entries")
    op.drop_index("ix_memory_entries_key", table_name="memory_entries")
    op.drop_index("ix_memory_entries_agent_name", table_name="memory_entries")
    op.drop_index("ix_memory_entries_session_id", table_name="memory_entries")
    op.drop_table("memory_entries")
