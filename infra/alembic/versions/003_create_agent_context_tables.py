"""Create agent context tables for event sourcing.

Revision ID: 003
Revises: 002
Create Date: 2025-01-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create agent_instances table
    op.create_table(
        "agent_instances",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column(
            "parent_instance_id",
            sa.String(64),
            sa.ForeignKey("agent_instances.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_instance_session", "agent_instances", ["session_id"])
    op.create_index("idx_instance_agent_name", "agent_instances", ["agent_name"])
    op.create_index("idx_instance_parent", "agent_instances", ["parent_instance_id"])

    # Create agent_context_events table
    # The auto-increment ID serves as global event ordering across
    # the entire session, enabling point-in-time state restoration
    op.create_table(
        "agent_context_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "instance_id",
            sa.String(64),
            sa.ForeignKey("agent_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Index for session-level queries (main use case for state restoration)
    op.create_index(
        "idx_event_session_id",
        "agent_context_events",
        ["session_id", "id"],
    )
    # Index for instance-level queries
    op.create_index("idx_event_instance", "agent_context_events", ["instance_id"])
    op.create_index("idx_event_type", "agent_context_events", ["event_type"])
    op.create_index("idx_event_tool_call", "agent_context_events", ["tool_call_id"])


def downgrade() -> None:
    # Drop agent_context_events table
    op.drop_index("idx_event_tool_call", table_name="agent_context_events")
    op.drop_index("idx_event_type", table_name="agent_context_events")
    op.drop_index("idx_event_instance", table_name="agent_context_events")
    op.drop_index("idx_event_session_id", table_name="agent_context_events")
    op.drop_table("agent_context_events")

    # Drop agent_instances table
    op.drop_index("idx_instance_parent", table_name="agent_instances")
    op.drop_index("idx_instance_agent_name", table_name="agent_instances")
    op.drop_index("idx_instance_session", table_name="agent_instances")
    op.drop_table("agent_instances")
