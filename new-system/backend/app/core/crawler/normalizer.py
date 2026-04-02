"""Normalize raw crawl data into standard format.

For Phase 1 (mock mode), the mock crawler already outputs StandardPost /
StandardComment.  This normalizer will be extended with platform-specific
mappings when real crawlers are integrated.
"""

from app.models.post import StandardComment, StandardPost


class DataNormalizer:
    @staticmethod
    def normalize_post(raw: dict, platform: str) -> StandardPost:
        return StandardPost(
            platform=platform,
            post_id=raw.get("post_id", raw.get("id", "")),
            content=raw.get("content", raw.get("text", "")),
            author_id=str(raw.get("author_id", raw.get("user_id", ""))),
            author_name=raw.get("author_name", raw.get("nickname", "unknown")),
            timestamp=raw.get("timestamp", raw.get("created_at")),
            url=raw.get("url", ""),
            likes=raw.get("likes", raw.get("like_count", 0)),
            reposts=raw.get("reposts", raw.get("repost_count", 0)),
            comments_count=raw.get("comments_count", raw.get("comment_count", 0)),
            media_urls=raw.get("media_urls", []),
            hashtags=raw.get("hashtags", []),
            raw_data=raw,
        )

    @staticmethod
    def normalize_comment(raw: dict, platform: str) -> StandardComment:
        return StandardComment(
            platform=platform,
            comment_id=raw.get("comment_id", raw.get("id", "")),
            post_id=raw.get("post_id", ""),
            content=raw.get("content", raw.get("text", "")),
            author_id=str(raw.get("author_id", raw.get("user_id", ""))),
            author_name=raw.get("author_name", raw.get("nickname", "unknown")),
            timestamp=raw.get("timestamp", raw.get("created_at")),
            reply_to=raw.get("reply_to"),
            likes=raw.get("likes", 0),
        )
