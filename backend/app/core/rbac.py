from app.models import ProjectMemberRole, SystemRole

MANAGER_ROLES = {SystemRole.MANAGER, SystemRole.ADMIN}
CONTROLLER_ROLES = {SystemRole.CONTROLLER, SystemRole.MANAGER, SystemRole.ADMIN}
EXECUTION_ROLES = {
    SystemRole.EXECUTOR,
    SystemRole.CONTROLLER,
    SystemRole.MANAGER,
    SystemRole.ADMIN,
}

PROJECT_MANAGER_ROLES = {ProjectMemberRole.MANAGER}
PROJECT_CONTROLLER_ROLES = {ProjectMemberRole.CONTROLLER, ProjectMemberRole.MANAGER}
PROJECT_EXECUTOR_ROLES = {
    ProjectMemberRole.READER,
    ProjectMemberRole.EXECUTOR,
    ProjectMemberRole.CONTROLLER,
    ProjectMemberRole.MANAGER,
}
