"""Shared FastAPI dependencies: database session, current user, role checks, paging."""
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import InvalidToken, PermissionDenied
from app.core.security import decode_access_token
from app.models import User, UserRole
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: DbSession) -> User:
    # The user is loaded on every request, so a deactivated account or a
    # changed role takes effect immediately, even with an unexpired token.
    user = UserRepository(session).get_by_id(decode_access_token(token))
    if user is None or not user.is_active:
        raise InvalidToken()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole) -> Callable[[User], User]:
    def check_role(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDenied()
        return user

    return check_role


CurrentAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
CurrentCustomer = Annotated[User, Depends(require_role(UserRole.CUSTOMER))]

SearchTerm = Annotated[str | None, Query(max_length=100)]
CategoryFilter = Annotated[int | None, Query(ge=1)]
PageNumber = Annotated[int, Query(ge=1, le=1_000_000)]
PageSize = Annotated[int, Query(ge=1, le=100)]
