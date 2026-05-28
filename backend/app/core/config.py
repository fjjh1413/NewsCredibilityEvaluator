import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.project_name = os.getenv("PROJECT_NAME", "zhiyun-bianzhen-backend")
        self.project_version = os.getenv("PROJECT_VERSION", "0.1.0")
        self.api_prefix = os.getenv("API_PREFIX", "/api")
        self.backend_cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "*")
        self.database_host = os.getenv("DATABASE_HOST", "127.0.0.1")
        self.database_port = int(os.getenv("DATABASE_PORT", "3306"))
        self.database_user = os.getenv("DATABASE_USER", "root")
        self.database_password = os.getenv("DATABASE_PASSWORD", "")
        self.database_name = os.getenv("DATABASE_NAME", "zhiyun_bianzhen")
        self.secret_key = os.getenv("SECRET_KEY", "")
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )
        self.first_superuser_username = os.getenv("FIRST_SUPERUSER_USERNAME", "")
        self.first_superuser_password = os.getenv("FIRST_SUPERUSER_PASSWORD", "")
        self.first_superuser_email = os.getenv("FIRST_SUPERUSER_EMAIL", "")

    @property
    def cors_origins(self) -> list[str]:
        if self.backend_cors_origins.strip() == "*":
            return ["*"]
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def database_url(self) -> str:
        password = quote_plus(self.database_password)
        return (
            f"mysql+pymysql://{self.database_user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
            "?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
