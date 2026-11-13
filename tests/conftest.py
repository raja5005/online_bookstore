"""Test setup.

Tests run against a separate MySQL database, online_bookstore_test, which is
created fresh and dropped afterwards. They never touch online_bookstore.
"""
import os
from pathlib import Path

# These must be set before anything imports the Settings singleton.
TEST_DB_NAME = "online_bookstore_test"
os.environ["DB_NAME"] = TEST_DB_NAME
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-long-enough-for-hs256-signing")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, text

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.main import app
from app.models import User, UserRole
from app.services.auth_service import AuthService

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
SEED_FILE = Path(__file__).resolve().parents[1] / "db" / "seed.sql"

CUSTOMER_EMAIL = "customer@example.com"
CUSTOMER_PASSWORD = "customer-pass-1"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-password-1"


def _server_engine():
    settings = Settings()
    url = URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )
    return create_engine(url, isolation_level="AUTOCOMMIT")


@pytest.fixture(scope="session", autouse=True)
def test_database():
    assert Settings().db_name == TEST_DB_NAME, "Refusing to run tests on a non-test database"

    lines = SCHEMA_FILE.read_text().replace("online_bookstore", TEST_DB_NAME).splitlines()
    sql = "\n".join(line for line in lines if not line.lstrip().startswith("--"))

    engine = _server_engine()
    with engine.connect() as connection:
        connection.exec_driver_sql(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`")
        for statement in sql.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
    yield
    DatabaseManager().engine.dispose()
    with engine.connect() as connection:
        connection.exec_driver_sql(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`")
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    tables = [
        "notifications",
        "payments",
        "order_status_history",
        "order_items",
        "orders",
        "cart_items",
        "book_authors",
        "books",
        "authors",
        "categories",
        "carts",
        "users",
    ]
    with DatabaseManager().engine.begin() as connection:
        for table in tables:
            connection.execute(text(f"DELETE FROM {table}"))


@pytest.fixture
def catalog():
    """Load the sample books from db/seed.sql (14 books in 5 categories)."""
    lines = SEED_FILE.read_text().replace("online_bookstore", TEST_DB_NAME).splitlines()
    sql = "\n".join(line for line in lines if not line.lstrip().startswith("--"))
    with DatabaseManager().engine.begin() as connection:
        for statement in sql.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def add_user(role: UserRole, email: str, password: str, full_name: str = "Test User") -> User:
    with DatabaseManager().new_session() as session:
        return AuthService(session).register(role, email, password, full_name)


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def customer_headers(client: TestClient) -> dict[str, str]:
    add_user(UserRole.CUSTOMER, CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    return login(client, CUSTOMER_EMAIL, CUSTOMER_PASSWORD)


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    add_user(UserRole.ADMIN, ADMIN_EMAIL, ADMIN_PASSWORD)
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
