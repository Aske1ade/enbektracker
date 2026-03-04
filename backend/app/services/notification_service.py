import json

from sqlmodel import Session

from app.integrations.email_sender import send_notification_email
from app.models import Notification, NotificationType, User
from app.repositories import notifications as notification_repo


def _render_email_html(title: str, message: str) -> str:
    return f"<h3>{title}</h3><p>{message}</p>"


def notify_user(
    session: Session,
    *,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    payload: dict | None = None,
    user_email: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        payload_json=json.dumps(payload) if payload else None,
    )
    created = notification_repo.create_notification(session, notification)

    if user_email:
        send_notification_email(
            email_to=user_email,
            subject=title,
            body=_render_email_html(title, message),
        )

    return created


def notify_users(
    session: Session,
    *,
    users: list[User],
    notification_type: NotificationType,
    title: str,
    message: str,
    payload: dict | None = None,
) -> list[Notification]:
    result: list[Notification] = []
    for user in users:
        result.append(
            notify_user(
                session,
                user_id=user.id,
                notification_type=notification_type,
                title=title,
                message=message,
                payload=payload,
                user_email=user.email,
            )
        )
    return result
