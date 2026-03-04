from sqlmodel import Session, func, select

from app.models import TaskAttachment


def list_task_attachments(
    session: Session,
    *,
    task_id: int,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[TaskAttachment], int]:
    count = session.exec(
        select(func.count())
        .select_from(TaskAttachment)
        .where(TaskAttachment.task_id == task_id)
    ).one()
    attachments = session.exec(
        select(TaskAttachment)
        .where(TaskAttachment.task_id == task_id)
        .order_by(TaskAttachment.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return attachments, count


def get_task_attachment(session: Session, attachment_id: int) -> TaskAttachment | None:
    return session.get(TaskAttachment, attachment_id)


def create_task_attachment(session: Session, attachment: TaskAttachment) -> TaskAttachment:
    session.add(attachment)
    session.commit()
    session.refresh(attachment)
    return attachment


def delete_task_attachment(session: Session, attachment: TaskAttachment) -> None:
    session.delete(attachment)
    session.commit()
