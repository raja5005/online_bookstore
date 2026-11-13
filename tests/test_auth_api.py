"""Registration, login, token handling and role restrictions, through the real API."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.exceptions import EmailAlreadyRegistered
from app.models import Cart, User, UserRole
from app.services.auth_service import AuthService
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    CUSTOMER_EMAIL,
    CUSTOMER_PASSWORD,
    add_user,
    login,
)

NEW_USER = {"email": "new@example.com", "password": "password-123", "full_name": "New User"}


def set_active(email: str, active: bool) -> None:
    with DatabaseManager().engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET is_active = :a WHERE email = :e"), {"a": active, "e": email}
        )


def find_user(email: str) -> User | None:
    with DatabaseManager().new_session() as session:
        return session.scalar(select(User).where(User.email == email))


def token(claims: dict, key: str | None = None, algorithm: str = "HS256") -> dict[str, str]:
    signed = jwt.encode(claims, key or Settings().secret_key, algorithm=algorithm)
    return {"Authorization": f"Bearer {signed}"}


def valid_claims(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    return {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5), **overrides}


# --- Registration ---------------------------------------------------------


def test_register_creates_customer(client):
    response = client.post("/api/auth/register", json=NEW_USER)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == NEW_USER["email"]
    assert body["full_name"] == NEW_USER["full_name"]
    assert body["role"] == "CUSTOMER"
    assert body["is_active"] is True
    assert body["created_at"]


def test_register_never_returns_the_password(client):
    body = client.post("/api/auth/register", json=NEW_USER).json()
    assert not {"password", "password_hash"} & body.keys()


def test_register_stores_only_a_bcrypt_hash(client):
    client.post("/api/auth/register", json=NEW_USER)
    stored = find_user(NEW_USER["email"]).password_hash
    assert stored.startswith("$2b$")
    assert NEW_USER["password"] not in stored


def test_register_creates_the_customers_cart(client):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    with DatabaseManager().new_session() as session:
        assert session.scalar(select(Cart).where(Cart.user_id == user_id)) is not None


def test_register_cannot_choose_admin_role(client):
    payload = {**NEW_USER, "role": "ADMIN", "is_admin": True}
    assert client.post("/api/auth/register", json=payload).json()["role"] == "CUSTOMER"


def test_register_duplicate_email_conflicts(client):
    assert client.post("/api/auth/register", json=NEW_USER).status_code == 201
    response = client.post("/api/auth/register", json=NEW_USER)
    assert response.status_code == 409


def test_register_duplicate_email_ignores_case(client):
    client.post("/api/auth/register", json=NEW_USER)
    upper = {**NEW_USER, "email": NEW_USER["email"].upper()}
    assert client.post("/api/auth/register", json=upper).status_code == 409


def test_failed_duplicate_leaves_no_extra_rows(client):
    client.post("/api/auth/register", json=NEW_USER)
    client.post("/api/auth/register", json=NEW_USER)
    with DatabaseManager().engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM carts")).scalar() == 1


def test_simultaneous_duplicate_registrations_create_one_user():
    def attempt(_):
        with DatabaseManager().new_session() as session:
            try:
                AuthService(session).register(UserRole.CUSTOMER, "race@example.com", "password-123", "R")
                return "created"
            except EmailAlreadyRegistered:
                return "duplicate"

    with ThreadPoolExecutor(5) as pool:
        results = list(pool.map(attempt, range(5)))

    assert results.count("created") == 1
    assert results.count("duplicate") == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "not-an-email"},
        {"email": ""},
        {"full_name": ""},
        {"full_name": "   "},
        {"full_name": "x" * 121},
        {"password": ""},
        {"password": "short"},
        {"password": "x" * 129},
        {"password": "é" * 40},
    ],
)
def test_register_rejects_invalid_input(client, changes):
    response = client.post("/api/auth/register", json={**NEW_USER, **changes})
    assert response.status_code == 422
    assert find_user(NEW_USER["email"]) is None


# --- Login ----------------------------------------------------------------


def test_login_returns_a_working_token(client):
    client.post("/api/auth/register", json=NEW_USER)
    response = client.post(
        "/api/auth/login",
        data={"username": NEW_USER["email"], "password": NEW_USER["password"]},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/users/me", headers=headers).json()["email"] == NEW_USER["email"]


def test_login_email_ignores_case(client):
    client.post("/api/auth/register", json=NEW_USER)
    login(client, NEW_USER["email"].upper(), NEW_USER["password"])


def test_wrong_password_and_unknown_email_look_identical(client):
    client.post("/api/auth/register", json=NEW_USER)
    wrong = client.post(
        "/api/auth/login", data={"username": NEW_USER["email"], "password": "wrong-password"}
    )
    unknown = client.post(
        "/api/auth/login", data={"username": "nobody@example.com", "password": "wrong-password"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_deactivated_user_cannot_log_in(client):
    client.post("/api/auth/register", json=NEW_USER)
    set_active(NEW_USER["email"], False)
    response = client.post(
        "/api/auth/login",
        data={"username": NEW_USER["email"], "password": NEW_USER["password"]},
    )
    assert response.status_code == 401


def test_login_with_very_long_password_is_refused_cleanly(client):
    client.post("/api/auth/register", json=NEW_USER)
    response = client.post(
        "/api/auth/login", data={"username": NEW_USER["email"], "password": "x" * 500}
    )
    assert response.status_code == 401


# --- Tokens ---------------------------------------------------------------


def test_profile_requires_a_token(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_profile_returns_the_logged_in_user(client, customer_headers):
    body = client.get("/api/users/me", headers=customer_headers).json()
    assert body["email"] == CUSTOMER_EMAIL
    assert body["role"] == "CUSTOMER"


def test_garbage_token_is_rejected(client):
    assert client.get("/api/users/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_tampered_token_is_rejected(client, customer_headers):
    value = customer_headers["Authorization"]
    swap = "A" if value[-2] != "A" else "B"
    tampered = {"Authorization": value[:-2] + swap + value[-1]}
    assert client.get("/api/users/me", headers=tampered).status_code == 401


def test_token_signed_with_another_key_is_rejected(client):
    user = add_user(UserRole.CUSTOMER, CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    headers = token(valid_claims(sub=str(user.id)), key="another-key-that-is-also-long-enough-123")
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_unsigned_token_is_rejected(client):
    user = add_user(UserRole.ADMIN, ADMIN_EMAIL, ADMIN_PASSWORD)
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=5)}
    unsigned = jwt.encode(claims, key="", algorithm="none")
    headers = {"Authorization": f"Bearer {unsigned}"}
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_expired_token_is_rejected(client):
    user = add_user(UserRole.CUSTOMER, CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    headers = token({"sub": str(user.id), "iat": past, "exp": past + timedelta(minutes=5)})
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_token_without_expiry_is_rejected(client):
    user = add_user(UserRole.CUSTOMER, CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    headers = token({"sub": str(user.id), "iat": datetime.now(timezone.utc)})
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_token_with_non_numeric_subject_is_rejected(client):
    assert client.get("/api/users/me", headers=token(valid_claims(sub="abc"))).status_code == 401


def test_token_for_deleted_user_is_rejected(client, customer_headers):
    with DatabaseManager().engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))
    assert client.get("/api/users/me", headers=customer_headers).status_code == 401


def test_deactivation_takes_effect_on_existing_tokens(client, customer_headers):
    assert client.get("/api/users/me", headers=customer_headers).status_code == 200
    set_active(CUSTOMER_EMAIL, False)
    assert client.get("/api/users/me", headers=customer_headers).status_code == 401


# --- Role restrictions ----------------------------------------------------

NEW_ADMIN = {"email": "second@example.com", "password": "admin-password-2", "full_name": "Second"}


def test_create_admin_requires_a_token(client):
    assert client.post("/api/admin/admins", json=NEW_ADMIN).status_code == 401


def test_customer_cannot_create_admin(client, customer_headers):
    response = client.post("/api/admin/admins", json=NEW_ADMIN, headers=customer_headers)
    assert response.status_code == 403
    assert find_user(NEW_ADMIN["email"]) is None


def test_admin_can_create_admin_who_can_log_in(client, admin_headers):
    response = client.post("/api/admin/admins", json=NEW_ADMIN, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["role"] == "ADMIN"
    headers = login(client, NEW_ADMIN["email"], NEW_ADMIN["password"])
    assert client.get("/api/users/me", headers=headers).json()["role"] == "ADMIN"


def test_new_admin_gets_no_cart(client, admin_headers):
    user_id = client.post("/api/admin/admins", json=NEW_ADMIN, headers=admin_headers).json()["id"]
    with DatabaseManager().new_session() as session:
        assert session.scalar(select(Cart).where(Cart.user_id == user_id)) is None


def test_new_admin_needs_a_stronger_password_than_a_customer(client, admin_headers):
    weak = {**NEW_ADMIN, "password": "elevenchars"}
    assert client.post("/api/admin/admins", json=weak, headers=admin_headers).status_code == 422


def test_demoted_admin_loses_access_immediately(client, admin_headers):
    with DatabaseManager().engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET role = 'CUSTOMER' WHERE email = :e"), {"e": ADMIN_EMAIL}
        )
    response = client.post("/api/admin/admins", json=NEW_ADMIN, headers=admin_headers)
    assert response.status_code == 403


# --- System ---------------------------------------------------------------


def test_health_reports_database_connected(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
