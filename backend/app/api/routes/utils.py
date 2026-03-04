from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from minio.error import S3Error
from pydantic.networks import EmailStr

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.integrations.minio_client import get_minio_client
from app.models import Message
from app.services import desktop_agent_service
from app.utils import generate_test_email, send_email

router = APIRouter()


@router.get("/health-check/")
def health_check() -> bool:
    """
    Health check endpoint for container orchestration and smoke checks.
    """
    return True


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/desktop-agent/download")
def desktop_agent_download(session: SessionDep):
    """
    Download desktop-agent installer.
    Priority:
      1) Uploaded binary in MinIO (managed via admin page)
      2) Local backend file path (DESKTOP_AGENT_BINARY_PATH)
      3) Redirect URL (DESKTOP_AGENT_DOWNLOAD_URL)
    """
    uploaded_meta = desktop_agent_service.get_uploaded_agent_meta(session)
    if uploaded_meta is not None:
        object_key = str(uploaded_meta.get("object_key") or "").strip()
        file_name = str(uploaded_meta.get("file_name") or "EnbekTracker-setup.exe")
        media_type = str(uploaded_meta.get("content_type") or "application/octet-stream")
        if object_key:
            try:
                object_stream = get_minio_client().get_object(
                    settings.MINIO_BUCKET,
                    object_key,
                )
            except S3Error:
                object_stream = None
            if object_stream is not None:
                headers = {
                    "Content-Disposition": (
                        f"attachment; filename*=UTF-8''{quote(file_name)}"
                    )
                }

                def iter_stream():
                    try:
                        while True:
                            chunk = object_stream.read(1024 * 1024)
                            if not chunk:
                                break
                            yield chunk
                    finally:
                        object_stream.close()
                        object_stream.release_conn()

                return StreamingResponse(
                    iter_stream(),
                    media_type=media_type,
                    headers=headers,
                )

    if settings.DESKTOP_AGENT_BINARY_PATH:
        binary_path = Path(settings.DESKTOP_AGENT_BINARY_PATH)
        if binary_path.is_file():
            return FileResponse(
                path=binary_path,
                media_type="application/vnd.microsoft.portable-executable",
                filename=binary_path.name,
            )

    if settings.DESKTOP_AGENT_DOWNLOAD_URL:
        return RedirectResponse(url=settings.DESKTOP_AGENT_DOWNLOAD_URL, status_code=307)

    raise HTTPException(status_code=404, detail="Desktop agent download is not configured")
