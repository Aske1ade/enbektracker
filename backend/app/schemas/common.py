from enum import Enum

from sqlmodel import SQLModel


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class MessageResponse(SQLModel):
    message: str


class ValidationIssue(SQLModel):
    loc: list[str | int]
    msg: str
    type: str


class APIErrorResponse(SQLModel):
    code: str
    detail: str
    request_id: str
    issues: list[ValidationIssue] | None = None
