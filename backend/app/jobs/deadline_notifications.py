from datetime import timedelta

from sqlmodel import Session, select

from app.core.db import engine
from app.models import DesktopEventType, NotificationType, Task, User
from app.services import desktop_event_service
from app.services.notification_service import notify_user
from app.services.task_service import refresh_deadline_flags_for_open_tasks, utcnow


def send_deadline_notifications() -> None:
    now = utcnow()
    approaching_until = now + timedelta(days=1)

    with Session(engine) as session:
        refresh_deadline_flags_for_open_tasks(session)

        approaching_tasks = session.exec(
            select(Task).where(
                Task.due_date >= now,
                Task.due_date <= approaching_until,
                Task.is_overdue.is_(False),
                Task.closed_at.is_(None),
            )
        ).all()

        overdue_tasks = session.exec(
            select(Task).where(Task.is_overdue.is_(True), Task.closed_at.is_(None))
        ).all()

        for task in approaching_tasks:
            if not task.assignee_id:
                continue
            assignee = session.get(User, task.assignee_id)
            if not assignee:
                continue
            notify_user(
                session,
                user_id=assignee.id,
                notification_type=NotificationType.TASK_DEADLINE_APPROACHING,
                title="Срок задачи скоро наступит",
                message=f"Задача '{task.title}' скоро просрочится",
                payload={"task_id": task.id},
                user_email=assignee.email,
            )
            desktop_event_service.enqueue_task_event(
                session,
                user_id=assignee.id,
                event_type=DesktopEventType.DUE_SOON,
                task=task,
                title="Срок задачи скоро наступит",
                message=f"Задача '{task.title}' скоро просрочится",
                payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
                dedupe_key=f"task:{task.id}:due_soon:{task.due_date.date().isoformat()}",
            )

        for task in overdue_tasks:
            if not task.assignee_id:
                continue
            assignee = session.get(User, task.assignee_id)
            if not assignee:
                continue
            notify_user(
                session,
                user_id=assignee.id,
                notification_type=NotificationType.TASK_OVERDUE,
                title="Задача просрочена",
                message=f"Задача '{task.title}' просрочена",
                payload={"task_id": task.id},
                user_email=assignee.email,
            )
            desktop_event_service.enqueue_task_event(
                session,
                user_id=assignee.id,
                event_type=DesktopEventType.OVERDUE,
                task=task,
                title="Задача просрочена",
                message=f"Задача '{task.title}' просрочена",
                payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
                dedupe_key=f"task:{task.id}:overdue:{task.due_date.date().isoformat()}",
            )


if __name__ == "__main__":
    send_deadline_notifications()
