"""Social crawler module with a small interface and internal runtime seam."""

from app.core.crawler.social.normalizers import (
    COMMENT_SORT_OPTIONS,
    generic_jsonl_to_comment,
    generic_jsonl_to_post,
    read_appended_jsonl_rows,
    sort_comments,
    weibo_comment_line_to_comment,
    weibo_content_line_to_post,
)
from app.core.crawler.social.runtime import (
    COGGUARD_TO_MEDIA,
    SUPPORTED_SOCIAL_PLATFORMS,
    MediaSocialCrawler,
)

__all__ = [
    "COMMENT_SORT_OPTIONS",
    "COGGUARD_TO_MEDIA",
    "SUPPORTED_SOCIAL_PLATFORMS",
    "MediaSocialCrawler",
    "generic_jsonl_to_comment",
    "generic_jsonl_to_post",
    "read_appended_jsonl_rows",
    "sort_comments",
    "weibo_comment_line_to_comment",
    "weibo_content_line_to_post",
]
