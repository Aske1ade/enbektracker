from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.repositories import notifications as notification_repo
from app.schemas.notification import NotificationPublic, NotificationsPublic
from app.services import rbac_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
def read_my_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> NotificationsPublic:
    notifications, count = notification_repo.list_user_notifications(
        session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return NotificationsPublic(
        data=[NotificationPublic.model_validate(n) for n in notifications],
        count=count,
    )


@router.post("/{notification_id}/read", response_model=NotificationPublic)
def mark_notification_as_read(
    notification_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> NotificationPublic:
    notification = notification_repo.get_notification(session, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.user_id != current_user.id and not rbac_service.is_system_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    updated = notification_repo.mark_as_read(session, notification)
    return NotificationPublic.model_validate(updated)
