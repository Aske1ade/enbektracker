from enum import Enum
from typing import Type

from sqlalchemy import Enum as SAEnum


def sa_str_enum(enum_cls: Type[Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        native_enum=True,
    )


class SystemRole(str, Enum):
    USER = "user"
    SYSTEM_ADMIN = "system_admin"

    # Legacy values kept for backward-compatible deserialization during rollout.
    EXECUTOR = "executor"
    CONTROLLER = "controller"
    MANAGER = "manager"
    ADMIN = "admin"


class ProjectMemberRole(str, Enum):
    READER = "reader"
    EXECUTOR = "executor"
    CONTROLLER = "controller"
    MANAGER = "manager"

class TaskDeadlineState(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class TaskUrgencyState(str, Enum):
    OVERDUE = "overdue"
    CRITICAL = "critical"
    NORMAL = "normal"
    RESERVE = "reserve"


class TaskHistoryAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DUE_DATE_CHANGED = "due_date_changed"
    STATUS_CHANGED = "status_changed"
    ASSIGNEE_CHANGED = "assignee_changed"
    CLOSED = "closed"
    REOPENED = "reopened"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"


class NotificationType(str, Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_DUE_DATE_CHANGED = "task_due_date_changed"
    TASK_COMMENTED = "task_commented"
    TASK_DEADLINE_APPROACHING = "task_deadline_approaching"
    TASK_OVERDUE = "task_overdue"
    TASK_STATUS_CHANGED = "task_status_changed"
    SYSTEM = "system"


class DesktopEventType(str, Enum):
    ASSIGN = "assign"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    STATUS_CHANGED = "status_changed"
    CLOSE_REQUESTED = "close_requested"
    CLOSE_APPROVED = "close_approved"
    SYSTEM = "system"


class ProjectAccessSubjectType(str, Enum):
    USER = "user"
    GROUP = "group"
