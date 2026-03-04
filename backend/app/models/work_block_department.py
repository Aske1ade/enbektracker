from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkBlockDepartment(SQLModel, table=True):
    __tablename__ = "work_block_department"
    __table_args__ = (
        UniqueConstraint(
            "block_id",
            "department_id",
            name="uq_work_block_department_block_department",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    block_id: int = Field(foreign_key="work_block.id", nullable=False, index=True)
    department_id: int = Field(foreign_key="department.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    block: "WorkBlock" = Relationship(back_populates="departments")
    department: "Department" = Relationship(back_populates="block_links")
