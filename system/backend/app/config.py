"""应用配置管理模块。

通过 pydantic-settings 从 .env 文件加载环境变量，集中管理
MySQL / MongoDB / Redis / JWT 等所有配置项，并暴露组装后的
连接 URL 供各模块直接使用。
"""

import secrets
import warnings
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

# Secrets that must never sign tokens in a deployed environment.
PLACEHOLDER_JWT_SECRETS = frozenset(
    {
        "",
        "change-me-to-a-random-secret-key-in-production",
        "your-secret-key",
        "changeme",
        "secret",
    }
)


class Settings(BaseSettings):
    """全局配置，字段值优先从 ``.env`` 文件读取，未配置时使用默认值。"""
    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "cogguard"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "cogguard"
    MYSQL_DATABASE_TEST: str = "cogguard_test"

    # MongoDB
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_USER: str = "cogguard"
    MONGO_PASSWORD: str = ""
    MONGO_DATABASE: str = "cogguard"
    MONGO_DATABASE_TEST: str = "cogguard_test"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Backend
    BACKEND_ENV: str = "local"
    BACKEND_DEBUG: bool = False
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Seed administrator created on first startup when no `admin` row exists.
    # Existing accounts are never rewritten, so rotating this password in the
    # database survives restarts.
    DEFAULT_ADMIN_PASSWORD: str = ""

    # Server-side media fetching may only reach public addresses. Disable the
    # guard only for local fixtures that legitimately serve from 127.0.0.1.
    MEDIA_DOWNLOAD_ALLOW_PRIVATE_HOSTS: bool = False

    # ----- Built-in crawler runtimes -----
    # 登录方式：qrcode | cookie | phone
    MEDIACRAWLER_LOGIN_TYPE: str = "cookie"
    # cookie 登录时从环境读取 Cookie 字符串（微博等）
    MEDIACRAWLER_COOKIES: str = ""
    # Node.js 安装目录（例如 D:/node）；会在 MediaCrawler 子进程里注入 PATH
    MEDIACRAWLER_NODE_DIR: str = ""
    # 宿主机本地 HTTP/SOCKS 代理；Clash Verge TUN/fake-ip 模式下建议填 http://127.0.0.1:7897
    MEDIACRAWLER_PROXY: str = ""
    # 是否抓取二级评论（MediaCrawler 当前支持的评论树上限）
    MEDIACRAWLER_GET_SUB_COMMENTS: bool = False
    # 单条帖子最多抓取多少条评论（含一级评论与可选二级评论）
    MEDIACRAWLER_MAX_COMMENTS_PER_POST: int = 200
    # Downloaded social media files are stored under project output by default.
    MEDIA_DOWNLOAD_ROOT: str = str(PROJECT_ROOT / "output" / "media_downloads")

    # ----- Internal trained BotRHG runtime -----
    BOTRHG_CHECKPOINT_PATH: str = str(PROJECT_ROOT / "output" / "botrhg_weibo" / "checkpoint.pt")
    BOTRHG_DATA_FINGERPRINT: str = "50327a90e7b9fa6cb65140af3e1573d139925033b184af2ed43aa938ab42c0ae"
    BOTRHG_DEVICE: str = "cpu"
    ACCOUNT_ACQUISITION_TEXT_MODEL_PATH: str = ""
    ACCOUNT_ACQUISITION_MAX_LENGTH: int = 128
    ACCOUNT_ACQUISITION_BATCH_SIZE: int = 4
    ACCOUNT_ACQUISITION_DEVICE: str = "cpu"
    # ----- Governed account-model training -----
    # These are operational policy values, rather than request parameters, so
    # a recorded run can be reproduced and an operator cannot bypass gates.
    ACCOUNT_TRAINING_DAPT_TOKEN_THRESHOLD: int = 500_000
    ACCOUNT_TRAINING_SUPERVISED_LABEL_THRESHOLD: int = 200
    ACCOUNT_TRAINING_COOLDOWN_DAYS: int = 7
    ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS: int = 300
    ACCOUNT_TRAINING_MAX_RESUMES: int = 3
    # A committed training dispatch is published by FastAPI's durable outbox
    # poller. This interval also spaces retries after broker failures.
    ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS: float = 5.0
    ACCOUNT_TRAINING_OUTBOX_CLAIM_LEASE_SECONDS: float = 30.0
    ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS: float = 5.0
    # Shared only with the internal evaluator. It signs evidence submitted to
    # the governance API and must remain independent from authentication keys.
    ACCOUNT_MODEL_EVALUATION_HMAC_SECRET: str = ""
    # Legacy checkpoint bootstrapping is opt-in and local-only. Governed
    # production runtimes require an already persisted activation pointer.
    ACCOUNT_MODEL_BOOTSTRAP_MODE: str = "disabled"

    # ----- Coordination Discover research artifact runtime -----
    COORDINATION_DISCOVER_MODE: str = "artifact_first"
    COORDINATION_DISCOVER_ARTIFACT_ROOT: str = str(PROJECT_ROOT / "artifacts" / "coordination_discover")
    COORDINATION_DISCOVER_DEVICE: str = "cuda"
    COORDINATION_DISCOVER_FALLBACK: str = "evidence_runtime_v2"
    COORDINATION_DISCOVER_DETECT_ROLE: str = "validation_only"
    COORDINATION_DISCOVER_MODALITY_POLICY: str = "platform_generic_only"
    COORDINATION_DISCOVER_REQUIRE_LEIDEN: bool = True
    MODEL_ARTIFACT_ROOT: str = str(PROJECT_ROOT / "artifacts")

    # Operational policies preserve the fast local prototype while making
    # production queue and activation behavior explicit and auditable.
    ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE: str = "auto"
    ANALYSIS_TEACHER_DISPATCH_MODE: str = "auto"

    # Immutable analysis projections are cached by source/run identity. Redis
    # shares warm results across backend processes; the local LRU remains the
    # fast path and the cache never becomes a source of truth.
    ANALYSIS_RESULT_CACHE_ENABLED: bool = True
    ANALYSIS_RESULT_CACHE_REDIS_ENABLED: bool = True
    ANALYSIS_RESULT_CACHE_MAX_ENTRIES: int = 16
    ANALYSIS_RESULT_CACHE_TTL_SECONDS: int = 604800
    ANALYSIS_RESULT_CACHE_NAMESPACE: str = "cogguard:analysis-result"

    # ----- LLM API (趋势预测用) -----
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_WIRE: str = "chat_completions"
    LLM_TIMEOUT_SECONDS: float = 180.0
    LLM_INCLUDE_MEDIA_BASE64: bool = False
    LLM_REQUIRE_VISION: bool = False

    # ----- LLM response cache (demo stability) -----
    # Recorded successful LLM responses can be replayed so a walkthrough does
    # not depend on live network access. Only genuine responses are ever
    # written: the cache is populated by real calls in RECORD mode, never by
    # hand-authored text. Modes: "off" | "replay" | "record".
    LLM_CACHE_MODE: str = "off"
    LLM_CACHE_ROOT: str = str(PROJECT_ROOT / "output" / "llm_cache")
    REVIEW_EXTERNAL_RETRIEVAL_ENABLED: bool = False
    REVIEW_RETRIEVAL_API_KEY: str = ""
    REVIEW_RETRIEVAL_BASE_URL: str = ""
    REVIEW_RETRIEVAL_SEARCH_PATH: str = "/search"
    REVIEW_RETRIEVAL_PROVIDER_NAME: str = ""
    REVIEW_RETRIEVAL_ADAPTER: str = ""
    # Master key used to encrypt API keys stored in Review provider configs.
    # Keep it independent from JWT_SECRET_KEY so provider credentials can be
    # rotated and audited separately from authentication tokens.
    REVIEW_CONFIG_ENCRYPTION_KEY: str = ""

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    @property
    def mysql_url_test(self) -> str:
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE_TEST}"
        )

    @property
    def mongo_url(self) -> str:
        return (
            f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}"
            f"@{self.MONGO_HOST}:{self.MONGO_PORT}"
        )

    @property
    def redis_url(self) -> str:
        return (
            f"redis://:{self.REDIS_PASSWORD}"
            f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        )

    @property
    def model_activation_requires_dual_approval(self) -> bool:
        mode = self.ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE.strip().lower()
        if mode == "single_operator":
            return False
        if mode == "dual_operator":
            return True
        return self.BACKEND_ENV.strip().lower() == "production"

    @property
    def teacher_inline_fallback_allowed(self) -> bool:
        mode = self.ANALYSIS_TEACHER_DISPATCH_MODE.strip().lower()
        if mode == "queue_required":
            return False
        if mode == "local_inline_fallback":
            return True
        return self.BACKEND_ENV.strip().lower() != "production"

    @property
    def account_model_local_bootstrap_allowed(self) -> bool:
        return (
            self.BACKEND_ENV.strip().lower() != "production"
            and self.ACCOUNT_MODEL_BOOTSTRAP_MODE.strip().lower() == "local_legacy"
        )

    @model_validator(mode="after")
    def _reject_placeholder_secrets(self) -> "Settings":
        """Fail fast in production when auth secrets are still placeholders.

        In debug mode the placeholder only warns, so local development and the
        test suite keep working without a populated ``.env``.
        """
        environment = self.BACKEND_ENV.strip().lower()
        approval_mode = self.ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE.strip().lower()
        dispatch_mode = self.ANALYSIS_TEACHER_DISPATCH_MODE.strip().lower()
        account_bootstrap_mode = self.ACCOUNT_MODEL_BOOTSTRAP_MODE.strip().lower()
        if approval_mode not in {"auto", "single_operator", "dual_operator"}:
            raise ValueError(
                "ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE must be auto, single_operator, or dual_operator."
            )
        if dispatch_mode not in {"auto", "queue_required", "local_inline_fallback"}:
            raise ValueError(
                "ANALYSIS_TEACHER_DISPATCH_MODE must be auto, queue_required, or local_inline_fallback."
            )
        if account_bootstrap_mode not in {"disabled", "local_legacy"}:
            raise ValueError("ACCOUNT_MODEL_BOOTSTRAP_MODE must be disabled or local_legacy.")
        if environment == "production" and approval_mode == "single_operator":
            raise ValueError("Production model activation requires dual_operator approval mode.")
        if environment == "production" and dispatch_mode == "local_inline_fallback":
            raise ValueError("Production Teacher review requires a durable queue.")
        if environment == "production" and account_bootstrap_mode != "disabled":
            raise ValueError("ACCOUNT_MODEL_BOOTSTRAP_MODE must be disabled in production.")
        if environment == "production" and len(self.ACCOUNT_MODEL_EVALUATION_HMAC_SECRET.strip()) < 32:
            raise ValueError(
                "ACCOUNT_MODEL_EVALUATION_HMAC_SECRET must be explicitly configured with at least 32 characters "
                "in production."
            )
        if not self.JWT_SECRET_KEY.strip():
            if environment == "production":
                raise ValueError("JWT_SECRET_KEY must be explicitly configured in production.")
            self.JWT_SECRET_KEY = secrets.token_urlsafe(48)
            warnings.warn(
                "JWT_SECRET_KEY is unset; using an ephemeral local-development secret. "
                "Configure JWT_SECRET_KEY for persistent sessions.",
                stacklevel=2,
            )
        elif self.JWT_SECRET_KEY.strip().lower() in PLACEHOLDER_JWT_SECRETS:
            message = (
                "JWT_SECRET_KEY is unset or still a well-known placeholder. "
                "Anyone can forge admin tokens with it. Set JWT_SECRET_KEY to a "
                "random secret in system/.env."
            )
            if environment == "production":
                raise ValueError(message)
            warnings.warn(f"{message} (allowed only for local development)", stacklevel=2)
        if environment == "production" and not self.DEFAULT_ADMIN_PASSWORD.strip():
            raise ValueError("DEFAULT_ADMIN_PASSWORD must be explicitly configured in production.")
        for field_name in (
            "ACCOUNT_TRAINING_DAPT_TOKEN_THRESHOLD",
            "ACCOUNT_TRAINING_SUPERVISED_LABEL_THRESHOLD",
            "ACCOUNT_TRAINING_COOLDOWN_DAYS",
            "ACCOUNT_TRAINING_HEARTBEAT_TIMEOUT_SECONDS",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive.")
        if self.ACCOUNT_TRAINING_MAX_RESUMES < 0:
            raise ValueError("ACCOUNT_TRAINING_MAX_RESUMES cannot be negative.")
        if self.ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS <= 0:
            raise ValueError("ACCOUNT_TRAINING_OUTBOX_POLL_INTERVAL_SECONDS must be positive.")
        for field_name in (
            "ACCOUNT_TRAINING_OUTBOX_CLAIM_LEASE_SECONDS",
            "ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive.")
        return self

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(BASE_DIR / ".env")),
        extra="ignore",
    )


settings = Settings()


def resolve_project_path(value: str | Path) -> Path:
    """Resolve relative operational paths from the repository system root."""

    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


__all__ = ["BASE_DIR", "PROJECT_ROOT", "Settings", "resolve_project_path", "settings"]
