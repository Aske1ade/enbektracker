from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from minio.error import S3Error

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.integrations.minio_client import get_minio_client
from app.models import Task, TaskHistoryAction
from app.repositories import task_attachments as attachment_repo
from app.repositories import tasks as task_repo
from app.schemas.task import (
    TaskAttachmentPublic,
    TaskAttachmentsPublic,
)
from app.services import audit_service, attachment_service, rbac_service

router = APIRouter(prefix="/task-attachments", tags=["task-attachments"])


@router.get("/", response_model=TaskAttachmentsPublic)
def read_task_attachments(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> TaskAttachmentsPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    attachments, count = attachment_repo.list_task_attachments(
        session,
        task_id=task_id,
        skip=skip,
        limit=limit,
    )

    return TaskAttachmentsPublic(
        data=[TaskAttachmentPublic.model_validate(a) for a in attachments],
        count=count,
    )


@router.post("/upload", response_model=TaskAttachmentPublic)
async def upload_attachment(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> TaskAttachmentPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    created = await attachment_service.upload_task_attachment(
        session,
        task_id=task_id,
        uploader_id=current_user.id,
        file=file,
    )

    audit_service.add_task_history(
        session,
        task_id=task.id,
        actor_id=current_user.id,
        action=TaskHistoryAction.ATTACHMENT_ADDED,
        new_value=created.file_name,
    )

    return TaskAttachmentPublic.model_validate(created)


@router.get("/{attachment_id}/download-url")
def get_download_url(
    attachment_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    attachment = attachment_repo.get_task_attachment(session, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    task = session.get(Task, attachment.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Return backend proxy URL so client does not need direct network access to MinIO.
    url = f"{settings.API_V1_STR}/task-attachments/{attachment_id}/download"
    return {"url": url}


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Response:
    attachment = attachment_repo.get_task_attachment(session, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    task = session.get(Task, attachment.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    client = get_minio_client()
    object_stream = None
    try:
        object_stream = client.get_object(settings.MINIO_BUCKET, attachment.object_key)
        content = object_stream.read()
    except S3Error:
        raise HTTPException(status_code=502, detail="Attachment storage unavailable")
    finally:
        if object_stream is not None:
            object_stream.close()
            object_stream.release_conn()

    quoted_name = quote(attachment.file_name)
    return Response(
        content=content,
        media_type=attachment.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{attachment.file_name}\"; "
                f"filename*=UTF-8''{quoted_name}"
            ),
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    attachment = attachment_repo.get_task_attachment(session, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    task = session.get(Task, attachment.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if attachment.uploaded_by_id != current_user.id and not rbac_service.is_system_admin(current_user):
        rbac_service.require_project_controller_or_manager(
            session,
            project_id=task.project_id,
            user=current_user,
        )

    attachment_service.delete_task_attachment_from_storage(attachment)
    attachment_repo.delete_task_attachment(session, attachment)
    return {"message": "Attachment deleted successfully"}
