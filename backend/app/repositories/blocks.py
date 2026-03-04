from sqlalchemy.orm import selectinload
from sqlmodel import Session, delete, func, select

from app.models import (
    Department,
    Project,
    User,
    WorkBlock,
    WorkBlockDepartment,
    WorkBlockManager,
    WorkBlockProject,
)


def list_blocks(session: Session) -> list[WorkBlock]:
    return session.exec(select(WorkBlock).order_by(WorkBlock.name.asc())).all()


def get_block(session: Session, block_id: int) -> WorkBlock | None:
    return session.get(WorkBlock, block_id)


def create_block(session: Session, block: WorkBlock) -> WorkBlock:
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


def update_block(session: Session, block: WorkBlock) -> WorkBlock:
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


def delete_block(session: Session, block_id: int) -> None:
    session.exec(delete(WorkBlockDepartment).where(WorkBlockDepartment.block_id == block_id))
    session.exec(delete(WorkBlockProject).where(WorkBlockProject.block_id == block_id))
    session.exec(delete(WorkBlockManager).where(WorkBlockManager.block_id == block_id))
    block = session.get(WorkBlock, block_id)
    if block:
        session.delete(block)
    session.commit()


def block_counts(
    session: Session,
    *,
    block_id: int,
) -> tuple[int, int, int]:
    departments_count = session.exec(
        select(func.count(WorkBlockDepartment.id)).where(WorkBlockDepartment.block_id == block_id)
    ).one()
    projects_count = session.exec(
        select(func.count(WorkBlockProject.id)).where(WorkBlockProject.block_id == block_id)
    ).one()
    managers_count = session.exec(
        select(func.count(WorkBlockManager.id)).where(
            WorkBlockManager.block_id == block_id,
            WorkBlockManager.is_active.is_(True),
        )
    ).one()
    return departments_count, projects_count, managers_count


def list_block_departments(session: Session, *, block_id: int) -> list[WorkBlockDepartment]:
    return session.exec(
        select(WorkBlockDepartment)
        .options(selectinload(WorkBlockDepartment.department))
        .where(WorkBlockDepartment.block_id == block_id)
        .order_by(WorkBlockDepartment.id.asc())
    ).all()


def add_block_department(
    session: Session,
    *,
    block_id: int,
    department_id: int,
) -> WorkBlockDepartment:
    existing = session.exec(
        select(WorkBlockDepartment).where(
            WorkBlockDepartment.block_id == block_id,
            WorkBlockDepartment.department_id == department_id,
        )
    ).first()
    if existing:
        return existing
    row = WorkBlockDepartment(block_id=block_id, department_id=department_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def remove_block_department(session: Session, *, block_id: int, department_id: int) -> None:
    session.exec(
        delete(WorkBlockDepartment).where(
            WorkBlockDepartment.block_id == block_id,
            WorkBlockDepartment.department_id == department_id,
        )
    )
    session.commit()


def list_block_projects(session: Session, *, block_id: int) -> list[WorkBlockProject]:
    return session.exec(
        select(WorkBlockProject)
        .options(selectinload(WorkBlockProject.project))
        .where(WorkBlockProject.block_id == block_id)
        .order_by(WorkBlockProject.id.asc())
    ).all()


def add_block_project(
    session: Session,
    *,
    block_id: int,
    project_id: int,
) -> WorkBlockProject:
    existing = session.exec(
        select(WorkBlockProject).where(
            WorkBlockProject.block_id == block_id,
            WorkBlockProject.project_id == project_id,
        )
    ).first()
    if existing:
        return existing
    row = WorkBlockProject(block_id=block_id, project_id=project_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def remove_block_project(session: Session, *, block_id: int, project_id: int) -> None:
    session.exec(
        delete(WorkBlockProject).where(
            WorkBlockProject.block_id == block_id,
            WorkBlockProject.project_id == project_id,
        )
    )
    session.commit()


def list_block_managers(session: Session, *, block_id: int) -> list[WorkBlockManager]:
    return session.exec(
        select(WorkBlockManager)
        .options(selectinload(WorkBlockManager.user))
        .where(WorkBlockManager.block_id == block_id)
        .order_by(WorkBlockManager.id.asc())
    ).all()


def upsert_block_manager(
    session: Session,
    *,
    block_id: int,
    user_id: int,
    is_active: bool,
) -> WorkBlockManager:
    row = session.exec(
        select(WorkBlockManager).where(
            WorkBlockManager.block_id == block_id,
            WorkBlockManager.user_id == user_id,
        )
    ).first()
    if row is None:
        row = WorkBlockManager(block_id=block_id, user_id=user_id, is_active=is_active)
    else:
        row.is_active = is_active
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def remove_block_manager(session: Session, *, block_id: int, user_id: int) -> None:
    session.exec(
        delete(WorkBlockManager).where(
            WorkBlockManager.block_id == block_id,
            WorkBlockManager.user_id == user_id,
        )
    )
    session.commit()


def get_block_project_ids_for_user(session: Session, *, user_id: int) -> set[int]:
    return set(
        session.exec(
            select(WorkBlockProject.project_id)
            .join(WorkBlockManager, WorkBlockManager.block_id == WorkBlockProject.block_id)
            .where(
                WorkBlockManager.user_id == user_id,
                WorkBlockManager.is_active.is_(True),
            )
        ).all()
    )


def get_department_name_map(session: Session) -> dict[int, str]:
    return {row[0]: row[1] for row in session.exec(select(Department.id, Department.name)).all()}


def get_project_name_map(session: Session) -> dict[int, str]:
    return {row[0]: row[1] for row in session.exec(select(Project.id, Project.name)).all()}


def get_user_display_name_map(session: Session) -> dict[int, str]:
    rows = session.exec(select(User.id, User.full_name, User.email)).all()
    return {row[0]: row[1] or row[2] or f"User #{row[0]}" for row in rows}
