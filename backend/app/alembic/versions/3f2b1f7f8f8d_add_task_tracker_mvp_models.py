"""Add task tracker MVP models

Revision ID: 3f2b1f7f8f8d
Revises: e2412789c190
Create Date: 2026-02-23 23:40:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3f2b1f7f8f8d"
down_revision = "e2412789c190"
branch_labels = None
depends_on = None


system_role_enum = postgresql.ENUM(
    "executor",
    "controller",
    "manager",
    "admin",
    name="systemrole",
    create_type=False,
)
project_member_role_enum = postgresql.ENUM(
    "executor",
    "controller",
    "manager",
    name="projectmemberrole",
    create_type=False,
)
task_priority_enum = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "critical",
    name="taskpriority",
    create_type=False,
)
task_deadline_state_enum = postgresql.ENUM(
    "green",
    "yellow",
    "red",
    name="taskdeadlinestate",
    create_type=False,
)
task_urgency_state_enum = postgresql.ENUM(
    "overdue",
    "critical",
    "normal",
    "reserve",
    name="taskurgencystate",
    create_type=False,
)
task_history_action_enum = postgresql.ENUM(
    "created",
    "updated",
    "due_date_changed",
    "status_changed",
    "assignee_changed",
    "closed",
    "reopened",
    "comment_added",
    "attachment_added",
    name="taskhistoryaction",
    create_type=False,
)
notification_type_enum = postgresql.ENUM(
    "task_assigned",
    "task_due_date_changed",
    "task_commented",
    "task_deadline_approaching",
    "task_overdue",
    "task_status_changed",
    "system",
    name="notificationtype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    system_role_enum.create(bind, checkfirst=True)
    project_member_role_enum.create(bind, checkfirst=True)
    task_priority_enum.create(bind, checkfirst=True)
    task_deadline_state_enum.create(bind, checkfirst=True)
    task_urgency_state_enum.create(bind, checkfirst=True)
    task_history_action_enum.create(bind, checkfirst=True)
    notification_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "department",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_department_name"), "department", ["name"], unique=True)
    op.create_index(op.f("ix_department_code"), "department", ["code"], unique=True)

    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_role_name"), "role", ["name"], unique=True)

    op.add_column(
        "user",
        sa.Column(
            "system_role",
            system_role_enum,
            nullable=False,
            server_default="executor",
        ),
    )
    op.add_column("user", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column(
        "user",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
    )
    op.create_foreign_key(
        "fk_user_department_id_department",
        "user",
        "department",
        ["department_id"],
        ["id"],
    )

    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("require_close_comment", sa.Boolean(), nullable=False),
        sa.Column("require_close_attachment", sa.Boolean(), nullable=False),
        sa.Column("deadline_yellow_days", sa.Integer(), nullable=False),
        sa.Column("deadline_normal_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_name"), "project", ["name"], unique=False)

    op.create_table(
        "project_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", project_member_role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index(
        op.f("ix_project_member_project_id"), "project_member", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_member_user_id"), "project_member", ["user_id"], unique=False
    )

    op.create_table(
        "project_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("color", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_project_status_name"),
        sa.UniqueConstraint("project_id", "order", name="uq_project_status_order"),
    )
    op.create_index(
        op.f("ix_project_status_project_id"), "project_status", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_project_status_code"), "project_status", ["code"], unique=False)

    op.create_table(
        "task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("controller_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", task_priority_enum, nullable=False),
        sa.Column("workflow_status_id", sa.Integer(), nullable=False),
        sa.Column("computed_deadline_state", task_deadline_state_enum, nullable=False),
        sa.Column("computed_urgency_state", task_urgency_state_enum, nullable=False),
        sa.Column("is_overdue", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignee_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["controller_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["workflow_status_id"], ["project_status.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_title"), "task", ["title"], unique=False)
    op.create_index(op.f("ix_task_project_id"), "task", ["project_id"], unique=False)
    op.create_index(op.f("ix_task_assignee_id"), "task", ["assignee_id"], unique=False)
    op.create_index(op.f("ix_task_creator_id"), "task", ["creator_id"], unique=False)
    op.create_index(op.f("ix_task_controller_id"), "task", ["controller_id"], unique=False)
    op.create_index(op.f("ix_task_due_date"), "task", ["due_date"], unique=False)
    op.create_index(
        op.f("ix_task_workflow_status_id"), "task", ["workflow_status_id"], unique=False
    )

    op.create_table(
        "task_comment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_comment_task_id"), "task_comment", ["task_id"], unique=False)
    op.create_index(
        op.f("ix_task_comment_author_id"), "task_comment", ["author_id"], unique=False
    )

    op.create_table(
        "task_attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("object_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_task_attachment_task_id"), "task_attachment", ["task_id"], unique=False
    )
    op.create_index(
        op.f("ix_task_attachment_uploaded_by_id"),
        "task_attachment",
        ["uploaded_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_attachment_object_key"),
        "task_attachment",
        ["object_key"],
        unique=True,
    )

    op.create_table(
        "task_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", task_history_action_enum, nullable=False),
        sa.Column("field_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("old_value", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("new_value", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_history_task_id"), "task_history", ["task_id"], unique=False)
    op.create_index(
        op.f("ix_task_history_actor_id"), "task_history", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_task_history_field_name"), "task_history", ["field_name"], unique=False
    )

    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("payload_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_user_id"), "notification", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_notification_is_read"), "notification", ["is_read"], unique=False
    )

    op.create_table(
        "report_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("template_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_report_template_name"), "report_template", ["name"], unique=True)

    op.create_table(
        "discipline_certificate_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("template_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_discipline_certificate_template_name"),
        "discipline_certificate_template",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_discipline_certificate_template_name"),
        table_name="discipline_certificate_template",
    )
    op.drop_table("discipline_certificate_template")

    op.drop_index(op.f("ix_report_template_name"), table_name="report_template")
    op.drop_table("report_template")

    op.drop_index(op.f("ix_notification_is_read"), table_name="notification")
    op.drop_index(op.f("ix_notification_user_id"), table_name="notification")
    op.drop_table("notification")

    op.drop_index(op.f("ix_task_history_field_name"), table_name="task_history")
    op.drop_index(op.f("ix_task_history_actor_id"), table_name="task_history")
    op.drop_index(op.f("ix_task_history_task_id"), table_name="task_history")
    op.drop_table("task_history")

    op.drop_index(op.f("ix_task_attachment_object_key"), table_name="task_attachment")
    op.drop_index(op.f("ix_task_attachment_uploaded_by_id"), table_name="task_attachment")
    op.drop_index(op.f("ix_task_attachment_task_id"), table_name="task_attachment")
    op.drop_table("task_attachment")

    op.drop_index(op.f("ix_task_comment_author_id"), table_name="task_comment")
    op.drop_index(op.f("ix_task_comment_task_id"), table_name="task_comment")
    op.drop_table("task_comment")

    op.drop_index(op.f("ix_task_workflow_status_id"), table_name="task")
    op.drop_index(op.f("ix_task_due_date"), table_name="task")
    op.drop_index(op.f("ix_task_controller_id"), table_name="task")
    op.drop_index(op.f("ix_task_creator_id"), table_name="task")
    op.drop_index(op.f("ix_task_assignee_id"), table_name="task")
    op.drop_index(op.f("ix_task_project_id"), table_name="task")
    op.drop_index(op.f("ix_task_title"), table_name="task")
    op.drop_table("task")

    op.drop_index(op.f("ix_project_status_code"), table_name="project_status")
    op.drop_index(op.f("ix_project_status_project_id"), table_name="project_status")
    op.drop_table("project_status")

    op.drop_index(op.f("ix_project_member_user_id"), table_name="project_member")
    op.drop_index(op.f("ix_project_member_project_id"), table_name="project_member")
    op.drop_table("project_member")

    op.drop_index(op.f("ix_project_name"), table_name="project")
    op.drop_table("project")

    op.drop_constraint("fk_user_department_id_department", "user", type_="foreignkey")
    op.drop_column("user", "updated_at")
    op.drop_column("user", "created_at")
    op.drop_column("user", "department_id")
    op.drop_column("user", "system_role")

    op.drop_index(op.f("ix_role_name"), table_name="role")
    op.drop_table("role")

    op.drop_index(op.f("ix_department_code"), table_name="department")
    op.drop_index(op.f("ix_department_name"), table_name="department")
    op.drop_table("department")

    bind = op.get_bind()
    notification_type_enum.drop(bind, checkfirst=True)
    task_history_action_enum.drop(bind, checkfirst=True)
    task_urgency_state_enum.drop(bind, checkfirst=True)
    task_deadline_state_enum.drop(bind, checkfirst=True)
    task_priority_enum.drop(bind, checkfirst=True)
    project_member_role_enum.drop(bind, checkfirst=True)
    system_role_enum.drop(bind, checkfirst=True)
