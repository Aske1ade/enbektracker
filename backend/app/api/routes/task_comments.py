from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.models import Task
from app.repositories import task_comments as comment_repo
from app.repositories import tasks as task_repo
from app.schemas.task import (
    TaskCommentCreate,
    TaskCommentPublic,
    TaskCommentsPublic,
    TaskCommentUpdate,
)
from app.services import rbac_service, task_service

router = APIRouter(prefix="/task-comments", tags=["task-comments"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/", response_model=TaskCommentsPublic)
def read_task_comments(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> TaskCommentsPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    comments, count = comment_repo.list_task_comments(
        session,
        task_id=task_id,
        skip=skip,
        limit=limit,
    )

    return TaskCommentsPublic(
        data=[
            TaskCommentPublic.model_validate(c).model_copy(
                update={
                    "author_name": (
                        c.author.full_name or c.author.email if c.author is not None else None
                    ),
                    "author_email": c.author.email if c.author is not None else None,
                }
            )
            for c in comments
        ],
        count=count,
    )


@router.post("/", response_model=TaskCommentPublic)
def create_task_comment(
    payload: TaskCommentCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TaskCommentPublic:
    task = task_repo.get_task(session, payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    created = task_service.add_task_comment(
        session,
        task=task,
        actor=current_user,
        comment=payload.comment,
    )
    return TaskCommentPublic.model_validate(created).model_copy(
        update={
            "author_name": current_user.full_name or current_user.email,
            "author_email": current_user.email,
        }
    )


@router.patch("/{comment_id}", response_model=TaskCommentPublic)
def update_task_comment(
    comment_id: int,
    payload: TaskCommentUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TaskCommentPublic:
    comment = comment_repo.get_task_comment(session, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_id != current_user.id and not rbac_service.is_system_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    comment.comment = payload.comment
    comment.updated_at = utcnow()
    updated = comment_repo.update_task_comment(session, comment)
    return TaskCommentPublic.model_validate(updated).model_copy(
        update={
            "author_name": (
                updated.author.full_name or updated.author.email
                if updated.author is not None
                else None
            ),
            "author_email": updated.author.email if updated.author is not None else None,
        }
    )


@router.delete("/{comment_id}")
def delete_task_comment(
    comment_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    comment = comment_repo.get_task_comment(session, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_id != current_user.id and not rbac_service.is_system_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    comment_repo.delete_task_comment(session, comment)
    return {"message": "Comment deleted successfully"}
