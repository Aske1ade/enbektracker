from datetime import timedelta

from fastapi import HTTPException, status

from app import crud
from app.core import security
from app.core.config import settings
from app.models import Token


def login_user(*, session, email: str, password: str) -> Token:
    user = crud.authenticate(session=session, email=email, password=password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id,
            expires_delta=access_token_expires,
        )
    )
