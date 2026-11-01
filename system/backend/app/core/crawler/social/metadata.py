from __future__ import annotations

from typing import Any


def build_social_crawl_metadata(
    *,
    crawl_comments: bool,
    recursive_comments: bool,
    enrich_author_profiles: bool,
    comment_sort: str,
    max_comments_per_post: int,
    output_files: dict[str, str] | None = None,
    raw_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "comments_requested": crawl_comments,
        "recursive_comments_requested": recursive_comments,
        "recursive_comments_supported": False,
        "effective_comment_depth": 2 if crawl_comments and recursive_comments else 1,
        "author_profile_enrichment_requested": enrich_author_profiles,
        "author_profile_enrichment_supported": False,
        "author_profile_source": "search_result_payload",
        "comment_sort": comment_sort,
        "max_comments_per_post": max_comments_per_post,
        "execution_mode": "internal_social_runtime_cli",
        "ingestion_mode": "jsonl_delta",
    }
    if output_files:
        metadata["output_files"] = output_files
    if raw_counts:
        metadata["raw_counts"] = raw_counts
    return metadata
