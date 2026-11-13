"""Endpoints for the logged-in user."""
from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def read_profile(user: CurrentUser) -> User:
    """Return the profile of the logged-in user."""
    return user
