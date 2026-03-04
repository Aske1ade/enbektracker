from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, col, delete, func, select

from app.models import (
    Department,
    Project,
    ProjectDepartment,
    ProjectMember,
    ProjectStatus,
    Task,
    TaskAssignee,
    TaskAttachment,
    TaskComment,
    TaskHistory,
    WorkBlockProject,
)

SORTABLE_FIELDS: dict[str, object] = {
    "id": Project.id,
    "name": Project.name,
    "created_at": Project.created_at,
    "updated_at": Project.updated_at,
}


def list_projects(
    session: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    department_id: int | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    viewer_user_id: int | None = None,
    can_view_all: bool = False,
    accessible_project_ids: set[int] | None = None,
) -> tuple[list[Project], int]:
    statement = select(Project).options(
        selectinload(Project.creator),
        selectinload(Project.organization),
        selectinload(Project.department),
        selectinload(Project.project_departments).selectinload(ProjectDepartment.department),
        selectinload(Project.block_links).selectinload(WorkBlockProject.block),
    )
    count_statement = select(func.count()).select_from(Project)
    filters = []

    if department_id is not None:
        department_exists = (
            select(ProjectDepartment.id)
            .where(
                ProjectDepartment.project_id == Project.id,
                ProjectDepartment.department_id == department_id,
            )
            .exists()
        )
        filters.append(
            (Project.department_id == department_id) | department_exists
        )

    if search:
        like = f"%{search.lower()}%"
        filters.append(func.lower(Project.name).like(like))

    if not can_view_all:
        if accessible_project_ids is not None:
            if not accessible_project_ids:
                return [], 0
            filters.append(Project.id.in_(sorted(accessible_project_ids)))
        elif viewer_user_id is None:
            return [], 0
        else:
            membership_exists = (
                select(ProjectMember.id)
                .where(
                    ProjectMember.project_id == Project.id,
                    ProjectMember.user_id == viewer_user_id,
                    ProjectMember.is_active.is_(True),
                )
                .exists()
            )
            filters.append(membership_exists)

    if filters:
        condition = and_(*filters)
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)

    sort_column = SORTABLE_FIELDS.get(sort_by, Project.created_at)
    if sort_order == "asc":
        statement = statement.order_by(col(sort_column).asc())
    else:
        statement = statement.order_by(col(sort_column).desc())

    count = session.exec(count_statement).one()
    projects = session.exec(statement.offset(skip).limit(limit)).all()
    return projects, count


def get_project_members_count_map(
    session: Session,
    *,
    project_ids: list[int],
) -> dict[int, int]:
    if not project_ids:
        return {}
    rows = session.exec(
        select(ProjectMember.project_id, func.count(ProjectMember.id))
        .where(
            ProjectMember.project_id.in_(project_ids),
            ProjectMember.is_active.is_(True),
        )
        .group_by(ProjectMember.project_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def get_project_member_user_ids_map(
    session: Session,
    *,
    project_ids: list[int],
) -> dict[int, list[int]]:
    if not project_ids:
        return {}
    rows = session.exec(
        select(ProjectMember.project_id, ProjectMember.user_id)
        .where(
            ProjectMember.project_id.in_(project_ids),
            ProjectMember.is_active.is_(True),
        )
        .order_by(ProjectMember.project_id.asc(), ProjectMember.user_id.asc())
    ).all()
    ids_by_project: dict[int, set[int]] = {}
    for project_id, user_id in rows:
        if project_id is None or user_id is None:
            continue
        ids_by_project.setdefault(int(project_id), set()).add(int(user_id))
    return {
        project_id: sorted(list(user_ids))
        for project_id, user_ids in ids_by_project.items()
    }


def get_project_tasks_count_map(
    session: Session,
    *,
    project_ids: list[int],
) -> dict[int, int]:
    if not project_ids:
        return {}
    rows = session.exec(
        select(Task.project_id, func.count(Task.id))
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def get_project(session: Session, project_id: int) -> Project | None:
    return session.exec(
        select(Project)
        .options(
            selectinload(Project.creator),
            selectinload(Project.organization),
            selectinload(Project.department),
            selectinload(Project.project_departments).selectinload(ProjectDepartment.department),
            selectinload(Project.block_links).selectinload(WorkBlockProject.block),
        )
        .where(Project.id == project_id)
    ).first()


def create_project(session: Session, project: Project) -> Project:
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def update_project(session: Session, project: Project) -> Project:
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project: Project) -> None:
    task_ids = session.exec(select(Task.id).where(Task.project_id == project.id)).all()
    if task_ids:
        session.exec(delete(TaskHistory).where(TaskHistory.task_id.in_(task_ids)))
        session.exec(delete(TaskComment).where(TaskComment.task_id.in_(task_ids)))
        session.exec(delete(TaskAttachment).where(TaskAttachment.task_id.in_(task_ids)))
        session.exec(delete(TaskAssignee).where(TaskAssignee.task_id.in_(task_ids)))

    session.exec(delete(Task).where(Task.project_id == project.id))
    session.exec(delete(ProjectStatus).where(ProjectStatus.project_id == project.id))
    session.exec(delete(ProjectMember).where(ProjectMember.project_id == project.id))
    session.exec(delete(ProjectDepartment).where(ProjectDepartment.project_id == project.id))
    session.exec(delete(WorkBlockProject).where(WorkBlockProject.project_id == project.id))
    session.delete(project)
    session.commit()


def list_project_members(
    session: Session, project_id: int, *, skip: int = 0, limit: int = 100
) -> tuple[list[ProjectMember], int]:
    count = session.exec(
        select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project_id)
    ).one()
    members = session.exec(
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id)
        .offset(skip)
        .limit(limit)
    ).all()
    return members, count


def get_project_member(
    session: Session,
    *,
    project_id: int,
    user_id: int,
) -> ProjectMember | None:
    return session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).first()


def create_project_member(session: Session, member: ProjectMember) -> ProjectMember:
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def update_project_member(session: Session, member: ProjectMember) -> ProjectMember:
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def delete_project_member(session: Session, member: ProjectMember) -> None:
    session.delete(member)
    session.commit()


def list_project_departments(session: Session, *, project_id: int) -> list[ProjectDepartment]:
    return session.exec(
        select(ProjectDepartment)
        .options(selectinload(ProjectDepartment.department))
        .where(ProjectDepartment.project_id == project_id)
        .order_by(ProjectDepartment.id.asc())
    ).all()


def replace_project_departments(
    session: Session,
    *,
    project_id: int,
    department_ids: list[int],
) -> list[ProjectDepartment]:
    session.exec(delete(ProjectDepartment).where(ProjectDepartment.project_id == project_id))
    for department_id in department_ids:
        session.add(
            ProjectDepartment(
                project_id=project_id,
                department_id=department_id,
            )
        )
    session.commit()
    return list_project_departments(session, project_id=project_id)


def get_department_names_for_project(
    session: Session,
    *,
    project_id: int,
) -> list[str]:
    rows = session.exec(
        select(Department.name)
        .join(ProjectDepartment, ProjectDepartment.department_id == Department.id)
        .where(ProjectDepartment.project_id == project_id)
        .order_by(Department.name.asc())
    ).all()
    return [row for row in rows if row]
