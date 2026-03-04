"""Add task assignee links for multiple assignees

Revision ID: 7b9d4f1a2c30
Revises: ab9e7c1d2f34
Create Date: 2026-02-27 19:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b9d4f1a2c30"
down_revision: str | None = "ab9e7c1d2f34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_assignee",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_assignee_task_user"),
    )
    op.create_index("ix_task_assignee_task_id", "task_assignee", ["task_id"], unique=False)
    op.create_index("ix_task_assignee_user_id", "task_assignee", ["user_id"], unique=False)
    op.execute(
        sa.text(
            """
            INSERT INTO task_assignee (task_id, user_id, created_at)
            SELECT id, assignee_id, NOW()
            FROM task
            WHERE assignee_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_task_assignee_user_id", table_name="task_assignee")
    op.drop_index("ix_task_assignee_task_id", table_name="task_assignee")
    op.drop_table("task_assignee")

