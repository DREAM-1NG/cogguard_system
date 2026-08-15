from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest


def _seed_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "seed_trump_visit_case_workbench.py"
    spec = importlib.util.spec_from_file_location("seed_trump_visit_case_workbench", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Posts:
    async def find_one(self, _query, _projection):
        return {
            "content": "An authority quotation.",
            "url": "",
        }


class _Mongo:
    raw_posts = _Posts()


def test_authority_post_requires_original_url():
    module = _seed_module()

    async def scenario():
        with pytest.raises(RuntimeError, match="authority post URL is empty"):
            await module._load_authority_post(
                _Mongo(),
                {"platform": "weibo", "author_id": "source", "post_id": "post"},
            )

    asyncio.run(scenario())
