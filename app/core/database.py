"""Database connection (Singleton pattern)."""
from collections.abc import Iterator

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings
from app.patterns.singleton import SingletonMeta

MYSQL_DUPLICATE_ENTRY = 1062


def is_duplicate_entry(error: IntegrityError) -> bool:
    return error.orig.args[0] == MYSQL_DUPLICATE_ENTRY


class Base(DeclarativeBase):
    """Base class for ORM models. Tables are created by db/schema.sql."""


class DatabaseManager(metaclass=SingletonMeta):
    """Owns the application's single SQLAlchemy engine and connection pool."""

    def __init__(self) -> None:
        settings = Settings()
        url = URL.create(
            "mysql+pymysql",
            username=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            query={"charset": "utf8mb4"},
        )
        # pool_pre_ping replaces connections that MySQL has closed while idle.
        self.engine = create_engine(url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def new_session(self) -> Session:
        return self._session_factory()

    def is_available(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False


def get_db() -> Iterator[Session]:
    """FastAPI dependency that gives each request its own session."""
    with DatabaseManager().new_session() as session:
        yield session
