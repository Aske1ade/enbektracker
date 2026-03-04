import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.services import system_settings_service

DESKTOP_AGENT_ASSET_KEY = "desktop_agent.asset"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_uploaded_agent_meta(session: Session) -> dict[str, Any] | None:
    raw = system_settings_service.get_str(
        session,
        key=DESKTOP_AGENT_ASSET_KEY,
        default=None,
    )
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    object_key = str(payload.get("object_key") or "").strip()
    file_name = str(payload.get("file_name") or "").strip()
    if not object_key or not file_name:
        return None
    content_type = str(payload.get("content_type") or "").strip()
    size_bytes_raw = payload.get("size_bytes")
    uploaded_at = str(payload.get("uploaded_at") or "").strip()
    try:
        size_bytes = int(size_bytes_raw)
    except (TypeError, ValueError):
        size_bytes = 0
    return {
        "object_key": object_key,
        "file_name": file_name,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": max(0, size_bytes),
        "uploaded_at": uploaded_at or None,
    }


def set_uploaded_agent_meta(
    session: Session,
    *,
    object_key: str,
    file_name: str,
    content_type: str,
    size_bytes: int,
) -> dict[str, Any]:
    payload = {
        "object_key": object_key,
        "file_name": file_name,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": max(0, int(size_bytes)),
        "uploaded_at": utcnow().isoformat(),
    }
    system_settings_service.set_str(
        session,
        key=DESKTOP_AGENT_ASSET_KEY,
        value=json.dumps(payload),
    )
    return payload


def clear_uploaded_agent_meta(session: Session) -> None:
    system_settings_service.delete_key(session, key=DESKTOP_AGENT_ASSET_KEY)
