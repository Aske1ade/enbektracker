"""Add task policy setting, org/group hierarchy, and normalize task workflow

Revision ID: f0d1e2a3b4c5
Revises: c2a6e8d9b4c0
Create Date: 2026-03-03 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f0d1e2a3b4c5"
down_revision = "c2a6e8d9b4c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization",
        sa.Column("parent_organization_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_organization_parent_organization_id"),
        "organization",
        ["parent_organization_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_organization_parent_organization_id",
        "organization",
        "organization",
        ["parent_organization_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "org_group",
        sa.Column("parent_group_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_org_group_parent_group_id"),
        "org_group",
        ["parent_group_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_org_group_parent_group_id",
        "org_group",
        "org_group",
        ["parent_group_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "system_setting",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_setting_key"), "system_setting", ["key"], unique=True)
    op.execute(
        """
        INSERT INTO system_setting (key, value, created_at, updated_at)
        VALUES ('tasks.allow_backdated_creation', 'false', now(), now())
        ON CONFLICT (key) DO NOTHING
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            project_row RECORD;
            in_progress_id INTEGER;
            review_id INTEGER;
            done_id INTEGER;
        BEGIN
            FOR project_row IN SELECT id FROM project LOOP
                -- Free canonical slots (0/1/2) to avoid uq_project_status_order conflicts
                -- while we normalize statuses for this project.
                UPDATE project_status
                SET "order" = COALESCE("order", 0) + 1000
                WHERE project_id = project_row.id;

                SELECT id INTO done_id
                FROM project_status
                WHERE project_id = project_row.id
                  AND (
                    is_final = TRUE
                    OR lower(COALESCE(code, '')) IN ('done', 'closed', 'final')
                    OR lower(COALESCE(name, '')) IN ('готово', 'закрыто', 'done', 'closed')
                  )
                ORDER BY "order", id
                LIMIT 1;
                IF done_id IS NULL THEN
                    INSERT INTO project_status (project_id, name, code, color, "order", is_default, is_final, created_at, updated_at)
                    VALUES (project_row.id, 'Готово', 'done', '#2F855A', 2, FALSE, TRUE, now(), now())
                    RETURNING id INTO done_id;
                END IF;

                SELECT id INTO review_id
                FROM project_status
                WHERE project_id = project_row.id
                  AND (
                    lower(COALESCE(code, '')) IN ('review', 'testing', 'check')
                    OR lower(COALESCE(name, '')) IN ('на проверке', 'на тестировании', 'review', 'testing', 'check')
                  )
                  AND id <> done_id
                ORDER BY "order", id
                LIMIT 1;
                IF review_id IS NULL THEN
                    INSERT INTO project_status (project_id, name, code, color, "order", is_default, is_final, created_at, updated_at)
                    VALUES (project_row.id, 'На проверке', 'review', '#2B6CB0', 1, FALSE, FALSE, now(), now())
                    RETURNING id INTO review_id;
                END IF;

                SELECT id INTO in_progress_id
                FROM project_status
                WHERE project_id = project_row.id
                  AND id NOT IN (done_id, review_id)
                  AND (
                    lower(COALESCE(code, '')) IN ('in_progress', 'in progress', 'new', 'todo', 'blocked')
                    OR lower(COALESCE(name, '')) IN ('в работе', 'не начато', 'заблокировано', 'in progress', 'new', 'todo', 'blocked')
                    OR is_default = TRUE
                  )
                ORDER BY "order", id
                LIMIT 1;
                IF in_progress_id IS NULL THEN
                    INSERT INTO project_status (project_id, name, code, color, "order", is_default, is_final, created_at, updated_at)
                    VALUES (project_row.id, 'В работе', 'in_progress', '#DD6B20', 0, TRUE, FALSE, now(), now())
                    RETURNING id INTO in_progress_id;
                END IF;

                UPDATE task t
                SET workflow_status_id = CASE
                    WHEN ps.is_final = TRUE
                      OR lower(COALESCE(ps.code, '')) IN ('done', 'closed', 'final')
                      OR lower(COALESCE(ps.name, '')) IN ('готово', 'закрыто', 'done', 'closed')
                        THEN done_id
                    WHEN lower(COALESCE(ps.code, '')) IN ('review', 'testing', 'check')
                      OR lower(COALESCE(ps.name, '')) IN ('на проверке', 'на тестировании', 'review', 'testing', 'check')
                        THEN review_id
                    ELSE in_progress_id
                END
                FROM project_status ps
                WHERE t.project_id = project_row.id
                  AND t.workflow_status_id = ps.id;

                UPDATE task
                SET closed_at = COALESCE(closed_at, updated_at, created_at)
                WHERE project_id = project_row.id
                  AND workflow_status_id = done_id;

                UPDATE task
                SET closed_at = NULL
                WHERE project_id = project_row.id
                  AND workflow_status_id IN (in_progress_id, review_id);

                DELETE FROM project_status
                WHERE project_id = project_row.id
                  AND id NOT IN (in_progress_id, review_id, done_id);

                UPDATE project_status
                SET name = 'В работе',
                    code = 'in_progress',
                    color = '#DD6B20',
                    "order" = 0,
                    is_default = TRUE,
                    is_final = FALSE,
                    updated_at = now()
                WHERE id = in_progress_id;

                UPDATE project_status
                SET name = 'На проверке',
                    code = 'review',
                    color = '#2B6CB0',
                    "order" = 1,
                    is_default = FALSE,
                    is_final = FALSE,
                    updated_at = now()
                WHERE id = review_id;

                UPDATE project_status
                SET name = 'Готово',
                    code = 'done',
                    color = '#2F855A',
                    "order" = 2,
                    is_default = FALSE,
                    is_final = TRUE,
                    updated_at = now()
                WHERE id = done_id;
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_system_setting_key"), table_name="system_setting")
    op.drop_table("system_setting")

    op.drop_constraint("fk_org_group_parent_group_id", "org_group", type_="foreignkey")
    op.drop_index(op.f("ix_org_group_parent_group_id"), table_name="org_group")
    op.drop_column("org_group", "parent_group_id")

    op.drop_constraint(
        "fk_organization_parent_organization_id",
        "organization",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_organization_parent_organization_id"), table_name="organization")
    op.drop_column("organization", "parent_organization_id")
