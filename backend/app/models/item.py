
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Item(SQLModel, table=True):
    __tablename__ = "item"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    owner_id: int | None = Field(default=None, foreign_key="user.id", nullable=False)

    owner: Optional["User"] = Relationship(back_populates="items")

