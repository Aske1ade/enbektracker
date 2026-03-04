"""Tracker phase refactor: status model, blocks, departments, demo seeds

Revision ID: f19a2e5c4c21
Revises: d90b4f1c2a10
Create Date: 2026-02-24 12:35:00.000000

"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f19a2e5c4c21"
down_revision = "d90b4f1c2a10"
branch_labels = None
depends_on = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_project_statuses() -> None:
    conn = op.get_bind()
    project_ids = [
        row[0] for row in conn.execute(text("SELECT id FROM project ORDER BY id")).fetchall()
    ]

    status_rows_query = text(
        """
        SELECT id, name, code, "order", is_default, is_final
        FROM project_status
        WHERE project_id = :project_id
        ORDER BY "order", id
        """
    )

    update_status_query = text(
        """
        UPDATE project_status
        SET name = :name,
            code = :code,
            color = :color,
            "order" = :order,
            is_default = :is_default,
            is_final = :is_final,
            updated_at = :updated_at
        WHERE id = :status_id
        """
    )

    insert_status_query = text(
        """
        INSERT INTO project_status (
            project_id, name, code, color, "order", is_default, is_final, created_at, updated_at
        ) VALUES (
            :project_id, :name, :code, :color, :order, :is_default, :is_final, :created_at, :updated_at
        )
        RETURNING id
        """
    )

    for project_id in project_ids:
        rows = conn.execute(
            status_rows_query,
            {"project_id": project_id},
        ).mappings().all()
        if not rows:
            continue

        conn.execute(
            text(
                """
                UPDATE project_status
                SET "order" = "order" + 100
                WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id},
        )

        rows_by_code: dict[str, list[dict]] = {}
        for row in rows:
            code = row["code"] or ""
            rows_by_code.setdefault(code, []).append(row)

        def pick(*codes: str) -> dict | None:
            for code in codes:
                candidates = rows_by_code.get(code, [])
                if candidates:
                    return candidates[0]
            return None

        canonical_specs = [
            ("new", "Не начато", "#2B6CB0", 0, True, False, ("new",)),
            (
                "in_progress",
                "В работе",
                "#DD6B20",
                1,
                False,
                False,
                ("in_progress", "review", "testing"),
            ),
            (
                "blocked",
                "Заблокировано",
                "#E53E3E",
                2,
                False,
                False,
                ("blocked", "rejected"),
            ),
            ("done", "Готово", "#2F855A", 3, False, True, ("done",)),
        ]

        canonical_ids: dict[str, int] = {}
        touched_ids: set[int] = set()

        for code, name, color, order, is_default, is_final, candidates in canonical_specs:
            existing = pick(*candidates)
            if existing and existing["id"] not in touched_ids:
                status_id = existing["id"]
                touched_ids.add(status_id)
                conn.execute(
                    update_status_query,
                    {
                        "status_id": status_id,
                        "name": name,
                        "code": code,
                        "color": color,
                        "order": order,
                        "is_default": is_default,
                        "is_final": is_final,
                        "updated_at": utcnow(),
                    },
                )
            else:
                status_id = conn.execute(
                    insert_status_query,
                    {
                        "project_id": project_id,
                        "name": name,
                        "code": code,
                        "color": color,
                        "order": order,
                        "is_default": is_default,
                        "is_final": is_final,
                        "created_at": utcnow(),
                        "updated_at": utcnow(),
                    },
                ).scalar_one()
            canonical_ids[code] = status_id

        # Rebind legacy statuses to canonical values before deleting extras.
        legacy_mappings = {
            "review": canonical_ids["in_progress"],
            "testing": canonical_ids["in_progress"],
            "rejected": canonical_ids["blocked"],
        }
        for legacy_code, target_status_id in legacy_mappings.items():
            legacy_ids = [
                row["id"]
                for row in rows
                if (row["code"] or "") == legacy_code and row["id"] != target_status_id
            ]
            if not legacy_ids:
                continue
            for legacy_id in legacy_ids:
                conn.execute(
                    text(
                        """
                        UPDATE task
                        SET workflow_status_id = :target_status_id
                        WHERE workflow_status_id = :legacy_id
                        """
                    ),
                    {"target_status_id": target_status_id, "legacy_id": legacy_id},
                )

        keep_ids = list(canonical_ids.values())
        remove_ids = [
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT id
                    FROM project_status
                    WHERE project_id = :project_id
                    """
                ),
                {"project_id": project_id},
            ).fetchall()
            if row[0] not in keep_ids
        ]
        for remove_id in remove_ids:
            conn.execute(
                text("DELETE FROM project_status WHERE id = :status_id"),
                {"status_id": remove_id},
            )


def upgrade() -> None:
    op.create_table(
        "work_block",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_block_name"), "work_block", ["name"], unique=True)
    op.create_index(op.f("ix_work_block_code"), "work_block", ["code"], unique=True)

    op.create_table(
        "project_department",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "department_id",
            name="uq_project_department_project_department",
        ),
    )
    op.create_index(
        op.f("ix_project_department_project_id"),
        "project_department",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_department_department_id"),
        "project_department",
        ["department_id"],
        unique=False,
    )

    op.create_table(
        "work_block_department",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("block_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["block_id"], ["work_block.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "block_id",
            "department_id",
            name="uq_work_block_department_block_department",
        ),
    )
    op.create_index(
        op.f("ix_work_block_department_block_id"),
        "work_block_department",
        ["block_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_block_department_department_id"),
        "work_block_department",
        ["department_id"],
        unique=False,
    )

    op.create_table(
        "work_block_project",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("block_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["block_id"], ["work_block.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "block_id",
            "project_id",
            name="uq_work_block_project_block_project",
        ),
    )
    op.create_index(
        op.f("ix_work_block_project_block_id"),
        "work_block_project",
        ["block_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_block_project_project_id"),
        "work_block_project",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "work_block_manager",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("block_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["block_id"], ["work_block.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("block_id", "user_id", name="uq_work_block_manager"),
    )
    op.create_index(
        op.f("ix_work_block_manager_block_id"),
        "work_block_manager",
        ["block_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_block_manager_user_id"),
        "work_block_manager",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "demo_seed_entity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "entity_type",
            "entity_id",
            name="uq_demo_seed_entity_batch_type_id",
        ),
    )
    op.create_index(
        op.f("ix_demo_seed_entity_batch_id"),
        "demo_seed_entity",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_demo_seed_entity_entity_type"),
        "demo_seed_entity",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_demo_seed_entity_entity_id"),
        "demo_seed_entity",
        ["entity_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO project_department (project_id, department_id, created_at, updated_at)
        SELECT p.id, p.department_id, timezone('utc', now()), timezone('utc', now())
        FROM project p
        WHERE p.department_id IS NOT NULL
        """
    )

    _normalize_project_statuses()

    op.drop_column("task", "priority")
    op.execute("DROP TYPE IF EXISTS taskpriority")


