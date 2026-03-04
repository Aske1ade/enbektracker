from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkBlockManager(SQLModel, table=True):
    __tablename__ = "work_block_manager"
    __table_args__ = (
        UniqueConstraint("block_id", "user_id", name="uq_work_block_manager"),
    )

    id: int | None = Field(default=None, primary_key=True)
    block_id: int = Field(foreign_key="work_block.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    block: "WorkBlock" = Relationship(back_populates="managers")
    user: "User" = Relationship(back_populates="block_memberships")
