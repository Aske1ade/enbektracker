from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Permission(SQLModel, table=True):
    __tablename__ = "permission"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    name: str = Field(max_length=255)
    description: str | None = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    role_links: list["RolePermission"] = Relationship(back_populates="permission")

