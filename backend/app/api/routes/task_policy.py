from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.task import TaskPolicyPublic
from app.services import system_settings_service

router = APIRouter(prefix="/task-policy", tags=["task-policy"])


@router.get("", response_model=TaskPolicyPublic)
def get_task_policy(session: SessionDep, current_user: CurrentUser) -> TaskPolicyPublic:
    allow_task_scoped_controller_assignment = system_settings_service.get_bool(
        session,
        key=system_settings_service.TASK_ALLOW_TASK_SCOPED_CONTROLLER_ASSIGNMENT_KEY,
        default=False,
    )
    return TaskPolicyPublic(
        allow_task_scoped_controller_assignment=allow_task_scoped_controller_assignment,
    )
