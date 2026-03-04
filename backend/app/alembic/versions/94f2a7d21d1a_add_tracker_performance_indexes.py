"""Add tracker performance indexes

Revision ID: 94f2a7d21d1a
Revises: 3f2b1f7f8f8d
Create Date: 2026-02-24 02:10:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "94f2a7d21d1a"
down_revision = "3f2b1f7f8f8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_task_project_status_due",
        "task",
        ["project_id", "workflow_status_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_task_project_assignee_due",
        "task",
        ["project_id", "assignee_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_task_history_task_created_at",
        "task_history",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_comment_task_created_at",
        "task_comment",
        ["task_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_comment_task_created_at", table_name="task_comment")
    op.drop_index("ix_task_history_task_created_at", table_name="task_history")
    op.drop_index("ix_task_project_assignee_due", table_name="task")
    op.drop_index("ix_task_project_status_due", table_name="task")
