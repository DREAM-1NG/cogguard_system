"""应用配置管理模块。

通过 pydantic-settings 从 .env 文件加载环境变量，集中管理
MySQL / MongoDB / Redis / JWT 等所有配置项，并暴露组装后的
连接 URL 供各模块直接使用。
"""

from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


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

    # ----- Real crawlers (optional; see doc/ENV_SETUP.md) -----
    # MediaCrawler 仓库根目录绝对路径；未配置时无法执行 weibo/douyin 等社交采集
    MEDIACRAWLER_ROOT: str = ""
    # 调用 MediaCrawler CLI 时的登录方式：qrcode | cookie | phone
    MEDIACRAWLER_LOGIN_TYPE: str = "cookie"
    # cookie 登录时从环境读取 Cookie 字符串（微博等）
    MEDIACRAWLER_COOKIES: str = ""
    # uv 可执行文件名（Windows 可为 uv.cmd）
    MEDIACRAWLER_UV_BIN: str = "uv"

    # NewsCrawler：HTTP 方式，填写新闻提取 API 根地址，例如 http://127.0.0.1:8020
    NEWSCRAWLER_API_BASE: str = ""
    # 或直接指向 NewsCrawler 仓库根目录，通过 import 调用 ExtractorService（与 API 二选一即可）
    NEWSCRAWLER_ROOT: str = ""

    # ----- LLM API (趋势预测用) -----
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"

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

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


settings = Settings()
