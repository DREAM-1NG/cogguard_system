"""日志配置模块。

使用 loguru 替代标准 logging，配置控制台输出（DEBUG 级别）
和按日期轮转的文件输出（INFO 级别，保留 30 天）。
"""

import sys

from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
)
logger.add(
    "logs/cogguard_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    encoding="utf-8",
)
