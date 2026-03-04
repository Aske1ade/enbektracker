from datetime import datetime

from sqlmodel import Session, func, select

from app.models import Notification


def list_user_notifications(
    session: Session,
    *,
    user_id: int,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Notification], int]:
    count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id)
    ).one()
    notifications = session.exec(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return notifications, count


def create_notification(session: Session, notification: Notification) -> Notification:
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def get_notification(session: Session, notification_id: int) -> Notification | None:
    return session.get(Notification, notification_id)


def mark_as_read(session: Session, notification: Notification) -> Notification:
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification
