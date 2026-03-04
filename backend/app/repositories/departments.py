from sqlmodel import Session, func, select

from app.models import Department


def list_departments(session: Session, *, skip: int = 0, limit: int = 100) -> tuple[list[Department], int]:
    count = session.exec(select(func.count()).select_from(Department)).one()
    departments = session.exec(select(Department).offset(skip).limit(limit)).all()
    return departments, count


def get_department(session: Session, department_id: int) -> Department | None:
    return session.get(Department, department_id)


def create_department(session: Session, department: Department) -> Department:
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


def update_department(session: Session, department: Department) -> Department:
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


def delete_department(session: Session, department: Department) -> None:
    session.delete(department)
    session.commit()
