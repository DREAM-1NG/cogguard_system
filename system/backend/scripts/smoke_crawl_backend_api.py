"""Screenshot-friendly smoke test for the crawl backend API."""

from __future__ import annotations

import time
import os

import httpx
from pymongo import MongoClient


BASE_URL = "http://127.0.0.1:8000/api/v1"
EVENT_ID = "backend_screenshot_smoke_20260702"


def main() -> None:
    print("=== CogGuard Crawler Backend API Test ===")
    print("Workdir: G:\\CISCN\\CogGuard\\system\\backend")
    print(f"API base: {BASE_URL}")
    print()

    mongo = MongoClient("mongodb://cogguard:cogguard123@127.0.0.1:27017/?authSource=admin")[
        "cogguard"
    ]
    mongo.raw_posts.delete_many({"event_id": EVENT_ID})
    mongo.raw_comments.delete_many({"event_id": EVENT_ID})

    health = httpx.get(f"{BASE_URL}/health", timeout=10)
    print(f"[1] GET /api/v1/health -> HTTP {health.status_code}, body={health.text}")

    platforms = httpx.get(f"{BASE_URL}/crawl/platforms", timeout=10)
    platform_items = platforms.json()["data"]
    print(f"[2] GET /api/v1/crawl/platforms -> HTTP {platforms.status_code}, count={len(platform_items)}")
    for item in platform_items:
        print(f"    platform={item['id']}, name={item['name']}, status={item['status']}")

    login = httpx.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": os.environ.get("COGGUARD_SMOKE_USERNAME", "admin"),
            "password": os.environ.get("COGGUARD_SMOKE_PASSWORD", ""),
        },
        timeout=10,
    )
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[3] POST /api/v1/auth/login -> HTTP {login.status_code}, token_len={len(token)}")

    existing = httpx.get(
        f"{BASE_URL}/crawl/data",
        params={"platform": "weibo", "keyword": "特朗普", "page": 1, "page_size": 2},
        headers=headers,
        timeout=20,
    )
    existing_payload = existing.json()["data"]
    print(
        "[4] GET /api/v1/crawl/data platform=weibo keyword=特朗普 "
        f"-> HTTP {existing.status_code}, total={existing_payload['total']}, "
        f"returned={len(existing_payload['items'])}"
    )
    for post in existing_payload["items"]:
        content = post.get("content") or ""
        if len(content) > 40:
            content = content[:40] + "..."
        print(
            f"    post_id={post.get('post_id')}, author={post.get('author_name')}, "
            f"likes={post.get('likes')}, content={content}"
        )

    create = httpx.post(
        f"{BASE_URL}/crawl/social",
        json={
            "platform": "mock_weibo",
            "keywords": ["backend-screenshot-smoke"],
            "event_id": EVENT_ID,
            "source_keyword": "backend-screenshot-smoke",
            "max_posts": 2,
            "crawl_comments": False,
            "execution_mode": "local",
        },
        headers=headers,
        timeout=20,
    )
    job = create.json()["data"]
    job_id = job["id"]
    print(
        f"[5] POST /api/v1/crawl/social -> HTTP {create.status_code}, "
        f"job_id={job_id}, status={job['status']}, celery_task_id={job['celery_task_id']}"
    )

    final_job = job
    for attempt in range(1, 21):
        time.sleep(0.5)
        jobs = httpx.get(
            f"{BASE_URL}/crawl/jobs",
            params={"page": 1, "page_size": 20},
            headers=headers,
            timeout=10,
        ).json()["data"]["items"]
        matched = [item for item in jobs if item["id"] == job_id]
        if not matched:
            continue
        final_job = matched[0]
        print(f"[6.{attempt}] job status -> status={final_job['status']}, progress={final_job['progress']}")
        if final_job["status"] in {"completed", "failed", "cancelled"}:
            break

    posts_count = mongo.raw_posts.count_documents({"event_id": EVENT_ID})
    comments_count = mongo.raw_comments.count_documents({"event_id": EVENT_ID})
    sample = mongo.raw_posts.find_one(
        {"event_id": EVENT_ID},
        {"_id": 0, "event_id": 1, "platform": 1, "post_id": 1, "content": 1, "crawl_job_id": 1},
    )
    print(f"[7] MongoDB ingest check -> posts={posts_count}, comments={comments_count}")
    print(f"[8] sample inserted document -> {sample}")

    cleanup = httpx.delete(f"{BASE_URL}/crawl/jobs/{job_id}", headers=headers, timeout=20)
    left_posts = mongo.raw_posts.count_documents({"event_id": EVENT_ID})
    left_comments = mongo.raw_comments.count_documents({"event_id": EVENT_ID})
    print(f"[9] DELETE /api/v1/crawl/jobs/{job_id} -> HTTP {cleanup.status_code}, body={cleanup.text}")
    print(f"[10] after cleanup -> posts={left_posts}, comments={left_comments}")

    if final_job["status"] != "completed" or posts_count != 2 or left_posts != 0:
        raise SystemExit("Smoke test failed")

    print()
    print("=== Crawler Backend API Test Passed ===")
    print("You can screenshot this terminal window.")


if __name__ == "__main__":
    main()
