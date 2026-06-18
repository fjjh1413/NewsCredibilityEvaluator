import os
import tempfile
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

DEFAULT_EMBEDDING_PROVIDER = "dashscope"
DEFAULT_EMBEDDING_DIMENSION = 1024
DEFAULT_DETECT_RATE_LIMIT_COUNT = 3
DEFAULT_DETECT_RATE_LIMIT_WINDOW_SECONDS = 60
PRODUCTION_ENV_NAMES = {"prod", "production"}
PLACEHOLDER_SECRET_KEYS = {
    "change_me",
    "changeme",
    "replace_with_secret_key",
    "replace_with_a_long_random_secret",
    "your-secret-key",
    "your_secret_key",
}
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32
MIN_PRODUCTION_SECRET_KEY_UNIQUE_CHARS = 8


def _read_positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _read_environment() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or "development"
    ).strip().lower()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.env_file_exists = ENV_FILE.is_file()
        self.environment = _read_environment()
        self.project_name = os.getenv("PROJECT_NAME", "zhiyun-bianzhen-backend")
        self.project_version = os.getenv("PROJECT_VERSION", "0.1.0")
        self.api_prefix = os.getenv("API_PREFIX", "/api")
        self.backend_cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "*")
        self.database_host = os.getenv("DATABASE_HOST", "127.0.0.1")
        self.database_port = int(os.getenv("DATABASE_PORT", "3306"))
        self.database_user = os.getenv("DATABASE_USER", "root")
        self.database_password = os.getenv("DATABASE_PASSWORD", "")
        self.database_name = os.getenv("DATABASE_NAME", "zhiyun_bianzhen")
        self.database_url_override = os.getenv("DATABASE_URL", "").strip()
        self.secret_key = os.getenv("SECRET_KEY", "").strip()
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )
        self.first_superuser_username = os.getenv("FIRST_SUPERUSER_USERNAME", "")
        self.first_superuser_password = os.getenv("FIRST_SUPERUSER_PASSWORD", "")
        self.first_superuser_email = os.getenv("FIRST_SUPERUSER_EMAIL", "")
        self.chroma_persist_dir = (
            os.getenv("CHROMA_PATH")
            or os.getenv("CHROMA_PERSIST_DIR")
            or "./chroma_db"
        )
        self.embedding_provider = (
            os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER).strip().lower()
            or DEFAULT_EMBEDDING_PROVIDER
        )
        self.embedding_dimension = _read_positive_int_env(
            "EMBEDDING_DIMENSION",
            DEFAULT_EMBEDDING_DIMENSION,
        )
        self.deepseek_embedding_model = os.getenv(
            "DEEPSEEK_EMBEDDING_MODEL", "deepseek-embedding-v1"
        ).strip()
        self.dashscope_embedding_model = os.getenv(
            "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4"
        ).strip()
        self.report_dir = os.getenv("REPORT_DIR") or str(
            Path(tempfile.gettempdir()) / "zhiyun-bianzhen" / "reports"
        )
        self.detect_rate_limit_count = _read_positive_int_env(
            "DETECT_RATE_LIMIT_COUNT",
            DEFAULT_DETECT_RATE_LIMIT_COUNT,
        )
        self.detect_rate_limit_window_seconds = _read_positive_int_env(
            "DETECT_RATE_LIMIT_WINDOW_SECONDS",
            DEFAULT_DETECT_RATE_LIMIT_WINDOW_SECONDS,
        )
        # ── Bocha AI ──
        self.bocha_api_key = os.getenv("BOCHA_API_KEY", "").strip()
        self.bocha_api_base_url = (
            os.getenv("BOCHA_API_BASE_URL", "https://api.bochaai.com").strip()
        )
        # ── 实时联网检索 ──
        self.web_search_enabled = os.getenv("WEB_SEARCH_ENABLED", "true").strip().lower() == "true"
        self.web_search_freshness = os.getenv("WEB_SEARCH_FRESHNESS", "oneMonth").strip()
        self.web_search_count = _read_positive_int_env("WEB_SEARCH_COUNT", 5)
        self.web_search_timeout_seconds = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "8").strip() or "8")
        # ── 定时抓取 ──
        self.crawl_enabled = os.getenv("CRAWL_ENABLED", "true").strip().lower() == "true"
        self.crawl_schedule = os.getenv("CRAWL_SCHEDULE", "0 */6 * * *").strip()
        self.crawl_concurrent_fetches = _read_positive_int_env("CRAWL_CONCURRENT_FETCHES", 3)
        self.crawl_fetch_timeout_seconds = float(os.getenv("CRAWL_FETCH_TIMEOUT_SECONDS", "10").strip() or "10")
        self.crawl_fetch_max_bytes = _read_positive_int_env("CRAWL_FETCH_MAX_BYTES", 2 * 1024 * 1024)
        self.crawl_allow_private_hosts = os.getenv("CRAWL_ALLOW_PRIVATE_HOSTS", "false").strip().lower() == "true"
        self.crawl_auto_sync_vector = os.getenv("CRAWL_AUTO_SYNC_VECTOR", "true").strip().lower() == "true"
        # ── 链接识别（检测页 paste-URL → 提取预览）──
        # SSRF default-deny：默认拒绝抓取私有/内网地址；仅本地联调时设为 true.
        self.article_fetch_allow_private_hosts = (
            os.getenv("ARTICLE_FETCH_ALLOW_PRIVATE_HOSTS", "false").strip().lower() == "true"
        )

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
        if self.database_url_override:
            return self.database_url_override

        password = quote_plus(self.database_password)
        return (
            f"mysql+pymysql://{self.database_user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
            "?charset=utf8mb4"
        )

    @property
    def chroma_persist_path(self) -> str:
        path = Path(self.chroma_persist_dir)
        if not path.is_absolute():
            path = BASE_DIR / path
        return str(path)

    @property
    def report_path(self) -> str:
        path = Path(self.report_dir).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        resolved = path.resolve()
        if resolved.is_relative_to(BASE_DIR.resolve()):
            raise RuntimeError("REPORT_DIR must point outside the backend source directory")
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(f"Unable to create REPORT_DIR at {resolved}: {exc}") from exc
        return str(resolved)

    def validate_required_settings(self) -> None:
        secret_key = self.secret_key
        if not secret_key:
            raise RuntimeError(
                "SECRET_KEY is required. Please configure it in backend/.env."
            )

        if secret_key.lower() in PLACEHOLDER_SECRET_KEYS:
            raise RuntimeError(
                "SECRET_KEY must not use a placeholder value. "
                "Please configure a strong secret in backend/.env."
            )

        if self.environment in PRODUCTION_ENV_NAMES and _is_weak_secret_key(secret_key):
            raise RuntimeError(
                "SECRET_KEY is too weak for production. "
                "Please configure a long random secret in backend/.env."
            )


def _is_weak_secret_key(secret_key: str) -> bool:
    return (
        len(secret_key) < MIN_PRODUCTION_SECRET_KEY_LENGTH
        or len(set(secret_key)) < MIN_PRODUCTION_SECRET_KEY_UNIQUE_CHARS
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
