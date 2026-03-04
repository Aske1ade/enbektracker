from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemSetting(SQLModel, table=True):
    __tablename__ = "system_setting"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True, nullable=False)
    value: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
