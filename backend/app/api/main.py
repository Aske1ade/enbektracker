from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    blocks,
    calendar,
    dashboards,
    desktop_events,
    departments,
    items,
    login,
    notifications,
    organizations,
    project_statuses,
    projects,
    roles,
    reports,
    task_policy,
    task_attachments,
    task_comments,
    tasks,
    users,
    utils,
)

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(items.router, prefix="/items", tags=["items"])

api_router.include_router(departments.router)
api_router.include_router(projects.router)
api_router.include_router(project_statuses.router)
api_router.include_router(tasks.router)
api_router.include_router(task_policy.router)
api_router.include_router(task_comments.router)
api_router.include_router(task_attachments.router)
api_router.include_router(blocks.router)
api_router.include_router(organizations.router)
api_router.include_router(dashboards.router)
api_router.include_router(reports.router)
api_router.include_router(roles.router)
api_router.include_router(calendar.router)
api_router.include_router(notifications.router)
api_router.include_router(desktop_events.router)
