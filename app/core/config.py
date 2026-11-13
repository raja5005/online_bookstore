"""Application configuration (Singleton pattern)."""
import os
from pathlib import Path

from dotenv import load_dotenv

from app.patterns.singleton import SingletonMeta

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIN_SECRET_KEY_LENGTH = 32


class Settings(metaclass=SingletonMeta):
    """Values read once from the environment and the .env file."""

    def __init__(self) -> None:
        # Real environment variables take priority over the .env file.
        load_dotenv(PROJECT_ROOT / ".env")

        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = int(os.getenv("DB_PORT", "3306"))
        self.db_user = os.getenv("DB_USER", "root")
        self.db_password = os.getenv("DB_PASSWORD", "")
        self.db_name = os.getenv("DB_NAME", "online_bookstore")

        self.secret_key = os.getenv("SECRET_KEY", "")
        if len(self.secret_key) < MIN_SECRET_KEY_LENGTH:
            raise RuntimeError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters. "
                "See .env.example."
            )
        self.jwt_algorithm = "HS256"
        self.access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
