from sqlmodel import Session, func, select

from app.models import TaskComment


def list_task_comments(
    session: Session,
    *,
    task_id: int,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[TaskComment], int]:
    count = session.exec(
        select(func.count()).select_from(TaskComment).where(TaskComment.task_id == task_id)
    ).one()
    comments = session.exec(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return comments, count


def get_task_comment(session: Session, comment_id: int) -> TaskComment | None:
    return session.get(TaskComment, comment_id)


def create_task_comment(session: Session, comment: TaskComment) -> TaskComment:
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return comment


def update_task_comment(session: Session, comment: TaskComment) -> TaskComment:
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return comment


def delete_task_comment(session: Session, comment: TaskComment) -> None:
    session.delete(comment)
    session.commit()
