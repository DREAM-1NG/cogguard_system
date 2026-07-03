"""应用配置管理模块。

通过 pydantic-settings 从 .env 文件加载环境变量，集中管理
MySQL / MongoDB / Redis / JWT 等所有配置项，并暴露组装后的
连接 URL 供各模块直接使用。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


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

    # ----- Real crawlers (optional; see doc/engineering/environment-setup.md) -----
    # MediaCrawler 仓库根目录绝对路径；未配置时无法执行 weibo/douyin 等社交采集
    MEDIACRAWLER_ROOT: str = ""
    # 调用 MediaCrawler CLI 时的登录方式：qrcode | cookie | phone
    MEDIACRAWLER_LOGIN_TYPE: str = "cookie"
    # cookie 登录时从环境读取 Cookie 字符串（微博等）
    MEDIACRAWLER_COOKIES: str = ""
    # uv 可执行文件名（Windows 可为 uv.cmd）
    MEDIACRAWLER_UV_BIN: str = "uv"
    # MediaCrawler 使用的 Python 解释器；为空时回退到当前后端 Python
    MEDIACRAWLER_PYTHON_BIN: str = ""
    # Node.js 安装目录（例如 D:/node）；会在 MediaCrawler 子进程里注入 PATH
    MEDIACRAWLER_NODE_DIR: str = ""
    # uv 缓存目录；Windows 上可指向项目本地目录以避开用户缓存权限问题
    MEDIACRAWLER_UV_CACHE_DIR: str = ""
    # 宿主机本地 HTTP/SOCKS 代理；Clash Verge TUN/fake-ip 模式下建议填 http://127.0.0.1:7897
    MEDIACRAWLER_PROXY: str = ""
    # 是否抓取二级评论（MediaCrawler 当前支持的评论树上限）
    MEDIACRAWLER_GET_SUB_COMMENTS: bool = False
    # 单条帖子最多抓取多少条评论（含一级评论与可选二级评论）
    MEDIACRAWLER_MAX_COMMENTS_PER_POST: int = 200
    # Downloaded social media files are stored under project output by default.
    MEDIA_DOWNLOAD_ROOT: str = str(PROJECT_ROOT / "output" / "media_downloads")

    # NewsCrawler：HTTP 方式，填写新闻提取 API 根地址，例如 http://127.0.0.1:8020
    NEWSCRAWLER_API_BASE: str = ""
    # 或直接指向 NewsCrawler 仓库根目录，通过 import 调用 ExtractorService（与 API 二选一即可）
    NEWSCRAWLER_ROOT: str = ""

    # ----- LLM API (趋势预测用) -----
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_WIRE: str = "chat_completions"
    LLM_TIMEOUT_SECONDS: float = 180.0
    LLM_INCLUDE_MEDIA_BASE64: bool = False
    LLM_REQUIRE_VISION: bool = False
    KT3_EXTERNAL_RETRIEVAL_ENABLED: bool = False
    KT3_RETRIEVAL_API_KEY: str = ""
    KT3_RETRIEVAL_BASE_URL: str = ""
    KT3_RETRIEVAL_SEARCH_PATH: str = "/search"
    KT3_RETRIEVAL_PROVIDER_NAME: str = ""
    KT3_RETRIEVAL_ADAPTER: str = ""
    # Master key used to encrypt API keys stored in KT3 provider configs.
    # Keep it independent from JWT_SECRET_KEY so provider credentials can be
    # rotated and audited separately from authentication tokens.
    KT3_CONFIG_ENCRYPTION_KEY: str = ""

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

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(BASE_DIR / ".env")),
        extra="ignore",
    )


settings = Settings()
