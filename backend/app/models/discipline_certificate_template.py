
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DisciplineCertificateTemplate(SQLModel, table=True):
    __tablename__ = "discipline_certificate_template"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str | None = None
    template_json: str | None = None
    created_by_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
