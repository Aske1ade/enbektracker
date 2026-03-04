"""Add tracker visibility and sorting indexes

Revision ID: b6c9d3a4f1a0
Revises: 94f2a7d21d1a
Create Date: 2026-02-24 08:20:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b6c9d3a4f1a0"
down_revision = "94f2a7d21d1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_project_member_user_active_project",
        "project_member",
        ["user_id", "is_active", "project_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_visibility_project_updated",
        "task",
        ["project_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_overdue_due_date",
        "task",
        ["is_overdue", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_task_assignee_updated",
        "task",
        ["assignee_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_project_department_updated",
        "project",
        ["department_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_department_updated", table_name="project")
    op.drop_index("ix_task_assignee_updated", table_name="task")
    op.drop_index("ix_task_overdue_due_date", table_name="task")
    op.drop_index("ix_task_visibility_project_updated", table_name="task")
    op.drop_index("ix_project_member_user_active_project", table_name="project_member")
