"""Public endpoints for registering and logging in."""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.models import User, UserRole
from app.schemas.user import Token, UserCreate, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, session: DbSession) -> User:
    """Create a customer account. Public sign-up can only ever create customers."""
    return AuthService(session).register(
        UserRole.CUSTOMER, data.email, data.password, data.full_name
    )


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: DbSession) -> Token:
    """Log in with your email as the username, and receive an access token."""
    return Token(access_token=AuthService(session).login(form.username, form.password))