def downgrade() -> None:
    task_priority_enum = postgresql.ENUM(
        "low",
        "medium",
        "high",
        "critical",
        "urgent",
        "immediate",
        name="taskpriority",
    )
    task_priority_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "task",
        sa.Column(
            "priority",
            task_priority_enum,
            nullable=False,
            server_default="medium",
        ),
    )

    op.drop_index(op.f("ix_demo_seed_entity_entity_id"), table_name="demo_seed_entity")
    op.drop_index(op.f("ix_demo_seed_entity_entity_type"), table_name="demo_seed_entity")
    op.drop_index(op.f("ix_demo_seed_entity_batch_id"), table_name="demo_seed_entity")
    op.drop_table("demo_seed_entity")

    op.drop_index(op.f("ix_work_block_manager_user_id"), table_name="work_block_manager")
    op.drop_index(op.f("ix_work_block_manager_block_id"), table_name="work_block_manager")
    op.drop_table("work_block_manager")

    op.drop_index(op.f("ix_work_block_project_project_id"), table_name="work_block_project")
    op.drop_index(op.f("ix_work_block_project_block_id"), table_name="work_block_project")
    op.drop_table("work_block_project")

    op.drop_index(
        op.f("ix_work_block_department_department_id"),
        table_name="work_block_department",
    )
    op.drop_index(op.f("ix_work_block_department_block_id"), table_name="work_block_department")
    op.drop_table("work_block_department")

    op.drop_index(
        op.f("ix_project_department_department_id"),
        table_name="project_department",
    )
    op.drop_index(op.f("ix_project_department_project_id"), table_name="project_department")
    op.drop_table("project_department")

    op.drop_index(op.f("ix_work_block_code"), table_name="work_block")
    op.drop_index(op.f("ix_work_block_name"), table_name="work_block")
    op.drop_table("work_block")
