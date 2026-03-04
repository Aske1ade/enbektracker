from sqlmodel import Session, select

from app.models import (
    Project,
    ProjectAccessSubjectType,
    ProjectMember,
    ProjectMemberRole,
    ProjectStatus,
    ProjectSubjectRole,
    Role,
    User,
)
from app.repositories import project_statuses as status_repo
from app.repositories import projects as project_repo

DEFAULT_STATUS_PRESET = [
    ("В работе", "in_progress", "#DD6B20", 0, True, False),
    ("На проверке", "review", "#2B6CB0", 1, False, False),
    ("Готово", "done", "#2F855A", 2, False, True),
]


def create_project_with_defaults(
    session: Session,
    *,
    creator: User,
    name: str,
    icon: str | None,
    description: str | None,
    organization_id: int | None,
    department_id: int | None,
    require_close_comment: bool,
    require_close_attachment: bool,
    deadline_yellow_days: int,
    deadline_normal_days: int,
) -> Project:
    project = Project(
        name=name,
        icon=icon,
        description=description,
        organization_id=organization_id,
        department_id=department_id,
        created_by_id=creator.id,
        require_close_comment=require_close_comment,
        require_close_attachment=require_close_attachment,
        deadline_yellow_days=deadline_yellow_days,
        deadline_normal_days=deadline_normal_days,
    )
    project = project_repo.create_project(session, project)

    member = ProjectMember(
        project_id=project.id,
        user_id=creator.id,
        role=ProjectMemberRole.MANAGER,
        is_active=True,
    )
    project_repo.create_project_member(session, member)

    role_id = session.exec(select(Role.id).where(Role.name == "project_admin")).first()
    if role_id is not None:
        session.add(
            ProjectSubjectRole(
                project_id=project.id,
                role_id=role_id,
                subject_type=ProjectAccessSubjectType.USER,
                subject_user_id=creator.id,
                subject_group_id=None,
                is_active=True,
            )
        )
        session.commit()

    for name, code, color, order, is_default, is_final in DEFAULT_STATUS_PRESET:
        status_obj = ProjectStatus(
            project_id=project.id,
            name=name,
            code=code,
            color=color,
            order=order,
            is_default=is_default,
            is_final=is_final,
        )
        status_repo.create_project_status(session, status_obj)

    return project
