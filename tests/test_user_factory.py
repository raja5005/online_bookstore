"""Factory pattern: the right kind of user, with the right rules and defaults."""
import pytest

from app.core.exceptions import WeakPassword
from app.core.security import verify_password
from app.models import Admin, Cart, Customer, UserRole
from app.patterns.user_factory import UserFactory


def make(role, password="long-enough-password", email="person@example.com"):
    return UserFactory.create_user(role, email, password, "  Pat Example  ")


def test_creates_customer_with_an_empty_cart():
    user = make(UserRole.CUSTOMER)
    assert isinstance(user, Customer)
    assert user.role is UserRole.CUSTOMER
    assert isinstance(user.cart, Cart)


def test_creates_admin_without_a_cart():
    user = make(UserRole.ADMIN)
    assert isinstance(user, Admin)
    assert user.role is UserRole.ADMIN
    assert not hasattr(user, "cart")


def test_password_is_hashed():
    user = make(UserRole.CUSTOMER, password="my-secret-password")
    assert user.password_hash != "my-secret-password"
    assert user.password_hash.startswith("$2b$")
    assert verify_password("my-secret-password", user.password_hash)
    assert not verify_password("another-password", user.password_hash)


def test_email_and_name_are_normalized():
    user = make(UserRole.CUSTOMER, email="  Person@Example.COM ")
    assert user.email == "person@example.com"
    assert user.full_name == "Pat Example"


@pytest.mark.parametrize(
    ("role", "length", "accepted"),
    [
        (UserRole.CUSTOMER, 7, False),
        (UserRole.CUSTOMER, 8, True),
        (UserRole.ADMIN, 11, False),
        (UserRole.ADMIN, 12, True),
    ],
)
def test_minimum_password_length_depends_on_role(role, length, accepted):
    password = "x" * length
    if accepted:
        assert make(role, password=password).password_hash
    else:
        with pytest.raises(WeakPassword):
            make(role, password=password)


@pytest.mark.parametrize("role", list(UserRole))
def test_password_over_bcrypt_limit_is_rejected(role):
    # 40 two-byte characters: 80 bytes, even though it is only 40 characters.
    with pytest.raises(WeakPassword):
        make(role, password="é" * 40)
