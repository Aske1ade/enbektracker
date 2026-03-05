from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col, delete, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Department,
    DesktopEvent,
    DisciplineCertificateTemplate,
    GroupMembership,
    Item,
    Message,
    Notification,
    OrgGroup,
    OrganizationMembership,
    Project,
    ProjectMember,
    ProjectSubjectRole,
    ReportTemplate,
    Task,
    TaskAssignee,
    TaskAttachment,
    TaskComment,
    TaskHistory,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    WorkBlockManager,
    SystemRole,
)
from app.services import rbac_service
from app.utils import generate_new_account_email, send_email

router = APIRouter()


@router.get("/", response_model=UsersPublic)
def read_users(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    statement = select(User)
    if not rbac_service.is_system_admin(current_user):
        allowed_user_ids = rbac_service.get_same_group_user_ids(session, user=current_user)
        count_statement = count_statement.where(
            User.is_active.is_(True),
            User.id.in_(sorted(allowed_user_ids)),
        )
        statement = statement.where(
            User.is_active.is_(True),
            User.id.in_(sorted(allowed_user_ids)),
        )
    count = session.exec(count_statement).one()
    users = session.exec(statement.offset(skip).limit(limit)).all()

    return UsersPublic(data=users, count=count)


@router.post("/", response_model=UserPublic)
def create_user(*, session: SessionDep, current_user: CurrentUser, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    rbac_service.require_system_admin(current_user)

    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    current_user.must_change_password = False
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    can_assign_tasks = rbac_service.can_assign_task_to_others(
        session=session,
        user=current_user,
    )
    payload = UserPublic.model_validate(current_user)
    return payload.model_copy(update={"can_assign_tasks": can_assign_tasks})


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Нельзя удалить текущего пользователя"
        )
    statement = delete(Item).where(col(Item.owner_id) == current_user.id)
    session.exec(statement)  # type: ignore
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open user registration is forbidden on this server",
        )
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: int, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not rbac_service.is_system_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: int,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    rbac_service.require_system_admin(current_user)

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    if "department_id" in user_in.model_fields_set and user_in.department_id is not None:
        if session.get(Department, user_in.department_id) is None:
            raise HTTPException(status_code=400, detail="Указанный департамент не найден")
    if "primary_group_id" in user_in.model_fields_set and user_in.primary_group_id is not None:
        if session.get(OrgGroup, user_in.primary_group_id) is None:
            raise HTTPException(status_code=400, detail="Указанная группа не найдена")

    # Safety guard: an administrator cannot accidentally remove own admin access.
    if db_user.id == current_user.id:
        next_is_active = (
            user_in.is_active if "is_active" in user_in.model_fields_set else db_user.is_active
        )
        next_is_superuser = (
            user_in.is_superuser
            if "is_superuser" in user_in.model_fields_set
            else db_user.is_superuser
        )
        next_system_role = (
            user_in.system_role
            if "system_role" in user_in.model_fields_set and user_in.system_role is not None
            else db_user.system_role
        )
        next_is_admin_like = next_is_superuser or next_system_role in {
            SystemRole.SYSTEM_ADMIN,
            SystemRole.ADMIN,
        }
        if not next_is_active:
            raise HTTPException(
                status_code=400,
                detail="Нельзя деактивировать собственный административный аккаунт",
            )
        if not next_is_admin_like:
            raise HTTPException(
                status_code=400,
                detail="Нельзя снять у себя административные права",
            )

    try:
        db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    except SQLAlchemyError as exc:
        session.rollback()
        raw_detail = getattr(exc, "orig", None) or str(exc)
        raise HTTPException(
            status_code=409,
            detail=f"Не удалось обновить пользователя: {raw_detail}",
        ) from exc
    return db_user


@router.delete("/{user_id}")
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: int
) -> Message:
    """
    Delete a user.
    """
    rbac_service.require_system_admin(current_user)

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Нельзя удалить текущего пользователя"
        )
    try:
        # Keep historical/project data consistent while removing user account.
        session.exec(
            delete(ProjectSubjectRole).where(
                ProjectSubjectRole.subject_user_id == user_id
            )
        )
        session.exec(delete(ProjectMember).where(ProjectMember.user_id == user_id))
        session.exec(
            delete(OrganizationMembership).where(OrganizationMembership.user_id == user_id)
        )
        session.exec(delete(GroupMembership).where(GroupMembership.user_id == user_id))
        session.exec(delete(WorkBlockManager).where(WorkBlockManager.user_id == user_id))
        session.exec(delete(TaskAssignee).where(TaskAssignee.user_id == user_id))

        if current_user.id is not None:
            session.exec(
                Task.__table__.update()
                .where(Task.creator_id == user_id)
                .values(creator_id=int(current_user.id))
            )
            session.exec(
                TaskComment.__table__.update()
                .where(TaskComment.author_id == user_id)
                .values(author_id=int(current_user.id))
            )
            session.exec(
                TaskAttachment.__table__.update()
                .where(TaskAttachment.uploaded_by_id == user_id)
                .values(uploaded_by_id=int(current_user.id))
            )
            session.exec(
                TaskHistory.__table__.update()
                .where(TaskHistory.actor_id == user_id)
                .values(actor_id=int(current_user.id))
            )

        session.exec(
            Task.__table__.update()
            .where(Task.assignee_id == user_id)
            .values(assignee_id=None)
        )
        session.exec(
            Task.__table__.update()
            .where(Task.controller_id == user_id)
            .values(controller_id=None)
        )
        session.exec(
            Project.__table__.update()
            .where(Project.created_by_id == user_id)
            .values(created_by_id=None)
        )
        session.exec(
            ReportTemplate.__table__.update()
            .where(ReportTemplate.created_by_id == user_id)
            .values(created_by_id=None)
        )
        session.exec(
            DisciplineCertificateTemplate.__table__.update()
            .where(DisciplineCertificateTemplate.created_by_id == user_id)
            .values(created_by_id=None)
        )

        session.exec(delete(DesktopEvent).where(DesktopEvent.user_id == user_id))
        session.exec(delete(Notification).where(Notification.user_id == user_id))
        session.exec(delete(Item).where(col(Item.owner_id) == user_id))  # type: ignore

        session.delete(user)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить пользователя из-за связанных данных: {exc.orig}",
        ) from exc

    return Message(message="User deleted successfully")
