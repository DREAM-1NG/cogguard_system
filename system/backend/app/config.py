"""应用配置管理模块。

通过 pydantic-settings 从 .env 文件加载环境变量，集中管理
MySQL / MongoDB / Redis / JWT 等所有配置项，并暴露组装后的
连接 URL 供各模块直接使用。
"""

import warnings
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

# Secrets that must never sign tokens outside local development. They ship as
# defaults so a fresh clone still boots, but production startup refuses them
# instead of silently signing admin tokens with a publicly known key.
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
    MYSQL_PASSWORD: str = "cogguard123"
    MYSQL_DATABASE: str = "cogguard"
    MYSQL_DATABASE_TEST: str = "cogguard_test"

    # MongoDB
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_USER: str = "cogguard"
    MONGO_PASSWORD: str = "cogguard123"
    MONGO_DATABASE: str = "cogguard"
    MONGO_DATABASE_TEST: str = "cogguard_test"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "cogguard123"
    REDIS_DB: int = 0

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Backend
    BACKEND_DEBUG: bool = True
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Seed administrator created on first startup when no `admin` row exists.
    # Existing accounts are never rewritten, so rotating this password in the
    # database survives restarts.
    DEFAULT_ADMIN_PASSWORD: str = "123123"

    # The static preview token bypasses authentication for frontend-only
    # walkthroughs. It is honoured only while BACKEND_DEBUG is true; setting
    # BACKEND_DEBUG=false (production) disables the bypass regardless.
    PREVIEW_AUTH_ENABLED: bool = True

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

    # ----- Coordination Discover research artifact runtime -----
    COORDINATION_DISCOVER_MODE: str = "artifact_first"
    COORDINATION_DISCOVER_ARTIFACT_ROOT: str = str(PROJECT_ROOT / "artifacts" / "coordination_discover")
    COORDINATION_DISCOVER_DEVICE: str = "cuda"
    COORDINATION_DISCOVER_FALLBACK: str = "evidence_runtime_v2"
    COORDINATION_DISCOVER_DETECT_ROLE: str = "validation_only"
    COORDINATION_DISCOVER_MODALITY_POLICY: str = "platform_generic_only"
    COORDINATION_DISCOVER_REQUIRE_LEIDEN: bool = True

    # ----- LLM API (趋势预测用) -----
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_WIRE: str = "chat_completions"
    LLM_TIMEOUT_SECONDS: float = 180.0
    LLM_INCLUDE_MEDIA_BASE64: bool = False
    LLM_REQUIRE_VISION: bool = False
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
    def preview_auth_allowed(self) -> bool:
        """Preview bypass is only ever active in debug (non-production) mode."""
        return bool(self.PREVIEW_AUTH_ENABLED and self.BACKEND_DEBUG)

    @model_validator(mode="after")
    def _reject_placeholder_secrets(self) -> "Settings":
        """Fail fast in production when auth secrets are still placeholders.

        In debug mode the placeholder only warns, so local development and the
        test suite keep working without a populated ``.env``.
        """
        if self.JWT_SECRET_KEY.strip().lower() in PLACEHOLDER_JWT_SECRETS:
            message = (
                "JWT_SECRET_KEY is unset or still a well-known placeholder. "
                "Anyone can forge admin tokens with it. Set JWT_SECRET_KEY to a "
                "random secret in system/.env."
            )
            if not self.BACKEND_DEBUG:
                raise ValueError(message)
            warnings.warn(f"{message} (allowed because BACKEND_DEBUG=true)", stacklevel=2)
        return self

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(BASE_DIR / ".env")),
        extra="ignore",
    )


settings = Settings()
