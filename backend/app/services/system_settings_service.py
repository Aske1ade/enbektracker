from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import SystemSetting

TASK_ALLOW_BACKDATED_CREATION_KEY = "tasks.allow_backdated_creation"
DEMO_DATA_LOCKED_KEY = "demo_data.locked"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_record(session: Session, *, key: str) -> SystemSetting | None:
    return session.exec(select(SystemSetting).where(SystemSetting.key == key)).first()


def get_str(
    session: Session,
    *,
    key: str,
    default: str | None = None,
) -> str | None:
    record = _get_record(session, key=key)
    if record is None:
        return default
    return record.value


def set_str(
    session: Session,
    *,
    key: str,
    value: str,
) -> str:
    record = _get_record(session, key=key)
    now = utcnow()
    if record is None:
        record = SystemSetting(
            key=key,
            value=value,
            created_at=now,
            updated_at=now,
        )
    else:
        record.value = value
        record.updated_at = now
    session.add(record)
    session.commit()
    return value


def delete_key(session: Session, *, key: str) -> None:
    record = _get_record(session, key=key)
    if record is None:
        return
    session.delete(record)
    session.commit()


def get_bool(
    session: Session,
    *,
    key: str,
    default: bool = False,
) -> bool:
    record = _get_record(session, key=key)
    if record is None:
        return default
    return str(record.value).strip().lower() in {"1", "true", "yes", "on"}


def set_bool(
    session: Session,
    *,
    key: str,
    value: bool,
) -> bool:
    record = _get_record(session, key=key)
    now = utcnow()
    if record is None:
        record = SystemSetting(
            key=key,
            value="true" if value else "false",
            created_at=now,
            updated_at=now,
        )
    else:
        record.value = "true" if value else "false"
        record.updated_at = now
    session.add(record)
    session.commit()
    return value
