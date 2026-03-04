"""Add organization/group RBAC model and migrate legacy access data

Revision ID: ab9e7c1d2f34
Revises: f19a2e5c4c21
Create Date: 2026-02-25 10:45:00.000000

"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ab9e7c1d2f34"
down_revision = "f19a2e5c4c21"
branch_labels = None
depends_on = None


PERMISSIONS: list[tuple[str, str]] = [
    ("read_organization", "Read Organization"),
    ("create_organization", "Create Organization"),
    ("update_organization", "Update Organization"),
    ("delete_organization", "Delete Organization"),
    ("create_project", "Create Project"),
    ("read_project_basic", "Read Project Basic"),
    ("read_project_full", "Read Project Full"),
    ("update_project", "Update Project"),
    ("delete_project", "Delete Project"),
    ("read_role", "Read Role"),
    ("manage_role", "Manage Role"),
    ("update_self", "Update Self"),
    ("create_user", "Create User"),
    ("read_user_basic", "Read User Basic"),
    ("read_user_full", "Read User Full"),
    ("update_user", "Update User"),
    ("delete_user", "Delete User"),
    ("create_group", "Create Group"),
    ("read_group", "Read Group"),
    ("update_group", "Update Group"),
    ("delete_group", "Delete Group"),
    ("low_level_admin_read", "Low-level Admin Read"),
    ("low_level_admin_write", "Low-level Admin Write"),
    ("task_update", "Обновление задачи"),
    ("task_delete", "Удаление задачи"),
    ("task_create_links", "Создание связей задач"),
    ("task_commands_without_notifications", "Применять команды без уведомлений"),
    ("watchers_update", "Обновление списка наблюдателей"),
    ("attachment_add", "Добавление вложения"),
    ("attachment_update", "Обновление вложения"),
    ("attachment_delete", "Удаление вложения"),
    ("task_comment_create", "Создание комментария к задаче"),
    ("task_comment_read", "Чтение комментария к задаче"),
    ("task_comment_update", "Обновление комментария к задаче"),
    ("task_comment_delete", "Удаление комментария к задаче"),
    ("tag_saved_search_create", "Создание тега или сохраненного поиска"),
    ("tag_saved_search_update", "Изменение тега или сохраненного поиска"),
    ("tag_saved_search_delete", "Удаление тега или сохраненного поиска"),
    ("share_custom_view", "Share Custom View"),
    ("work_item_read", "Чтение единицы работы"),
    ("work_item_update", "Обновление единицы работы"),
    ("work_item_create", "Создание единицы работы"),
    ("report_read", "Чтение отчета"),
    ("issue_read", "Чтение задачи"),
    ("issue_private_fields_read", "Чтение закрытых полей задач"),
    ("issue_create", "Создание задачи"),
    ("watchers_read", "Просмотр списка наблюдателей"),
    ("voters_read", "Просмотр списка проголосовавших пользователей"),
    ("foreign_comment_update", "Обновление чужого комментария к задаче"),
    (
        "foreign_comment_delete_permanent",
        "Удаление чужого комментария и окончательное удаление комментария",
    ),
    ("foreign_work_item_update", "Обновление единицы работы другого пользователя"),
    ("foreign_work_item_create", "Создание единицы работы другого пользователя"),
    ("report_create", "Создание отчета"),
    ("report_share", "Поделиться отчетом"),
    ("article_read", "Чтение статьи"),
    ("issue_private_fields_update", "Обновление закрытых полей задачи"),
    ("visibility_constraints_bypass", "Подавление ограничений видимости"),
    ("article_create", "Создание статьи"),
    ("article_update", "Обновление статьи"),
    ("article_delete", "Удаление статьи"),
    ("article_comment_read", "Чтение комментария к статье"),
    ("article_comment_create", "Создание комментария к статье"),
    ("article_comment_update", "Обновление комментария к статье"),
    ("article_comment_delete", "Удаление комментария к статье"),
]

ROLE_TO_PERMISSIONS: dict[str, list[str]] = {
    "system_admin": [permission_key for permission_key, _ in PERMISSIONS],
    "reader": [
        "read_project_basic",
        "read_project_full",
        "issue_read",
        "task_comment_read",
        "attachment_add",
        "report_read",
    ],
    "contributor": [
        "read_project_basic",
        "read_project_full",
        "issue_read",
        "issue_create",
        "task_update",
        "task_comment_read",
        "task_comment_create",
        "task_comment_update",
        "attachment_add",
        "attachment_update",
        "report_read",
    ],
    "project_admin": [
        "read_project_basic",
        "read_project_full",
        "update_project",
        "read_group",
        "update_group",
        "issue_read",
        "issue_create",
        "task_update",
        "task_delete",
        "task_comment_read",
        "task_comment_create",
        "task_comment_update",
        "task_comment_delete",
        "attachment_add",
        "attachment_update",
        "attachment_delete",
        "report_read",
        "report_create",
        "report_share",
    ],
}

ROLE_DESCRIPTIONS = {
    "system_admin": "Системный администратор",
    "reader": "Reader",
    "contributor": "Contributor",
    "project_admin": "Project Admin",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_systemrole_values() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # PostgreSQL requires committing enum value additions before using them.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE systemrole ADD VALUE IF NOT EXISTS 'user'")
        op.execute("ALTER TYPE systemrole ADD VALUE IF NOT EXISTS 'system_admin'")


def _create_schema() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_organization_name"),
        sa.UniqueConstraint("code", name="uq_organization_code"),
    )
    op.create_index(op.f("ix_organization_name"), "organization", ["name"], unique=False)
    op.create_index(op.f("ix_organization_code"), "organization", ["code"], unique=False)

    op.create_table(
        "org_group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("legacy_department_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["legacy_department_id"], ["department.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_department_id", name="uq_org_group_legacy_department"),
        sa.UniqueConstraint("organization_id", "code", name="uq_org_group_org_code"),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_group_org_name"),
    )
    op.create_index(op.f("ix_org_group_organization_id"), "org_group", ["organization_id"], unique=False)
    op.create_index(op.f("ix_org_group_name"), "org_group", ["name"], unique=False)
    op.create_index(op.f("ix_org_group_code"), "org_group", ["code"], unique=False)
    op.create_index(
        op.f("ix_org_group_legacy_department_id"),
        "org_group",
        ["legacy_department_id"],
        unique=False,
    )

    op.create_table(
        "organization_membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_name", sa.String(length=64), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_membership_org_user",
        ),
    )
    op.create_index(
        op.f("ix_organization_membership_organization_id"),
        "organization_membership",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_membership_user_id"),
        "organization_membership",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "group_membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_name", sa.String(length=64), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["org_group.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),
    )
    op.create_index(op.f("ix_group_membership_group_id"), "group_membership", ["group_id"], unique=False)
    op.create_index(op.f("ix_group_membership_user_id"), "group_membership", ["user_id"], unique=False)

    op.create_table(
        "permission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_permission_key"),
    )
    op.create_index(op.f("ix_permission_key"), "permission", ["key"], unique=False)

    op.create_table(
        "role_permission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index(op.f("ix_role_permission_role_id"), "role_permission", ["role_id"], unique=False)
    op.create_index(
        op.f("ix_role_permission_permission_id"),
        "role_permission",
        ["permission_id"],
        unique=False,
    )

    op.add_column("project", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_project_organization_id"), "project", ["organization_id"], unique=False)
    op.create_foreign_key(
        "fk_project_organization_id_organization",
        "project",
        "organization",
        ["organization_id"],
        ["id"],
    )

    op.add_column("user", sa.Column("primary_group_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_user_primary_group_id"), "user", ["primary_group_id"], unique=False)
    op.create_foreign_key(
        "fk_user_primary_group_id_org_group",
        "user",
        "org_group",
        ["primary_group_id"],
        ["id"],
    )

    op.create_table(
        "project_subject_role",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column(
            "subject_type",
            sa.Enum("user", "group", name="projectaccesssubjecttype"),
            nullable=False,
        ),
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_group_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(subject_type = 'user' AND subject_user_id IS NOT NULL AND subject_group_id IS NULL) "
            "OR (subject_type = 'group' AND subject_group_id IS NOT NULL AND subject_user_id IS NULL)",
            name="ck_project_subject_role_subject_ref",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.ForeignKeyConstraint(["subject_group_id"], ["org_group.id"]),
        sa.ForeignKeyConstraint(["subject_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "role_id",
            "subject_type",
            "subject_user_id",
            "subject_group_id",
            name="uq_project_subject_role",
        ),
    )
    op.create_index(
        op.f("ix_project_subject_role_project_id"),
        "project_subject_role",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_subject_role_role_id"),
        "project_subject_role",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_subject_role_subject_user_id"),
        "project_subject_role",
        ["subject_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_subject_role_subject_group_id"),
        "project_subject_role",
        ["subject_group_id"],
        unique=False,
    )


def _migrate_legacy_data() -> None:
    now = _now_utc()
    conn = op.get_bind()
    metadata = sa.MetaData()

    organization = sa.Table("organization", metadata, autoload_with=conn)
    org_group = sa.Table("org_group", metadata, autoload_with=conn)
    organization_membership = sa.Table(
        "organization_membership", metadata, autoload_with=conn
    )
    group_membership = sa.Table("group_membership", metadata, autoload_with=conn)
    permission = sa.Table("permission", metadata, autoload_with=conn)
    role = sa.Table("role", metadata, autoload_with=conn)
    role_permission = sa.Table("role_permission", metadata, autoload_with=conn)
    project = sa.Table("project", metadata, autoload_with=conn)
    user = sa.Table("user", metadata, autoload_with=conn)
    project_subject_role = sa.Table("project_subject_role", metadata, autoload_with=conn)

    # 1) Global organization and legacy blocks -> organizations.
    conn.execute(
        organization.insert().values(
            name="Global",
            code="GLOBAL",
            description="Корневой контур миграции Tracker",
            is_global=True,
            created_at=now,
            updated_at=now,
        )
    )
    global_org_id = conn.execute(
        sa.select(organization.c.id).where(organization.c.code == "GLOBAL")
    ).scalar_one()

    block_rows = conn.execute(
        sa.text(
            "SELECT id, name, code, description, created_at, updated_at "
            "FROM work_block ORDER BY id"
        )
    ).mappings().all()
    existing_org_names = {"Global"}
    existing_org_codes = {"GLOBAL"}
    block_to_org: dict[int, int] = {}
    name_conflicts = 0
    code_conflicts = 0

    for row in block_rows:
        org_name = row["name"] or f"Organization #{row['id']}"
        if org_name in existing_org_names:
            org_name = f"{org_name} #{row['id']}"
            name_conflicts += 1
        existing_org_names.add(org_name)

        org_code = row["code"] or f"ORG-{row['id']}"
        if org_code in existing_org_codes:
            org_code = f"{org_code}-{row['id']}"
            code_conflicts += 1
        existing_org_codes.add(org_code)

        conn.execute(
            organization.insert().values(
                name=org_name,
                code=org_code,
                description=row["description"],
                is_global=False,
                created_at=row["created_at"] or now,
                updated_at=row["updated_at"] or now,
            )
        )
        org_id = conn.execute(
            sa.select(organization.c.id).where(organization.c.code == org_code)
        ).scalar_one()
        block_to_org[int(row["id"])] = int(org_id)

    # 2) Legacy departments -> groups in selected organizations.
    primary_block_rows = conn.execute(
        sa.text(
            """
            SELECT w.department_id, w.block_id
            FROM work_block_department w
            JOIN (
              SELECT department_id, MIN(id) AS min_id
              FROM work_block_department
              GROUP BY department_id
            ) m ON m.min_id = w.id
            """
        )
    ).mappings().all()
    department_to_block: dict[int, int] = {
        int(row["department_id"]): int(row["block_id"]) for row in primary_block_rows
    }

    department_rows = conn.execute(
        sa.text(
            "SELECT id, name, code, description, created_at, updated_at "
            "FROM department ORDER BY id"
        )
    ).mappings().all()
    used_group_names: set[tuple[int, str]] = set()
    used_group_codes: set[tuple[int, str]] = set()
    department_to_group: dict[int, int] = {}
    for row in department_rows:
        department_id = int(row["id"])
        organization_id = block_to_org.get(department_to_block.get(department_id, -1), global_org_id)

        group_name = row["name"] or f"Group #{department_id}"
        name_key = (organization_id, group_name)
        if name_key in used_group_names:
            group_name = f"{group_name} #{department_id}"
        used_group_names.add((organization_id, group_name))

        group_code = row["code"] or f"GRP-{department_id}"
        code_key = (organization_id, group_code)
        if code_key in used_group_codes:
            group_code = f"{group_code}-{department_id}"
        used_group_codes.add((organization_id, group_code))

        conn.execute(
            org_group.insert().values(
                organization_id=organization_id,
                name=group_name,
                code=group_code,
                description=row["description"],
                legacy_department_id=department_id,
                created_at=row["created_at"] or now,
                updated_at=row["updated_at"] or now,
            )
        )
        group_id = conn.execute(
            sa.select(org_group.c.id).where(org_group.c.legacy_department_id == department_id)
        ).scalar_one()
        department_to_group[department_id] = int(group_id)

    # 3) Memberships + user primary group.
    user_rows = conn.execute(
        sa.select(
            user.c.id,
            user.c.department_id,
            user.c.is_superuser,
            user.c.system_role,
        ).order_by(user.c.id.asc())
    ).all()
    org_membership_seen: set[tuple[int, int]] = set()
    group_membership_seen: set[tuple[int, int]] = set()

    for row in user_rows:
        user_id = int(row[0])
        org_membership_seen.add((global_org_id, user_id))
        conn.execute(
            organization_membership.insert().values(
                organization_id=global_org_id,
                user_id=user_id,
                role_name="member",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )

    manager_rows = conn.execute(
        sa.text(
            "SELECT block_id, user_id, is_active FROM work_block_manager ORDER BY id"
        )
    ).mappings().all()
    for row in manager_rows:
        user_id = int(row["user_id"])
        block_id = int(row["block_id"])
        organization_id = block_to_org.get(block_id, global_org_id)
        role_name = "manager" if row["is_active"] else "member"
        key = (organization_id, user_id)
        if key in org_membership_seen:
            if role_name == "manager":
                conn.execute(
                    sa.update(organization_membership)
                    .where(
                        organization_membership.c.organization_id == organization_id,
                        organization_membership.c.user_id == user_id,
                    )
                    .values(role_name="manager", is_active=True, updated_at=now)
                )
            continue
        conn.execute(
            organization_membership.insert().values(
                organization_id=organization_id,
                user_id=user_id,
                role_name=role_name,
                is_active=bool(row["is_active"]),
                created_at=now,
                updated_at=now,
            )
        )
        org_membership_seen.add(key)

    for row in user_rows:
        user_id = int(row[0])
        department_id = row[1]
        legacy_role = str(row[3])
        canonical_role = (
            "system_admin"
            if row[2] or legacy_role in {"admin", "manager", "system_admin"}
            else "user"
        )
        conn.execute(
            sa.update(user)
            .where(user.c.id == user_id)
            .values(system_role=canonical_role)
        )
        if department_id is None:
            continue
        group_id = department_to_group.get(int(department_id))
        if group_id is None:
            continue
        key = (group_id, user_id)
        if key not in group_membership_seen:
            conn.execute(
                group_membership.insert().values(
                    group_id=group_id,
                    user_id=user_id,
                    role_name="member",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            group_membership_seen.add(key)
        conn.execute(
            sa.update(user)
            .where(user.c.id == user_id)
            .values(primary_group_id=group_id)
        )
        group_org_id = conn.execute(
            sa.select(org_group.c.organization_id).where(org_group.c.id == group_id)
        ).scalar_one()
        org_key = (int(group_org_id), user_id)
        if org_key not in org_membership_seen:
            conn.execute(
                organization_membership.insert().values(
                    organization_id=int(group_org_id),
                    user_id=user_id,
                    role_name="member",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            org_membership_seen.add(org_key)

    # 4) Projects -> organizations.
    primary_project_block_rows = conn.execute(
        sa.text(
            """
            SELECT w.project_id, w.block_id
            FROM work_block_project w
            JOIN (
              SELECT project_id, MIN(id) AS min_id
              FROM work_block_project
              GROUP BY project_id
            ) m ON m.min_id = w.id
            """
        )
    ).mappings().all()
    project_to_block: dict[int, int] = {
        int(row["project_id"]): int(row["block_id"]) for row in primary_project_block_rows
    }
    project_rows = conn.execute(
        sa.select(project.c.id, project.c.department_id).order_by(project.c.id.asc())
    ).all()
    for row in project_rows:
        project_id = int(row[0])
        department_id = row[1]
        organization_id = block_to_org.get(project_to_block.get(project_id, -1))
        if organization_id is None and department_id is not None:
            group_id = department_to_group.get(int(department_id))
            if group_id is not None:
                organization_id = conn.execute(
                    sa.select(org_group.c.organization_id).where(org_group.c.id == group_id)
                ).scalar_one()
        if organization_id is None:
            organization_id = global_org_id
        conn.execute(
            sa.update(project)
            .where(project.c.id == project_id)
            .values(organization_id=int(organization_id))
        )

    # 5) Roles, permissions, role-permission matrix.
    for role_key, role_description in ROLE_DESCRIPTIONS.items():
        existing = conn.execute(
            sa.select(role.c.id).where(role.c.name == role_key)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        conn.execute(
            role.insert().values(
                name=role_key,
                description=role_description,
                is_system=True,
                created_at=now,
                updated_at=now,
            )
        )

    for permission_key, permission_name in PERMISSIONS:
        existing = conn.execute(
            sa.select(permission.c.id).where(permission.c.key == permission_key)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        conn.execute(
            permission.insert().values(
                key=permission_key,
                name=permission_name,
                created_at=now,
                updated_at=now,
            )
        )

    role_id_by_name = {
        str(row[0]): int(row[1])
        for row in conn.execute(sa.select(role.c.name, role.c.id)).all()
    }
    permission_id_by_key = {
        str(row[0]): int(row[1])
        for row in conn.execute(sa.select(permission.c.key, permission.c.id)).all()
    }
    existing_role_permission_pairs = {
        (int(row[0]), int(row[1]))
        for row in conn.execute(
            sa.select(role_permission.c.role_id, role_permission.c.permission_id)
        ).all()
    }
    for role_key, permission_keys in ROLE_TO_PERMISSIONS.items():
        role_id = role_id_by_name.get(role_key)
        if role_id is None:
            continue
        for permission_key in permission_keys:
            permission_id = permission_id_by_key.get(permission_key)
            if permission_id is None:
                continue
            pair = (role_id, permission_id)
            if pair in existing_role_permission_pairs:
                continue
            conn.execute(
                role_permission.insert().values(
                    role_id=role_id,
                    permission_id=permission_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            existing_role_permission_pairs.add(pair)

    # 6) Legacy project member links -> project_subject_role user assignments.
    existing_project_subject_pairs: set[tuple[int, int, str, int | None, int | None]] = set()
    for row in conn.execute(
        sa.select(
            project_subject_role.c.project_id,
            project_subject_role.c.role_id,
            project_subject_role.c.subject_type,
            project_subject_role.c.subject_user_id,
            project_subject_role.c.subject_group_id,
        )
    ).all():
        existing_project_subject_pairs.add(
            (int(row[0]), int(row[1]), str(row[2]), row[3], row[4])
        )

    member_rows = conn.execute(
        sa.text(
            "SELECT project_id, user_id, role, is_active "
            "FROM project_member WHERE is_active = true ORDER BY id"
        )
    ).mappings().all()
    member_role_to_new_role = {
        "executor": "reader",
        "controller": "project_admin",
        "manager": "project_admin",
    }

    for row in member_rows:
        role_name = member_role_to_new_role.get(str(row["role"]))
        if role_name is None:
            continue
        role_id = role_id_by_name.get(role_name)
        if role_id is None:
            continue
        key = (
            int(row["project_id"]),
            int(role_id),
            "user",
            int(row["user_id"]),
            None,
        )
        if key in existing_project_subject_pairs:
            continue
        conn.execute(
            project_subject_role.insert().values(
                project_id=int(row["project_id"]),
                role_id=int(role_id),
                subject_type="user",
                subject_user_id=int(row["user_id"]),
                subject_group_id=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        existing_project_subject_pairs.add(key)

    # Block managers historically had project-wide visibility via block links.
    manager_access_rows = conn.execute(
        sa.text(
            """
            SELECT DISTINCT bp.project_id, bm.user_id
            FROM work_block_project bp
            JOIN work_block_manager bm ON bm.block_id = bp.block_id
            WHERE bm.is_active = true
            """
        )
    ).mappings().all()
    project_admin_role_id = role_id_by_name.get("project_admin")
    if project_admin_role_id is not None:
        for row in manager_access_rows:
            key = (
                int(row["project_id"]),
                int(project_admin_role_id),
                "user",
                int(row["user_id"]),
                None,
            )
            if key in existing_project_subject_pairs:
                continue
            conn.execute(
                project_subject_role.insert().values(
                    project_id=int(row["project_id"]),
                    role_id=int(project_admin_role_id),
                    subject_type="user",
                    subject_user_id=int(row["user_id"]),
                    subject_group_id=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            existing_project_subject_pairs.add(key)

    print(
        "[migration ab9e7c1d2f34] legacy->org/group completed: "
        f"organizations={len(block_rows) + 1}, groups={len(department_rows)}, "
        f"name_conflicts={name_conflicts}, code_conflicts={code_conflicts}"
    )


def upgrade() -> None:
    _ensure_systemrole_values()
    _create_schema()
    _migrate_legacy_data()


def downgrade() -> None:
    op.drop_index(op.f("ix_project_subject_role_subject_group_id"), table_name="project_subject_role")
    op.drop_index(op.f("ix_project_subject_role_subject_user_id"), table_name="project_subject_role")
    op.drop_index(op.f("ix_project_subject_role_role_id"), table_name="project_subject_role")
    op.drop_index(op.f("ix_project_subject_role_project_id"), table_name="project_subject_role")
    op.drop_table("project_subject_role")

    op.drop_constraint("fk_user_primary_group_id_org_group", "user", type_="foreignkey")
    op.drop_index(op.f("ix_user_primary_group_id"), table_name="user")
    op.drop_column("user", "primary_group_id")

    op.drop_constraint("fk_project_organization_id_organization", "project", type_="foreignkey")
    op.drop_index(op.f("ix_project_organization_id"), table_name="project")
    op.drop_column("project", "organization_id")

    op.drop_index(op.f("ix_role_permission_permission_id"), table_name="role_permission")
    op.drop_index(op.f("ix_role_permission_role_id"), table_name="role_permission")
    op.drop_table("role_permission")

    op.drop_index(op.f("ix_permission_key"), table_name="permission")
    op.drop_table("permission")

    op.drop_index(op.f("ix_group_membership_user_id"), table_name="group_membership")
    op.drop_index(op.f("ix_group_membership_group_id"), table_name="group_membership")
    op.drop_table("group_membership")

    op.drop_index(
        op.f("ix_organization_membership_user_id"),
        table_name="organization_membership",
    )
    op.drop_index(
        op.f("ix_organization_membership_organization_id"),
        table_name="organization_membership",
    )
    op.drop_table("organization_membership")

    op.drop_index(op.f("ix_org_group_legacy_department_id"), table_name="org_group")
    op.drop_index(op.f("ix_org_group_code"), table_name="org_group")
    op.drop_index(op.f("ix_org_group_name"), table_name="org_group")
    op.drop_index(op.f("ix_org_group_organization_id"), table_name="org_group")
    op.drop_table("org_group")

    op.drop_index(op.f("ix_organization_code"), table_name="organization")
    op.drop_index(op.f("ix_organization_name"), table_name="organization")
    op.drop_table("organization")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS projectaccesssubjecttype")
