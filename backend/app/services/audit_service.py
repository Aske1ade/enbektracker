from sqlmodel import Session

from app.models import TaskHistory, TaskHistoryAction


def add_task_history(
    session: Session,
    *,
    task_id: int,
    actor_id: int,
    action: TaskHistoryAction,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> TaskHistory:
    history = TaskHistory(
        task_id=task_id,
        actor_id=actor_id,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )
    session.add(history)
    session.commit()
    session.refresh(history)
    return history
