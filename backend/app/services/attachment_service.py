import io
import mimetypes
import re
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from minio.error import S3Error
from sqlmodel import Session

from app.core.config import settings
from app.integrations.minio_client import ensure_bucket_exists, get_minio_client
from app.models import TaskAttachment
from app.repositories import task_attachments as attachment_repo

FILENAME_MAX_LEN = 120
FILENAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
FALLBACK_ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/csv",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-zip-compressed",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/svg+xml",
    # Browser/OS fallback for unknown binaries.
    "application/octet-stream",
}


def _build_object_key(task_id: int, filename: str) -> str:
    return f"tasks/{task_id}/{uuid4()}-{filename}"


def _normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        return "application/octet-stream"
    return content_type.split(";", maxsplit=1)[0].strip().lower()


def _sanitize_attachment_filename(file_name: str) -> str:
    basename = file_name.replace("\\", "/").split("/")[-1].strip()
    if not basename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attachment file name is required",
        )

    sanitized = FILENAME_SANITIZE_PATTERN.sub("_", basename)
    sanitized = sanitized.strip("._")
    if not sanitized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attachment file name is invalid",
        )

    if len(sanitized) > FILENAME_MAX_LEN:
        if "." in sanitized:
            stem, ext = sanitized.rsplit(".", maxsplit=1)
            ext_with_dot = f".{ext[:16]}"
            max_stem_len = max(1, FILENAME_MAX_LEN - len(ext_with_dot))
            sanitized = f"{stem[:max_stem_len]}{ext_with_dot}"
        else:
            sanitized = sanitized[:FILENAME_MAX_LEN]
    return sanitized


def _validate_attachment(*, content: bytes, file_name: str, content_type: str | None) -> None:
    if not file_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attachment file name is required",
        )

    max_size_bytes = settings.ATTACHMENTS_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Attachment is too large. Max size is {settings.ATTACHMENTS_MAX_SIZE_MB} MB",
        )

    allowed_types = {
        item.lower().strip()
        for item in settings.ATTACHMENTS_ALLOWED_CONTENT_TYPES
        if item and item.strip()
    }
    if "*" in allowed_types or "*/*" in allowed_types:
        return
    allowed_types |= FALLBACK_ALLOWED_CONTENT_TYPES
    if allowed_types:
        normalized_type = _normalize_content_type(content_type)
        if normalized_type not in allowed_types:
            guessed_type, _ = mimetypes.guess_type(file_name, strict=False)
            guessed_normalized = _normalize_content_type(guessed_type)
            if guessed_normalized in allowed_types:
                return
            if normalized_type.startswith(
                ("application/", "image/", "text/", "audio/", "video/")
            ):
                return
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Attachment content type is not allowed",
            )


async def upload_task_attachment(
    session: Session,
    *,
    task_id: int,
    uploader_id: int,
    file: UploadFile,
) -> TaskAttachment:
    ensure_bucket_exists(settings.MINIO_BUCKET)
    content = await file.read()
    file_name = _sanitize_attachment_filename(file.filename or "attachment")
    normalized_content_type = _normalize_content_type(file.content_type)
    _validate_attachment(
        content=content,
        file_name=file_name,
        content_type=normalized_content_type,
    )
    object_key = _build_object_key(task_id, file_name)

    client = get_minio_client()
    try:
        client.put_object(
            settings.MINIO_BUCKET,
            object_key,
            io.BytesIO(content),
            length=len(content),
            content_type=normalized_content_type,
        )
    except S3Error:
        raise

    attachment = TaskAttachment(
        task_id=task_id,
        uploaded_by_id=uploader_id,
        file_name=file_name,
        object_key=object_key,
        content_type=normalized_content_type,
        size_bytes=len(content),
    )
    return attachment_repo.create_task_attachment(session, attachment)


def delete_task_attachment_from_storage(attachment: TaskAttachment) -> None:
    client = get_minio_client()
    try:
        client.remove_object(settings.MINIO_BUCKET, attachment.object_key)
    except S3Error:
        # Keep DB consistency first; storage cleanup can be retried by background jobs.
        pass
