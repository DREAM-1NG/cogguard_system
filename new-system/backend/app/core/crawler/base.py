"""爬虫引擎抽象基类。

定义所有平台爬虫必须实现的接口规范：
- ``search``: 按关键词搜索帖子
- ``fetch_comments``: 获取指定帖子的评论

具体实现见 ``mock.py``（模拟数据）和后续的 ``social.py`` / ``news.py``。
"""

from abc import ABC, abstractmethod

from app.models.post import StandardComment, StandardPost


class BaseCrawler(ABC):
    """爬虫基类，所有平台爬虫需继承此类并实现抽象方法。"""
    platform: str = ""

    def __init__(self) -> None:
        #: 新闻等场景下的文章 URL 列表（与 Celery 任务参数 ``post_ids`` 对应）
        self.post_ids: list[str] = []

    @abstractmethod
    async def search(self, keywords: list[str], max_posts: int = 50) -> list[StandardPost]:
        ...

    @abstractmethod
    async def fetch_comments(self, post_id: str, max_comments: int = 100) -> list[StandardComment]:
        ...
