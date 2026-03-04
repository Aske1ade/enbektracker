from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    Department,
    DemoSeedEntity,
    DesktopEvent,
    DisciplineCertificateTemplate,
    GroupMembership,
    Item,
    Notification,
    OrgGroup,
    Organization,
    OrganizationMembership,
    Permission,
    Project,
    ProjectDepartment,
    ProjectMember,
    ProjectSubjectRole,
    ProjectStatus,
    ReportTemplate,
    Role,
    RolePermission,
    Task,
    TaskAttachment,
    TaskComment,
    TaskHistory,
    User,
    WorkBlock,
    WorkBlockDepartment,
    WorkBlockManager,
    WorkBlockProject,
)
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        # Avoid destructive cleanup against local/dev databases.
        if settings.ENVIRONMENT != "test":
            return
        # Cleanup order matters because of FK constraints.
        for model in [
            Notification,
            DesktopEvent,
            DemoSeedEntity,
            ProjectSubjectRole,
            RolePermission,
            Permission,
            GroupMembership,
            OrganizationMembership,
            TaskHistory,
            TaskAttachment,
            TaskComment,
            Task,
            WorkBlockManager,
            WorkBlockDepartment,
            WorkBlockProject,
            ProjectDepartment,
            ProjectMember,
            ProjectStatus,
            Project,
            OrgGroup,
            Organization,
            WorkBlock,
            ReportTemplate,
            DisciplineCertificateTemplate,
            Item,
            User,
            Department,
            Role,
        ]:
            session.execute(delete(model))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
