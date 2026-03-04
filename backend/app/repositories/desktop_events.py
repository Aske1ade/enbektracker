from sqlmodel import Session, select

from app.models import DesktopEvent


def create_desktop_event(session: Session, event: DesktopEvent) -> DesktopEvent:
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def has_dedupe_key(
    session: Session,
    *,
    user_id: int,
    dedupe_key: str,
) -> bool:
    existing = session.exec(
        select(DesktopEvent.id).where(
            DesktopEvent.user_id == user_id,
            DesktopEvent.dedupe_key == dedupe_key,
        )
    ).first()
    return existing is not None


def list_user_events_after_cursor(
    session: Session,
    *,
    user_id: int,
    cursor: int | None,
    limit: int,
) -> tuple[list[DesktopEvent], int | None, bool]:
    statement = select(DesktopEvent).where(DesktopEvent.user_id == user_id)
    if cursor is not None:
        statement = statement.where(DesktopEvent.id > cursor)

    rows = session.exec(
        statement.order_by(DesktopEvent.id.asc()).limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    data = rows[:limit]
    next_cursor = data[-1].id if data else cursor
    return data, next_cursor, has_more
