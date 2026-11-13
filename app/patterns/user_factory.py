"""Factory pattern: user creation.

Code that needs a new user calls UserFactory.create_user() with a role. It does
not need to know which class is built or what rules apply to that kind of user.

UserCreator holds the steps shared by every user. Each subclass supplies what
differs for its user type:

    Type      Class     Minimum password   Starts with
    Customer  Customer  8 characters       an empty cart
    Admin     Admin     12 characters      no cart

To add a new user type, write one new creator and add it to UserFactory._creators.
"""
from abc import ABC, abstractmethod

from app.core.exceptions import WeakPassword
from app.core.security import MAX_PASSWORD_BYTES, hash_password
from app.models import Admin, Cart, Customer, User, UserRole


class UserCreator(ABC):
    min_password_length: int

    def create(self, email: str, password: str, full_name: str) -> User:
        self._check_password(password)
        user = self._new_user()
        user.email = email.strip().lower()
        user.full_name = full_name.strip()
        user.password_hash = hash_password(password)
        return user

    def _check_password(self, password: str) -> None:
        if len(password) < self.min_password_length:
            raise WeakPassword(
                f"The password must be at least {self.min_password_length} characters."
            )
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise WeakPassword(f"The password must be at most {MAX_PASSWORD_BYTES} bytes.")

    @abstractmethod
    def _new_user(self) -> User:
        """Build the concrete user type with its role-specific defaults."""


class CustomerCreator(UserCreator):
    min_password_length = 8

    def _new_user(self) -> User:
        return Customer(cart=Cart())


class AdminCreator(UserCreator):
    min_password_length = 12

    def _new_user(self) -> User:
        return Admin()


class UserFactory:
    _creators: dict[UserRole, UserCreator] = {
        UserRole.CUSTOMER: CustomerCreator(),
        UserRole.ADMIN: AdminCreator(),
    }

    @classmethod
    def create_user(cls, role: UserRole, email: str, password: str, full_name: str) -> User:
        return cls._creators[role].create(email, password, full_name)
