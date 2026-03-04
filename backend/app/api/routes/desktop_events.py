from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.repositories import desktop_events as desktop_event_repo
from app.schemas.desktop_event import DesktopEventPublic, DesktopEventsPollPublic

router = APIRouter(prefix="/desktop-events", tags=["desktop-events"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/poll", response_model=DesktopEventsPollPublic)
def poll_desktop_events(
    session: SessionDep,
    current_user: CurrentUser,
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> DesktopEventsPollPublic:
    events, next_cursor, has_more = desktop_event_repo.list_user_events_after_cursor(
        session,
        user_id=current_user.id,
        cursor=cursor,
        limit=limit,
    )
    return DesktopEventsPollPublic(
        data=[DesktopEventPublic.model_validate(event) for event in events],
        next_cursor=next_cursor,
        has_more=has_more,
        server_time=utcnow(),
    )
