from datetime import timedelta

from sqlmodel import Session, select

from app.core.db import engine
from app.models import DesktopEventType, NotificationType, Task, TaskAssignee, User
from app.services import desktop_event_service, system_settings_service
from app.services.notification_service import notify_user
from app.services.task_service import refresh_deadline_flags_for_open_tasks, utcnow


def _interval_time_slot_minutes(*, now_ts: float, interval_minutes: int) -> int:
    return int(now_ts // (interval_minutes * 60))


def _task_assignee_ids(session: Session, *, task: Task) -> set[int]:
    assignee_ids = {
        int(user_id)
        for user_id in session.exec(
            select(TaskAssignee.user_id).where(TaskAssignee.task_id == task.id)
        ).all()
    }
    if task.assignee_id is not None:
        assignee_ids.add(int(task.assignee_id))
    return assignee_ids


def send_deadline_notifications() -> None:
    now = utcnow()
    approaching_until = now + timedelta(days=1)

    with Session(engine) as session:
        refresh_deadline_flags_for_open_tasks(session)
        overdue_desktop_reminders_enabled = system_settings_service.get_bool(
            session,
            key=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDERS_ENABLED_KEY,
            default=True,
        )
        overdue_desktop_reminder_interval_minutes = system_settings_service.get_int(
            session,
            key=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MINUTES_KEY,
            default=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MIN,
        )
        overdue_desktop_reminder_interval_minutes = max(
            system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MIN,
            min(
                overdue_desktop_reminder_interval_minutes,
                system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MAX,
            ),
        )

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
            for assignee_id in _task_assignee_ids(session, task=task):
                assignee = session.get(User, assignee_id)
                if not assignee:
                    continue
                overdue_dedupe_key = (
                    f"task:{task.id}:overdue:{task.due_date.date().isoformat()}"
                )
                first_overdue_event = desktop_event_service.enqueue_task_event(
                    session,
                    user_id=assignee.id,
                    event_type=DesktopEventType.OVERDUE,
                    task=task,
                    title="Задача просрочена",
                    message=f"Задача '{task.title}' просрочена",
                    payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
                    dedupe_key=overdue_dedupe_key,
                )
                if first_overdue_event is not None:
                    # Keep email/in-app notification single-shot; repeated alerts are desktop only.
                    notify_user(
                        session,
                        user_id=assignee.id,
                        notification_type=NotificationType.TASK_OVERDUE,
                        title="Задача просрочена",
                        message=f"Задача '{task.title}' просрочена",
                        payload={"task_id": task.id},
                        user_email=assignee.email,
                    )
                    continue
                if not overdue_desktop_reminders_enabled:
                    continue
                time_slot = _interval_time_slot_minutes(
                    now_ts=now.timestamp(),
                    interval_minutes=overdue_desktop_reminder_interval_minutes,
                )
                desktop_event_service.enqueue_task_event(
                    session,
                    user_id=assignee.id,
                    event_type=DesktopEventType.OVERDUE,
                    task=task,
                    title="Задача просрочена",
                    message=f"Задача '{task.title}' просрочена",
                    payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
                    dedupe_key=(
                        f"task:{task.id}:overdue:repeat:"
                        f"{overdue_desktop_reminder_interval_minutes}:{time_slot}"
                    ),
                )


if __name__ == "__main__":
    send_deadline_notifications()
