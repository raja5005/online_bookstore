"""Registration and login rules."""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import is_duplicate_entry
from app.core.exceptions import EmailAlreadyRegistered, InvalidCredentials
from app.core.security import create_access_token, spend_password_check_time, verify_password
from app.models import User, UserRole
from app.patterns.user_factory import UserFactory
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    def register(self, role: UserRole, email: str, password: str, full_name: str) -> User:
        user = UserFactory.create_user(role, email, password, full_name)
        self.users.add(user)
        # Rely on the unique index instead of checking first, so two
        # simultaneous sign-ups with the same email cannot both succeed.
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if is_duplicate_entry(exc):
                raise EmailAlreadyRegistered() from exc
            raise
        self.session.refresh(user)
        return user

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email.strip().lower())
        if user is None:
            spend_password_check_time(password)
            raise InvalidCredentials()
        if not verify_password(password, user.password_hash) or not user.is_active:
            raise InvalidCredentials()
        return create_access_token(user.id)
