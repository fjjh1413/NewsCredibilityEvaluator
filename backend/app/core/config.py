import ipaddress
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
SUPPORTED_RAG_INDEX_VERSIONS = {"v1", "v2", "hybrid"}
PRODUCTION_ENV_NAMES = {"prod", "production"}
PLACEHOLDER_SECRET_KEYS = {
    "change_me",
    "changeme",
    "replace_with_secret_key",
    "replace_with_a_long_random_secret",
    "replace_with_at_least_32_random_characters",
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


def _read_positive_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _read_float_range_env(
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "on"}


def _read_choice_env(name: str, default: str, allowed_values: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    return value if value in allowed_values else default


def _read_rag_index_version() -> str:
    value = os.getenv("RAG_INDEX_VERSION", "v1").strip().lower()
    return value if value in SUPPORTED_RAG_INDEX_VERSIONS else "v1"


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
        self.trusted_proxy_ips = os.getenv("TRUSTED_PROXY_IPS", "").strip()
        self.redis_enabled = _read_bool_env("REDIS_ENABLED", False)
        self.redis_required = _read_bool_env("REDIS_REQUIRED", False)
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip()
        self.redis_socket_timeout_seconds = _read_positive_float_env(
            "REDIS_SOCKET_TIMEOUT_SECONDS",
            1.0,
        )
        self.redis_socket_connect_timeout_seconds = _read_positive_float_env(
            "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
            1.0,
        )
        self.otel_tracing_enabled = _read_bool_env("OTEL_TRACING_ENABLED", False)
        self.otel_service_name = os.getenv(
            "OTEL_SERVICE_NAME",
            self.project_name,
        ).strip()
        self.otel_exporter_otlp_traces_endpoint = (
            os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            or "http://127.0.0.1:4318/v1/traces"
        ).strip()
        self.otel_trace_sample_ratio = _read_float_range_env(
            "OTEL_TRACE_SAMPLE_RATIO",
            0.10,
            0.0,
            1.0,
        )
        self.pyroscope_enabled = _read_bool_env("PYROSCOPE_ENABLED", False)
        self.pyroscope_required = _read_bool_env("PYROSCOPE_REQUIRED", False)
        self.pyroscope_server_address = os.getenv(
            "PYROSCOPE_SERVER_ADDRESS",
            "http://127.0.0.1:4040",
        ).strip()
        self.pyroscope_application_name = os.getenv(
            "PYROSCOPE_APPLICATION_NAME",
            self.project_name,
        ).strip() or self.project_name
        self.pyroscope_sample_rate = _read_positive_int_env(
            "PYROSCOPE_SAMPLE_RATE",
            100,
        )
        self.pyroscope_basic_auth_username = os.getenv(
            "PYROSCOPE_BASIC_AUTH_USERNAME",
            "",
        ).strip()
        self.pyroscope_basic_auth_password = os.getenv(
            "PYROSCOPE_BASIC_AUTH_PASSWORD",
            "",
        ).strip()
        self.pyroscope_tenant_id = os.getenv("PYROSCOPE_TENANT_ID", "").strip()
        self.cache_key_prefix = os.getenv("CACHE_KEY_PREFIX", "newscred").strip()
        self.cache_default_ttl_seconds = _read_positive_int_env(
            "CACHE_DEFAULT_TTL_SECONDS",
            300,
        )
        self.cache_ttl_jitter_seconds = _read_positive_int_env(
            "CACHE_TTL_JITTER_SECONDS",
            30,
        )
        self.admin_statistics_cache_ttl_seconds = _read_positive_int_env(
            "ADMIN_STATISTICS_CACHE_TTL_SECONDS",
            60,
        )
        # ── Bocha AI ──
        self.async_detection_enabled = _read_bool_env(
            "ASYNC_DETECTION_ENABLED",
            False,
        )
        self.async_task_always_eager = _read_bool_env(
            "ASYNC_TASK_ALWAYS_EAGER",
            False,
        )
        self.celery_broker_url = (
            os.getenv("CELERY_BROKER_URL") or self.redis_url
        ).strip()
        self.celery_result_backend = (
            os.getenv("CELERY_RESULT_BACKEND") or self.redis_url
        ).strip()
        self.celery_worker_concurrency = _read_positive_int_env(
            "CELERY_WORKER_CONCURRENCY",
            2,
        )
        self.ai_cache_enabled = _read_bool_env("AI_CACHE_ENABLED", True)
        self.ai_cache_ttl_seconds = _read_positive_int_env(
            "AI_CACHE_TTL_SECONDS",
            3600,
        )
        self.web_search_cache_enabled = _read_bool_env(
            "WEB_SEARCH_CACHE_ENABLED",
            True,
        )
        self.web_search_cache_ttl_seconds = _read_positive_int_env(
            "WEB_SEARCH_CACHE_TTL_SECONDS",
            900,
        )
        self.embedding_cache_enabled = _read_bool_env(
            "EMBEDDING_CACHE_ENABLED",
            True,
        )
        self.embedding_cache_ttl_seconds = _read_positive_int_env(
            "EMBEDDING_CACHE_TTL_SECONDS",
            86400,
        )
        self.rag_index_version = _read_rag_index_version()
        self.rag_retrieval_debug = _read_bool_env("RAG_RETRIEVAL_DEBUG", False)
        self.rag_chunk_size = _read_positive_int_env("RAG_CHUNK_SIZE", 700)
        self.rag_chunk_overlap = _read_positive_int_env("RAG_CHUNK_OVERLAP", 100)
        self.rag_dense_top_n = _read_positive_int_env("RAG_DENSE_TOP_N", 50)
        self.rag_parent_top_k = _read_positive_int_env("RAG_PARENT_TOP_K", 15)
        self.rag_chunks_per_parent = _read_positive_int_env(
            "RAG_CHUNKS_PER_PARENT",
            2,
        )
        self.rag_lexical_enabled = _read_bool_env("RAG_LEXICAL_ENABLED", True)
        self.rag_mmr_enabled = _read_bool_env("RAG_MMR_ENABLED", True)
        self.rag_fusion_strategy = _read_choice_env(
            "RAG_FUSION_STRATEGY",
            "rrf",
            {"rrf", "weighted_sum"},
        )
        self.rag_rrf_rank_constant = _read_positive_int_env(
            "RAG_RRF_RANK_CONSTANT",
            60,
        )
        self.rag_claim_aware_enabled = _read_bool_env(
            "RAG_CLAIM_AWARE_ENABLED",
            True,
        )
        self.rag_claim_query_count = _read_positive_int_env(
            "RAG_CLAIM_QUERY_COUNT",
            4,
        )
        self.rag_supporting_spans_enabled = _read_bool_env(
            "RAG_SUPPORTING_SPANS_ENABLED",
            True,
        )
        self.rag_supporting_span_count = _read_positive_int_env(
            "RAG_SUPPORTING_SPAN_COUNT",
            2,
        )
        self.rag_rule_rerank_enabled = _read_bool_env(
            "RAG_RULE_RERANK_ENABLED",
            True,
        )
        self.rag_rerank_pool_size = _read_positive_int_env(
            "RAG_RERANK_POOL_SIZE",
            30,
        )
        self.rag_model_rerank_enabled = _read_bool_env(
            "RAG_MODEL_RERANK_ENABLED",
            False,
        )
        self.rag_audit_sample_limit = _read_positive_int_env(
            "RAG_AUDIT_SAMPLE_LIMIT",
            200,
        )
        self.knowledge_index_job_enabled = _read_bool_env(
            "KNOWLEDGE_INDEX_JOB_ENABLED",
            True,
        )
        self.knowledge_index_job_interval_seconds = _read_positive_int_env(
            "KNOWLEDGE_INDEX_JOB_INTERVAL_SECONDS",
            60,
        )
        self.knowledge_index_job_batch_size = _read_positive_int_env(
            "KNOWLEDGE_INDEX_JOB_BATCH_SIZE",
            20,
        )
        self.knowledge_index_job_max_attempts = _read_positive_int_env(
            "KNOWLEDGE_INDEX_JOB_MAX_ATTEMPTS",
            3,
        )
        self.knowledge_index_job_retry_delay_seconds = _read_positive_int_env(
            "KNOWLEDGE_INDEX_JOB_RETRY_DELAY_SECONDS",
            60,
        )
        self.report_generation_cache_enabled = _read_bool_env(
            "REPORT_GENERATION_CACHE_ENABLED",
            True,
        )
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
    def is_production(self) -> bool:
        return self.environment in PRODUCTION_ENV_NAMES

    @property
    def trusted_proxy_networks(
        self,
    ) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if not self.trusted_proxy_ips:
            return networks

        for raw_item in self.trusted_proxy_ips.split(","):
            item = raw_item.strip()
            if not item:
                continue
            try:
                networks.append(ipaddress.ip_network(item, strict=False))
            except ValueError as exc:
                raise RuntimeError(f"Invalid TRUSTED_PROXY_IPS entry: {item}") from exc
        return networks

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

        if self.is_production and _is_weak_secret_key(secret_key):
            raise RuntimeError(
                "SECRET_KEY is too weak for production. "
                "Please configure a long random secret in backend/.env."
            )

        if self.is_production and "*" in self.cors_origins:
            raise RuntimeError(
                "BACKEND_CORS_ORIGINS must list explicit origins in production."
            )

        if self.redis_enabled and not self.redis_url:
            raise RuntimeError("REDIS_URL is required when REDIS_ENABLED=true.")

        _ = self.trusted_proxy_networks


def _is_weak_secret_key(secret_key: str) -> bool:
    return (
        len(secret_key) < MIN_PRODUCTION_SECRET_KEY_LENGTH
        or len(set(secret_key)) < MIN_PRODUCTION_SECRET_KEY_UNIQUE_CHARS
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
