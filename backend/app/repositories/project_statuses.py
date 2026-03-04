from sqlmodel import Session, func, select

from app.models import ProjectStatus


def list_project_statuses(
    session: Session,
    *,
    project_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ProjectStatus], int]:
    statement = select(ProjectStatus)
    count_statement = select(func.count()).select_from(ProjectStatus)
    if project_id is not None:
        statement = statement.where(ProjectStatus.project_id == project_id)
        count_statement = count_statement.where(ProjectStatus.project_id == project_id)
    count = session.exec(count_statement).one()
    statuses = session.exec(statement.offset(skip).limit(limit)).all()
    return statuses, count


def get_project_status(session: Session, status_id: int) -> ProjectStatus | None:
    return session.get(ProjectStatus, status_id)


def create_project_status(session: Session, status: ProjectStatus) -> ProjectStatus:
    session.add(status)
    session.commit()
    session.refresh(status)
    return status


def update_project_status(session: Session, status: ProjectStatus) -> ProjectStatus:
    session.add(status)
    session.commit()
    session.refresh(status)
    return status


def delete_project_status(session: Session, status: ProjectStatus) -> None:
    session.delete(status)
    session.commit()


def get_default_project_status(session: Session, project_id: int) -> ProjectStatus | None:
    return session.exec(
        select(ProjectStatus)
        .where(ProjectStatus.project_id == project_id, ProjectStatus.is_default)
        .order_by(ProjectStatus.order)
    ).first()
