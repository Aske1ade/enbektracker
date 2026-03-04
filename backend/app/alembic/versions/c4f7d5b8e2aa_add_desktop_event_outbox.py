"""Add desktop event outbox

Revision ID: c4f7d5b8e2aa
Revises: b6c9d3a4f1a0
Create Date: 2026-02-24 08:50:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c4f7d5b8e2aa"
down_revision = "b6c9d3a4f1a0"
branch_labels = None
depends_on = None


desktop_event_type_enum = postgresql.ENUM(
    "assign",
    "due_soon",
    "overdue",
    "status_changed",
    "close_requested",
    "close_approved",
    "system",
    name="desktopeventtype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    desktop_event_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "desktop_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("event_type", desktop_event_type_enum, nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("deeplink", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("payload_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("dedupe_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_desktop_event_user_id"), "desktop_event", ["user_id"], unique=False)
    op.create_index(op.f("ix_desktop_event_task_id"), "desktop_event", ["task_id"], unique=False)
    op.create_index(
        op.f("ix_desktop_event_project_id"),
        "desktop_event",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_desktop_event_created_at"),
        "desktop_event",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_desktop_event_dedupe_key"),
        "desktop_event",
        ["dedupe_key"],
        unique=False,
    )
    op.create_index(
        "ix_desktop_event_user_cursor",
        "desktop_event",
        ["user_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_desktop_event_user_cursor", table_name="desktop_event")
    op.drop_index(op.f("ix_desktop_event_dedupe_key"), table_name="desktop_event")
    op.drop_index(op.f("ix_desktop_event_created_at"), table_name="desktop_event")
    op.drop_index(op.f("ix_desktop_event_project_id"), table_name="desktop_event")
    op.drop_index(op.f("ix_desktop_event_task_id"), table_name="desktop_event")
    op.drop_index(op.f("ix_desktop_event_user_id"), table_name="desktop_event")
    op.drop_table("desktop_event")
    desktop_event_type_enum.drop(op.get_bind(), checkfirst=True)
