from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TEMP_DIR = PROJECT_ROOT / "temp"

DATA_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

SUPPORTED_PLATFORMS = [
    {"id": "wechat", "name": "WeChat", "icon": "chat"},
    {"id": "toutiao", "name": "Toutiao", "icon": "news"},
    {"id": "netease", "name": "NetEase News", "icon": "news"},
    {"id": "sohu", "name": "Sohu News", "icon": "news"},
    {"id": "tencent", "name": "Tencent News", "icon": "news"},
    {"id": "detik", "name": "Detik News", "icon": "news"},
    {"id": "naver", "name": "Naver News", "icon": "news"},
    {"id": "lenny", "name": "Lenny's Newsletter", "icon": "newsletter"},
    {"id": "quora", "name": "Quora", "icon": "qa"},
    {"id": "bbc", "name": "BBC News", "icon": "news"},
    {"id": "cnn", "name": "CNN News", "icon": "news"},
    {"id": "twitter", "name": "Twitter/X", "icon": "social"},
]
