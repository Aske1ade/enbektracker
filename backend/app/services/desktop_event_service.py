import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from app.models import DesktopEvent, DesktopEventType, Task
from app.repositories import desktop_events as desktop_event_repo

DUE_SOON_WINDOW = timedelta(days=1)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_due_soon(due_date: datetime, *, now: datetime | None = None) -> bool:
    reference = now or utcnow()
    return reference <= due_date <= (reference + DUE_SOON_WINDOW)


def build_task_deeplink(task_id: int) -> str:
    return f"/tasks/{task_id}"


def enqueue_event(
    session: Session,
    *,
    user_id: int,
    event_type: DesktopEventType,
    title: str,
    message: str,
    task_id: int | None = None,
    project_id: int | None = None,
    deeplink: str | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> DesktopEvent | None:
    if dedupe_key and desktop_event_repo.has_dedupe_key(
        session,
        user_id=user_id,
        dedupe_key=dedupe_key,
    ):
        return None

    event = DesktopEvent(
        user_id=user_id,
        task_id=task_id,
        project_id=project_id,
        event_type=event_type,
        title=title,
        message=message,
        deeplink=deeplink,
        payload_json=json.dumps(payload) if payload else None,
        dedupe_key=dedupe_key,
    )
    return desktop_event_repo.create_desktop_event(session, event)


def enqueue_task_event(
    session: Session,
    *,
    user_id: int,
    event_type: DesktopEventType,
    task: Task,
    title: str,
    message: str,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> DesktopEvent | None:
    return enqueue_event(
        session,
        user_id=user_id,
        event_type=event_type,
        task_id=task.id,
        project_id=task.project_id,
        title=title,
        message=message,
        deeplink=build_task_deeplink(task.id),
        payload=payload,
        dedupe_key=dedupe_key,
    )
