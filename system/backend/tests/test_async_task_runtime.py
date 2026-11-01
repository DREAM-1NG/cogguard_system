from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from app.tasks import analysis_tasks, crawl_tasks, review_tasks
from app.tasks import async_runtime
from app.tasks.async_runtime import close_async_runtime, run_async


def test_sync_task_runner_reuses_one_event_loop_per_worker_thread():
    async def loop_identity() -> int:
        return id(asyncio.get_running_loop())

    try:
        first = run_async(loop_identity())
        second = run_async(loop_identity())
    finally:
        close_async_runtime()

    assert first == second


def test_sync_task_runner_recreates_loop_after_shutdown():
    async def current_loop():
        return asyncio.get_running_loop()

    first = run_async(current_loop())
    close_async_runtime()
    try:
        second = run_async(current_loop())
    finally:
        close_async_runtime()

    assert first.is_closed()
    assert second is not first


def test_sync_task_runner_keeps_worker_thread_loops_isolated():
    barrier = threading.Barrier(2)

    def worker_loop():
        async def current_loop():
            return asyncio.get_running_loop()

        loop = run_async(current_loop())
        barrier.wait(timeout=5)
        close_async_runtime()
        return loop

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(worker_loop)
        second_future = executor.submit(worker_loop)
        first = first_future.result(timeout=10)
        second = second_future.result(timeout=10)

    assert first is not second
    assert first.is_closed()
    assert second.is_closed()


def test_async_runtime_closes_all_connections_after_one_failure(monkeypatch):
    calls: list[str] = []

    async def fail_mysql():
        calls.append("mysql")
        raise RuntimeError("mysql close failed")

    async def close_mongo():
        calls.append("mongo")

    async def close_redis():
        calls.append("redis")

    monkeypatch.setattr(async_runtime, "close_mysql", fail_mysql)
    monkeypatch.setattr(async_runtime, "close_mongo", close_mongo)
    monkeypatch.setattr(async_runtime, "close_redis", close_redis)

    run_async(asyncio.sleep(0))
    close_async_runtime()

    assert calls == ["mysql", "mongo", "redis"]


def test_celery_task_modules_share_one_sync_async_bridge():
    assert analysis_tasks.run_async is async_runtime.run_async
    assert crawl_tasks.run_async is async_runtime.run_async
    assert review_tasks.run_async is async_runtime.run_async
