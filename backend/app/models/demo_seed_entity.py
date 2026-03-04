from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DemoSeedEntity(SQLModel, table=True):
    __tablename__ = "demo_seed_entity"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "entity_type",
            "entity_id",
            name="uq_demo_seed_entity_batch_type_id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True, nullable=False)
    entity_type: str = Field(index=True, nullable=False)
    entity_id: int = Field(index=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
