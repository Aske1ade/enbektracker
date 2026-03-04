import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.security import get_password_hash
from app.models import SystemRole, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_superuser() -> None:
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        if user is None:
            user = User(
                email=settings.FIRST_SUPERUSER,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_active=True,
                is_superuser=True,
                system_role=SystemRole.SYSTEM_ADMIN,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info("Created superuser %s (id=%s)", user.email, user.id)
            return

        user.hashed_password = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
        user.is_active = True
        user.is_superuser = True
        user.system_role = SystemRole.SYSTEM_ADMIN
        session.add(user)
        session.commit()
        logger.info("Updated superuser %s (id=%s)", user.email, user.id)


if __name__ == "__main__":
    sync_superuser()
