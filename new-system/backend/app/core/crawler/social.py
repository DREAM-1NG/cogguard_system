"""MediaCrawler 封装：通过子进程调用上游 ``main.py``，并解析产出 JSONL。"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.crawler.base import BaseCrawler
from app.models.post import StandardComment, StandardPost

# CogGuard platform id -> (MediaCrawler --platform 代码, data/ 下子目录名)
COGGUARD_TO_MEDIA: dict[str, tuple[str, str]] = {
    "weibo": ("wb", "weibo"),
    "douyin": ("dy", "douyin"),
    "xhs": ("xhs", "xhs"),
    "kuaishou": ("ks", "kuaishou"),
    "bilibili": ("bili", "bili"),
    "tieba": ("tieba", "tieba"),
    "zhihu": ("zhihu", "zhihu"),
}


def _parse_ts(val: Any) -> datetime:
    if val is None or val == "":
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(float(val), tz=timezone.utc)
        s = str(val).strip()
        if s.isdigit():
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
    except (ValueError, OSError):
        pass
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def weibo_content_line_to_post(raw: dict, cogguard_platform: str) -> StandardPost:
    """MediaCrawler 微博 ``search_contents_*.jsonl`` 行。"""
    note_id = str(raw.get("note_id", ""))
    return StandardPost(
        platform=cogguard_platform,
        post_id=note_id,
        content=str(raw.get("content", "")),
        author_id=str(raw.get("user_id", "")),
        author_name=str(raw.get("nickname", "")),
        timestamp=_parse_ts(raw.get("create_time")),
        url=str(raw.get("note_url", "")),
        likes=int(str(raw.get("liked_count", "0") or 0)),
        reposts=int(str(raw.get("shared_count", "0") or 0)),
        comments_count=int(str(raw.get("comments_count", "0") or 0)),
        media_urls=[],
        hashtags=[],
        raw_data=raw,
    )


def weibo_comment_line_to_comment(raw: dict, cogguard_platform: str) -> StandardComment:
    return StandardComment(
        platform=cogguard_platform,
        comment_id=str(raw.get("comment_id", "")),
        post_id=str(raw.get("note_id", "")),
        content=str(raw.get("content", "")),
        author_id=str(raw.get("user_id", "")),
        author_name=str(raw.get("nickname", "")),
        timestamp=_parse_ts(raw.get("create_time")),
        reply_to=str(raw.get("parent_comment_id", "") or "") or None,
        likes=int(str(raw.get("comment_like_count", "0") or 0)),
    )


def generic_jsonl_to_post(raw: dict, cogguard_platform: str) -> StandardPost:
    """其他平台 JSONL 的宽松映射（字段因平台而异）。"""
    pid = str(raw.get("note_id") or raw.get("aweme_id") or raw.get("id") or raw.get("video_id") or "")
    content = str(raw.get("content") or raw.get("desc") or raw.get("title") or "")
    uid = str(raw.get("user_id") or raw.get("uid") or raw.get("author_id") or "")
    name = str(raw.get("nickname") or raw.get("author_name") or raw.get("user_name") or "unknown")
    url = str(raw.get("note_url") or raw.get("url") or raw.get("share_url") or "")
    return StandardPost(
        platform=cogguard_platform,
        post_id=pid or str(hash(json.dumps(raw, sort_keys=True, default=str)))[:16],
        content=content,
        author_id=uid,
        author_name=name,
        timestamp=_parse_ts(raw.get("create_time") or raw.get("create_ts")),
        url=url,
        likes=int(raw.get("liked_count", 0) or raw.get("digg_count", 0) or 0),
        reposts=int(raw.get("shared_count", 0) or raw.get("share_count", 0) or 0),
        comments_count=int(raw.get("comments_count", 0) or raw.get("comment_count", 0) or 0),
        media_urls=list(raw.get("media_urls", []) or []),
        hashtags=list(raw.get("hashtags", []) or []),
        raw_data=raw,
    )


class MediaSocialCrawler(BaseCrawler):
    """真实社交爬虫：依赖本地 MediaCrawler 仓库与 ``uv run main.py``。"""

    def __init__(self, cogguard_platform: str) -> None:
        super().__init__()
        if cogguard_platform not in COGGUARD_TO_MEDIA:
            raise ValueError(f"不支持的社交平台: {cogguard_platform}")
        self.cogguard_platform = cogguard_platform
        self._mc_code, self._data_subdir = COGGUARD_TO_MEDIA[cogguard_platform]
        self.platform = cogguard_platform
        self.last_comments: list[StandardComment] = []

    async def search(self, keywords: list[str], max_posts: int = 50) -> list[StandardPost]:
        self.last_comments = []
        root = (settings.MEDIACRAWLER_ROOT or "").strip()
        if not root or not Path(root).is_dir():
            raise RuntimeError(
                "未配置有效的 MEDIACRAWLER_ROOT，无法调用 MediaCrawler。"
                " 请设置环境变量为 MediaCrawler 仓库根目录绝对路径。"
            )

        uv = shutil.which(settings.MEDIACRAWLER_UV_BIN.strip() or "uv")
        if not uv:
            raise RuntimeError("未找到 uv 可执行文件，请安装 uv 或设置 MEDIACRAWLER_UV_BIN。")

        kw = ",".join(k.strip() for k in keywords if k.strip())
        if not kw:
            raise ValueError("关键词不能为空（社交搜索模式）。")

        mc_root = Path(root).resolve()
        main_py = mc_root / "main.py"
        if not main_py.is_file():
            raise RuntimeError(f"在 {mc_root} 未找到 main.py，请确认 MEDIACRAWLER_ROOT 指向 MediaCrawler 根目录。")

        lt = settings.MEDIACRAWLER_LOGIN_TYPE.strip() or "cookie"
        cookies = settings.MEDIACRAWLER_COOKIES or ""

        cmd: list[str] = [
            uv,
            "run",
            "main.py",
            "--platform",
            self._mc_code,
            "--lt",
            lt,
            "--type",
            "search",
            "--keywords",
            kw,
            "--get_comment",
            "yes",
            "--save_data_option",
            "jsonl",
        ]
        if cookies and lt == "cookie":
            cmd.extend(["--cookies", cookies])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(mc_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace")[-4000:]
            out = (stdout or b"").decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"MediaCrawler 进程失败 (exit={proc.returncode}): {err or out}")

        posts = self._load_posts_from_jsonl(mc_root, max_posts)
        self._load_comments_from_jsonl(mc_root)
        return posts

    def _load_posts_from_jsonl(self, mc_root: Path, max_posts: int) -> list[StandardPost]:
        data_dir = mc_root / "data" / self._data_subdir / "jsonl"
        if not data_dir.is_dir():
            return []
        files = sorted(data_dir.glob("search_contents_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return []
        posts: list[StandardPost] = []
        with files[0].open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if self.cogguard_platform == "weibo":
                    posts.append(weibo_content_line_to_post(raw, self.cogguard_platform))
                else:
                    posts.append(generic_jsonl_to_post(raw, self.cogguard_platform))
                if len(posts) >= max_posts:
                    break
        return posts

    def _load_comments_from_jsonl(self, mc_root: Path) -> None:
        data_dir = mc_root / "data" / self._data_subdir / "jsonl"
        if not data_dir.is_dir():
            return
        files = sorted(data_dir.glob("search_comments_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return
        with files[0].open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if self.cogguard_platform == "weibo":
                    self.last_comments.append(weibo_comment_line_to_comment(raw, self.cogguard_platform))
                else:
                    # 通用评论行（字段可能不一致）
                    self.last_comments.append(
                        StandardComment(
                            platform=self.cogguard_platform,
                            comment_id=str(raw.get("comment_id", raw.get("cid", ""))),
                            post_id=str(raw.get("note_id", raw.get("aweme_id", ""))),
                            content=str(raw.get("content", raw.get("text", ""))),
                            author_id=str(raw.get("user_id", "")),
                            author_name=str(raw.get("nickname", "")),
                            timestamp=_parse_ts(raw.get("create_time")),
                            reply_to=None,
                            likes=int(raw.get("comment_like_count", 0) or 0),
                        )
                    )

    async def fetch_comments(self, post_id: str, max_comments: int = 100) -> list[StandardComment]:
        """评论已在 search 阶段通过 JSONL 批量加载，此处按 post_id 过滤。"""
        out = [c for c in self.last_comments if c.post_id == post_id]
        return out[:max_comments]
