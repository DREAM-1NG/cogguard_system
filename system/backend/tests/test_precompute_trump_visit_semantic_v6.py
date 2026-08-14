from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.semantic.runtime import ModelWeightsBlockedError


def _load_script():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "precompute_trump_visit_semantic_v6.py"
    spec = importlib.util.spec_from_file_location("_test_precompute_trump_visit_semantic_v6", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


class _FakeSession:
    def __init__(self, events):
        self.events = events

    async def execute(self, _statement):
        self.events.append("mysql_ready")

    async def commit(self):
        self.events.append("commit")


class _FakeMongo:
    def __init__(self, events):
        self.events = events

    async def command(self, value):
        assert value == "ping"
        self.events.append("mongo_ready")


class _QualityReport:
    def model_dump(self, **_kwargs):
        return {"status": "pass", "platform_counts": {"douyin": 2, "weibo": 2, "xhs": 2}}


class _Snapshot:
    snapshot_id = "snapshot_semantic"
    data_fingerprint = "fingerprint_semantic"
    platforms = ["douyin", "weibo", "xhs"]
    posts = [{"platform": "weibo"}, {"platform": "xhs"}, {"platform": "douyin"}]
    comments = [{"platform": "weibo"}, {"platform": "xhs"}, {"platform": "douyin"}]
    quality_report = _QualityReport()


class _PrebuiltRuntime:
    instance = None
    events = None

    @classmethod
    def ensure_runtime_dependencies(cls):
        cls.events.append("dependencies_ready")

    def __init__(self, **_kwargs):
        type(self).instance = self
        type(self).events.append("runtime_ready")


class _BlockedRuntime:
    events = None

    @classmethod
    def ensure_runtime_dependencies(cls):
        cls.events.append("dependencies_checked")
        raise ModelWeightsBlockedError("jieba runtime dependency unavailable")


def _fake_importer(events):
    sources = {
        platform: SimpleNamespace(
            platform=platform,
            posts_path=Path(f"{platform}-posts.jsonl"),
            comments_path=Path(f"{platform}-comments.jsonl"),
            creator_profiles_path=None,
            post_details_path=None,
        )
        for platform in ("weibo", "xhs", "douyin")
    }

    async def upsert_platform_result(_result, *, job_id):
        assert job_id > 0
        events.append("data_mutation")

    async def reconcile_legacy_weibo_manifest(_normalized, *, event_id, execute):
        assert event_id == "trump_visit_2026_05_21"
        assert execute is True
        events.append("manifest_reconciliation")
        return {
            "post_preview": 58,
            "post_deleted": 58,
            "comment_preview": 4068,
            "comment_deleted": 4068,
        }

    def normalize_platform_files(*, platform, **_kwargs):
        return SimpleNamespace(
            platform=platform,
            posts=[{"platform": platform}],
            comments=[{"platform": platform}],
            stats={"unique_posts": 1, "unique_comments": 1},
        )

    return SimpleNamespace(
        build_latest_trump_visit_sources=lambda _root: sources,
        normalize_platform_files=normalize_platform_files,
        ensure_mysql_import_job=lambda *_args, **_kwargs: 1,
        upsert_platform_result=upsert_platform_result,
        reconcile_legacy_weibo_manifest=reconcile_legacy_weibo_manifest,
    )


def _args(tmp_path: Path, *, execute: bool = True):
    return Namespace(
        data_runs_root=str(tmp_path / "data-runs"),
        model_root=str(tmp_path / "models"),
        embedding_root=str(tmp_path / "embeddings"),
        primary_claim="official primary claim",
        execute=execute,
    )


def test_precompute_persists_observed_propagation_before_semantic_enrichment(monkeypatch, tmp_path: Path, capsys):
    script = _load_script()
    events: list[str] = []
    captures: dict[str, object] = {}
    _PrebuiltRuntime.events = events
    _PrebuiltRuntime.instance = None
    snapshot = _Snapshot()

    class FakeRegistry:
        def __init__(self, **_kwargs):
            pass

        async def create_event_snapshot(self, **_kwargs):
            events.append("snapshot_mutation")
            return snapshot

        async def create_run(self, **kwargs):
            events.append("run_mutation")
            captures["requested_stages"] = kwargs["requested_stages"]
            return {"run_id": "run_semantic"}

    class FakeExecutor:
        def __init__(self, *, registry, engines):
            captures["registry"] = registry
            captures["engines"] = engines

        async def execute_run(self, run_id):
            assert run_id == "run_semantic"
            events.append("semantic_completed")
            return {
                "run_id": run_id,
                "status": "completed",
                "results": {
                    "semantic_enrichment": {
                        "status": "ok",
                        "model_versions": {"bge_embedding": "BAAI/bge-small-zh-v1.5@7999e1d"},
                        "embedding_manifest": {"artifact_sha256": "abc"},
                    }
                },
            }

    sentinel_ports = SimpleNamespace(propagation=None)

    def fake_default_ports(*, semantic_runtime=None, semantic_engine=None):
        captures["semantic_runtime"] = semantic_runtime
        captures["semantic_engine"] = semantic_engine
        return sentinel_ports

    monkeypatch.setattr(script, "import_mediacrawler_data_runs", _fake_importer(events))
    monkeypatch.setattr(script, "SemanticEnrichmentRuntime", _PrebuiltRuntime)
    monkeypatch.setattr(script, "async_session_factory", lambda: _AsyncContext(_FakeSession(events)))
    monkeypatch.setattr(script, "get_mongo_db", lambda: _FakeMongo(events))
    monkeypatch.setattr(script, "SqlAlchemyAnalysisStore", lambda _db: object())
    monkeypatch.setattr(script, "AnalysisRegistry", FakeRegistry)
    monkeypatch.setattr(script, "default_analysis_engine_ports", fake_default_ports)
    monkeypatch.setattr(script, "AnalysisExecutor", FakeExecutor)
    monkeypatch.setattr(script, "close_mongo", lambda: asyncio.sleep(0))

    exit_code = asyncio.run(script.main_async(_args(tmp_path)))
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captures["requested_stages"] == ["propagation_analysis", "semantic_enrichment"]
    assert captures["semantic_runtime"] is _PrebuiltRuntime.instance
    assert captures["engines"] is sentinel_ports
    assert isinstance(sentinel_ports.propagation, script.SnapshotObservedPropagationEngine)
    assert events.index("dependencies_ready") < events.index("data_mutation")
    assert events.index("runtime_ready") < events.index("data_mutation")
    assert events.index("mysql_ready") < events.index("data_mutation")
    assert events.index("mongo_ready") < events.index("data_mutation")
    assert events.index("semantic_completed") < events.index("commit")
    assert summary["platform_counts"] == {
        "douyin": {"comments": 1, "posts": 1},
        "weibo": {"comments": 1, "posts": 1},
        "xhs": {"comments": 1, "posts": 1},
    }
    assert summary["semantic_status"] == "ok"
    assert summary["model_versions"] == {"bge_embedding": "BAAI/bge-small-zh-v1.5@7999e1d"}
    assert summary["embedding_manifest"] == {"artifact_sha256": "abc"}


def test_precompute_reconciles_the_current_manifest_after_upsert_and_before_snapshot(monkeypatch, tmp_path: Path, capsys):
    script = _load_script()
    events: list[str] = []
    _PrebuiltRuntime.events = events
    snapshot = _Snapshot()

    class FakeRegistry:
        def __init__(self, **_kwargs):
            pass

        async def create_event_snapshot(self, **_kwargs):
            events.append("snapshot_mutation")
            return snapshot

        async def create_run(self, **_kwargs):
            return {"run_id": "run_semantic"}

    class FakeExecutor:
        def __init__(self, **_kwargs):
            pass

        async def execute_run(self, run_id):
            return {
                "run_id": run_id,
                "status": "completed",
                "results": {"semantic_enrichment": {"status": "ok"}},
            }

    monkeypatch.setattr(script, "import_mediacrawler_data_runs", _fake_importer(events))
    monkeypatch.setattr(script, "SemanticEnrichmentRuntime", _PrebuiltRuntime)
    monkeypatch.setattr(script, "async_session_factory", lambda: _AsyncContext(_FakeSession(events)))
    monkeypatch.setattr(script, "get_mongo_db", lambda: _FakeMongo(events))
    monkeypatch.setattr(script, "SqlAlchemyAnalysisStore", lambda _db: object())
    monkeypatch.setattr(script, "AnalysisRegistry", FakeRegistry)
    monkeypatch.setattr(script, "AnalysisExecutor", FakeExecutor)
    monkeypatch.setattr(script, "close_mongo", lambda: asyncio.sleep(0))

    exit_code = asyncio.run(script.main_async(_args(tmp_path)))
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert events.index("data_mutation") < events.index("manifest_reconciliation")
    assert events.index("manifest_reconciliation") < events.index("snapshot_mutation")
    assert summary["reconciliation"] == {
        "post_preview": 58,
        "post_deleted": 58,
        "comment_preview": 4068,
        "comment_deleted": 4068,
    }


def test_precompute_stops_before_snapshot_when_manifest_reconciliation_fails(monkeypatch, tmp_path: Path):
    script = _load_script()
    events: list[str] = []
    _PrebuiltRuntime.events = events

    class UnexpectedRegistry:
        def __init__(self, **_kwargs):
            raise AssertionError("a failed reconciliation must stop before snapshot creation")

    importer = _fake_importer(events)

    async def fail_reconciliation(*_args, **_kwargs):
        events.append("manifest_reconciliation")
        raise RuntimeError("legacy manifest cleanup failed")

    importer.reconcile_legacy_weibo_manifest = fail_reconciliation
    monkeypatch.setattr(script, "import_mediacrawler_data_runs", importer)
    monkeypatch.setattr(script, "SemanticEnrichmentRuntime", _PrebuiltRuntime)
    monkeypatch.setattr(script, "async_session_factory", lambda: _AsyncContext(_FakeSession(events)))
    monkeypatch.setattr(script, "get_mongo_db", lambda: _FakeMongo(events))
    monkeypatch.setattr(script, "AnalysisRegistry", UnexpectedRegistry)
    monkeypatch.setattr(script, "close_mongo", lambda: asyncio.sleep(0))

    with pytest.raises(RuntimeError, match="legacy manifest cleanup failed"):
        asyncio.run(script.main_async(_args(tmp_path)))

    assert events.index("data_mutation") < events.index("manifest_reconciliation")
    assert "snapshot_mutation" not in events


def test_precompute_reports_a_blocked_runtime_before_any_data_mutation(monkeypatch, tmp_path: Path, capsys):
    script = _load_script()
    events: list[str] = []
    _BlockedRuntime.events = events

    monkeypatch.setattr(script, "import_mediacrawler_data_runs", _fake_importer(events))
    monkeypatch.setattr(script, "SemanticEnrichmentRuntime", _BlockedRuntime)
    monkeypatch.setattr(script, "async_session_factory", lambda: _AsyncContext(_FakeSession(events)))
    monkeypatch.setattr(script, "get_mongo_db", lambda: _FakeMongo(events))
    monkeypatch.setattr(script, "close_mongo", lambda: asyncio.sleep(0))

    exit_code = asyncio.run(script.main_async(_args(tmp_path)))
    summary = json.loads(capsys.readouterr().out)

    assert exit_code != 0
    assert "data_mutation" not in events
    assert summary["semantic_status"] == "model_weights_blocked"
    assert summary["blocking_reason"] == "jieba runtime dependency unavailable"
    assert summary["run_id"] is None


def test_precompute_returns_nonzero_when_executor_blocks_the_semantic_stage(monkeypatch, tmp_path: Path, capsys):
    script = _load_script()
    events: list[str] = []
    _PrebuiltRuntime.events = events
    snapshot = _Snapshot()

    class FakeRegistry:
        def __init__(self, **_kwargs):
            pass

        async def create_event_snapshot(self, **_kwargs):
            return snapshot

        async def create_run(self, **_kwargs):
            return {"run_id": "run_semantic_blocked"}

    class BlockedExecutor:
        def __init__(self, **_kwargs):
            pass

        async def execute_run(self, run_id):
            assert run_id == "run_semantic_blocked"
            return {
                "run_id": run_id,
                "status": "needs_evidence",
                "results": {
                    "semantic_enrichment": {
                        "status": "model_weights_blocked",
                        "runtime_status": "blocked",
                        "blocking_reason": "bge_embedding unavailable at execution time",
                    }
                },
            }

    monkeypatch.setattr(script, "import_mediacrawler_data_runs", _fake_importer(events))
    monkeypatch.setattr(script, "SemanticEnrichmentRuntime", _PrebuiltRuntime)
    monkeypatch.setattr(script, "async_session_factory", lambda: _AsyncContext(_FakeSession(events)))
    monkeypatch.setattr(script, "get_mongo_db", lambda: _FakeMongo(events))
    monkeypatch.setattr(script, "SqlAlchemyAnalysisStore", lambda _db: object())
    monkeypatch.setattr(script, "AnalysisRegistry", FakeRegistry)
    monkeypatch.setattr(script, "AnalysisExecutor", BlockedExecutor)
    monkeypatch.setattr(script, "close_mongo", lambda: asyncio.sleep(0))

    exit_code = asyncio.run(script.main_async(_args(tmp_path)))
    summary = json.loads(capsys.readouterr().out)

    assert exit_code != 0
    assert summary["status"] == "needs_evidence"
    assert summary["semantic_status"] == "model_weights_blocked"
    assert summary["blocking_reason"] == "bge_embedding unavailable at execution time"


def test_precompute_validation_only_does_not_create_snapshot_or_run(monkeypatch, tmp_path: Path, capsys):
    script = _load_script()
    events: list[str] = []
    _PrebuiltRuntime.events = events

    class UnexpectedRegistry:
        def __init__(self, **_kwargs):
            raise AssertionError("validation-only precompute must not create a registry")

    monkeypatch.setattr(script, "import_mediacrawler_data_runs", _fake_importer(events))
    monkeypatch.setattr(script, "SemanticEnrichmentRuntime", _PrebuiltRuntime)
    monkeypatch.setattr(script, "async_session_factory", lambda: _AsyncContext(_FakeSession(events)))
    monkeypatch.setattr(script, "get_mongo_db", lambda: _FakeMongo(events))
    monkeypatch.setattr(script, "AnalysisRegistry", UnexpectedRegistry)
    monkeypatch.setattr(script, "close_mongo", lambda: asyncio.sleep(0))

    exit_code = asyncio.run(script.main_async(_args(tmp_path, execute=False)))
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["status"] == "validation_only"
    assert summary["semantic_status"] == "validation_only"
    assert summary["snapshot_id"] is None
    assert summary["run_id"] is None
    assert "data_mutation" not in events
    assert "manifest_reconciliation" not in events
