from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime, timezone
from typing import Any

from app.core.analysis import DEFAULT_ANALYSIS_STAGES, TimeWindow, build_event_snapshot
from app.core.analysis import semantic_enrichment as semantic_enrichment_module
from app.core.analysis.semantic_enrichment import (
    SemanticModelUnavailable,
    analyze_semantic_enrichment_snapshot,
    propagation_path_overlay,
)
from app.core.analysis.executor import (
    AnalysisEnginePorts,
    AnalysisExecutor,
    UnavailableTeacherJobPort,
)
from app.core.analysis.registry import AnalysisRegistry


class FakeSnapshotCollection:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        return self.documents.get(str(query["snapshot_id"]))


class FakeArtifactCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> None:
        artifact_id = str(query["artifact_id"])
        if "$set" in update:
            self.documents[artifact_id] = {**self.documents.get(artifact_id, {}), **dict(update["$set"])}


class FakeAnalysisStore:
    def __init__(self, snapshot_record: dict[str, Any], run: dict[str, Any]) -> None:
        self.snapshot_record = snapshot_record
        self.runs = {run["run_id"]: dict(run)}
        self.events: list[dict[str, Any]] = []
        self.next_event_id = 1

    async def get_snapshot_record(self, snapshot_id: str) -> dict[str, Any] | None:
        if self.snapshot_record["snapshot_id"] == snapshot_id:
            return dict(self.snapshot_record)
        return None

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.runs.get(run_id)
        return dict(run) if run else None

    async def update_run_status(self, *, run_id: str, status, payload: dict[str, Any], finished: bool):
        run = self.runs[run_id]
        run["status"] = status.value
        run["result"] = payload
        if finished:
            run["finished_at"] = "finished"
        return dict(run)

    async def update_artifact_manifest(self, *, run_id: str, manifest: dict[str, Any]):
        run = self.runs[run_id]
        run["artifact_manifest"] = manifest
        return dict(run)

    async def append_run_event(self, *, run_id: str, event_type: str, status, payload: dict[str, Any]):
        event = {
            "id": self.next_event_id,
            "run_id": run_id,
            "event_type": event_type,
            "status": status.value,
            "payload": payload,
        }
        self.next_event_id += 1
        self.events.append(event)
        return dict(event)

    async def list_run_events(self, *, run_id: str, after_id: int = 0, limit: int = 100):
        return [event for event in self.events if event["run_id"] == run_id and event["id"] > after_id][:limit]


class StaticCoordinationEngine:
    async def analyze(self, snapshot, options):
        return {"status": "ok", "summary": {"coordinated_edges": 0}}


class StaticPropagationEngine:
    async def hindcast(self, snapshot, options):
        return {"status": "ok", "next_hop_ranking": {"items": []}}


class StaticSemanticEngine:
    async def analyze(self, snapshot, options):
        return analyze_semantic_enrichment_snapshot(snapshot, options, runtime=FakeSemanticRuntime())


class StaticStudentRuntime:
    async def predict(self, case):
        return {"status": "ok", "verdict_type": "preliminary", "label": "uncertain"}


class QueuedTeacherJobPort:
    async def submit(self, case):
        return {"status": "queued", "job_id": "teacher_case_review_1", "verdict_type": "teacher_advisory"}


class FakeSemanticRuntime:
    runtime_backend = "fake_lm_encoder"
    cache_dir = r"G:\CISCN\hf_models"
    device = "cpu"
    model_versions = {
        "embedding": semantic_enrichment_module.EMBEDDING_MODEL_VERSION,
        "sentiment": semantic_enrichment_module.SENTIMENT_MODEL_VERSION,
        "stance": semantic_enrichment_module.STANCE_MODEL_VERSION,
        "ner": semantic_enrichment_module.NER_MODEL_VERSION,
    }

    def __init__(self) -> None:
        self.encoded_texts: list[str] = []
        self.sentiment_call_sizes: list[int] = []
        self.stance_call_sizes: list[int] = []
        self.entity_call_sizes: list[int] = []

    def encode_texts(self, texts: list[str]):
        self.encoded_texts.extend(texts)
        base = [
            [1.0, 0.0, 0.0],
            [0.94, 0.06, 0.0],
            [0.0, 1.0, 0.0],
            [0.1, 0.9, 0.0],
        ]
        return base[: len(texts)]

    def classify_sentiment(self, rows):
        self.sentiment_call_sizes.append(len(rows))
        labels = [
            {"label": "positive", "score": 0.91},
            {"label": "neutral", "score": 0.67},
            {"label": "positive", "score": 0.83},
            {"label": "negative", "score": 0.72},
        ]
        return labels[: len(rows)]

    def classify_stance(self, rows, primary_claim: str):
        self.stance_call_sizes.append(len(rows))
        labels = [
            {"label": "support", "score": 0.88},
            {"label": "neutral", "score": 0.61},
            {"label": "support", "score": 0.76},
            {"label": "deny", "score": 0.7},
        ]
        return labels[: len(rows)]

    def extract_entities(self, rows):
        self.entity_call_sizes.append(len(rows))
        entities = [
            [{"entity": "特朗普", "entity_type": "person", "score": 0.92}],
            [{"entity": "中美关系", "entity_type": "topic", "score": 0.89}],
            [{"entity": "中国", "entity_type": "location_or_country", "score": 0.9}],
            [{"entity": "央视新闻", "entity_type": "organization", "score": 0.87}],
        ]
        return entities[: len(rows)]


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _snapshot():
    return build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "author_name": "新华社",
                "timestamp": _dt(14),
                "content": "特朗普访华欢迎仪式引发大量讨论，中美关系稳定前行。",
                "hashtags": ["特朗普访华", "中美关系"],
            },
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "xhs",
                "post_id": "p2",
                "author_id": "u2",
                "author_name": "观察账号",
                "timestamp": _dt(14, 1),
                "content": "欢迎宴会细节曝光，网友关注访问行程。",
                "hashtags": ["特朗普访华"],
            },
        ],
        comments=[
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "weibo",
                "comment_id": "c1",
                "post_id": "p1",
                "reply_to": "p1",
                "author_id": "u3",
                "timestamp": _dt(14, 2),
                "content": "希望关系稳定。",
            }
        ],
        core_window=TimeWindow(start=_dt(11), end=_dt(22)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def test_default_analysis_stage_contract_stays_four_stage():
    assert DEFAULT_ANALYSIS_STAGES == (
        "coordination_discover",
        "propagation_analysis",
        "student",
        "teacher",
    )


def test_executor_runs_explicit_semantic_enrichment_without_primary_claim():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_semantic",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["semantic_enrichment"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                ),
                "analysis_run_artifacts": FakeArtifactCollection(),
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=StaticCoordinationEngine(),
                propagation=StaticPropagationEngine(),
                semantic=StaticSemanticEngine(),
                student=StaticStudentRuntime(),
                teacher=UnavailableTeacherJobPort(),
            ),
        )

        result = await executor.execute_run("run_semantic")
        semantic = result["results"]["semantic_enrichment"]

        assert result["status"] == "needs_evidence"
        assert semantic["status"] == "partial"
        assert semantic["technology"] == "semantic_enrichment"
        assert semantic["model_status"] == "candidate_unvalidated"
        assert semantic["stance"]["status"] == "blocked"
        assert semantic["stance"]["code"] == "blocked_missing_primary_claim"
        assert semantic["sentiment"]["summary"]["total_texts"] == 3
        assert semantic["keywords"]["main_posts"][0]["term"]
        assert semantic["topics"]["main_posts"]["topic_count"] >= 1
        assert semantic["entities"]["main_posts"]
        assert result["artifact_manifest"]["stages"]["semantic_enrichment"]["claimability"] == "non_claimable"

    asyncio.run(scenario())


def test_missing_primary_claim_status_is_not_hidden_by_queued_teacher_job():
    async def scenario():
        snapshot = _snapshot()
        store = FakeAnalysisStore(
            snapshot_record={
                "snapshot_id": snapshot.snapshot_id,
                "mongo_collection": "analysis_event_snapshots",
                "mongo_key": snapshot.snapshot_id,
            },
            run={
                "run_id": "run_semantic_teacher",
                "event_id": snapshot.event_id,
                "snapshot_id": snapshot.snapshot_id,
                "status": "queued",
                "requested_stages": ["semantic_enrichment", "teacher"],
                "options": {},
                "finished_at": None,
            },
        )
        registry = AnalysisRegistry(
            mongo_db={
                "analysis_event_snapshots": FakeSnapshotCollection(
                    {snapshot.snapshot_id: snapshot.model_dump(mode="json")}
                ),
                "analysis_run_artifacts": FakeArtifactCollection(),
            },
            store=store,
        )
        executor = AnalysisExecutor(
            registry=registry,
            engines=AnalysisEnginePorts(
                coordination=StaticCoordinationEngine(),
                propagation=StaticPropagationEngine(),
                semantic=StaticSemanticEngine(),
                student=StaticStudentRuntime(),
                teacher=QueuedTeacherJobPort(),
            ),
        )

        result = await executor.execute_run("run_semantic_teacher")

        assert result["status"] == "needs_evidence"
        assert result["results"]["teacher"]["job_id"] == "teacher_case_review_1"
        assert result["results"]["semantic_enrichment"]["stance"]["code"] == "blocked_missing_primary_claim"

    asyncio.run(scenario())


def test_semantic_artifact_hash_is_stable_for_identical_inputs(monkeypatch):
    snapshot = _snapshot()

    class SequenceDatetime(datetime):
        call_count = 0

        @classmethod
        def now(cls, tz=None):
            cls.call_count += 1
            return datetime(2026, 5, 14, 12, 0, cls.call_count, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(semantic_enrichment_module, "datetime", SequenceDatetime)

    first = semantic_enrichment_module.analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
        runtime=FakeSemanticRuntime(),
    )
    second = semantic_enrichment_module.analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
        runtime=FakeSemanticRuntime(),
    )

    assert first["generated_at"] != second["generated_at"]
    assert first["artifact_sha256"] == second["artifact_sha256"]


def test_semantic_decision_support_recommends_action_refs_without_changing_score_policy():
    snapshot = _snapshot()

    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "涓編鍏崇郴绋冲畾鍓嶈"},
        runtime=FakeSemanticRuntime(),
    )
    recommendations = semantic["decision_support"]["action_recommendations"]

    assert recommendations
    assert recommendations[0]["recommendation_id"] == "semantic_action_review_public_response"
    assert recommendations[0]["action_id"] == "action_review_public_response"
    assert recommendations[0]["status"] == "candidate_unvalidated"
    assert recommendations[0]["score_policy"] == "evidence_overlay_only"
    assert recommendations[0]["evidence_refs"] == [
        "semantic_case_workbench_demo",
        "claim_cctv_primary",
    ]
    assert recommendations[0]["does_not_modify"] == [
        "coordination_discover",
        "propagation_analysis",
        "student",
        "teacher",
    ]
    assert semantic["provenance"]["score_policy"] == "semantic_artifacts_are_evidence_overlay_only"


def test_semantic_runtime_is_required_and_does_not_rule_fallback():
    snapshot = _snapshot()

    try:
        analyze_semantic_enrichment_snapshot(
            snapshot,
            {"primary_claim_text": "中美关系稳定前行"},
        )
    except SemanticModelUnavailable as exc:
        assert exc.blocker["code"] == "semantic_model_unavailable"
        assert exc.blocker["cache_dir"] == r"G:\CISCN\hf_models"
        assert "degraded_rule_fallback" not in str(exc.blocker)
    else:
        raise AssertionError("semantic enrichment must fail closed when no real runtime is supplied")


def test_huggingface_runtime_uses_manual_local_snapshots_without_remote_revision(monkeypatch, tmp_path):
    cache_dir = tmp_path / "hf_models"
    local_root = cache_dir / "local_snapshots"
    model_pairs = [
        (semantic_enrichment_module.EMBEDDING_MODEL_ID, semantic_enrichment_module.EMBEDDING_MODEL_REVISION),
        (semantic_enrichment_module.SENTIMENT_MODEL_ID, semantic_enrichment_module.SENTIMENT_MODEL_REVISION),
        (semantic_enrichment_module.STANCE_MODEL_ID, semantic_enrichment_module.STANCE_MODEL_REVISION),
        (semantic_enrichment_module.NER_MODEL_ID, semantic_enrichment_module.NER_MODEL_REVISION),
    ]
    local_paths = {
        repo_id: local_root / f"{repo_id.replace('/', '__')}--{revision}" for repo_id, revision in model_pairs
    }
    for path in local_paths.values():
        path.mkdir(parents=True)

    sentence_calls: list[dict[str, Any]] = []
    pipeline_calls: list[dict[str, Any]] = []
    tokenizer_calls: list[dict[str, Any]] = []
    sequence_calls: list[dict[str, Any]] = []
    token_calls: list[dict[str, Any]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name_or_path, **kwargs):
            sentence_calls.append({"model": model_name_or_path, "kwargs": kwargs})

        def encode(self, *args, **kwargs):
            return []

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            tokenizer_calls.append({"model": model, "kwargs": kwargs})
            return f"tokenizer:{model}"

    class FakeSequenceModel:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            sequence_calls.append({"model": model, "kwargs": kwargs})
            return f"sequence:{model}"

    class FakeTokenModel:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            token_calls.append({"model": model, "kwargs": kwargs})
            return f"token:{model}"

    def fake_pipeline(task, **kwargs):
        pipeline_calls.append({"task": task, "kwargs": kwargs})
        return lambda *args, **pipe_kwargs: []

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            AutoModelForSequenceClassification=FakeSequenceModel,
            AutoModelForTokenClassification=FakeTokenModel,
            AutoTokenizer=FakeTokenizer,
            pipeline=fake_pipeline,
        ),
    )

    semantic_enrichment_module.HuggingFaceSemanticRuntime(cache_dir=str(cache_dir), device="cpu")

    assert sentence_calls[0]["model"] == str(local_paths[semantic_enrichment_module.EMBEDDING_MODEL_ID])
    assert "revision" not in sentence_calls[0]["kwargs"]
    loaded_models = {call["model"] for call in [*tokenizer_calls, *sequence_calls, *token_calls]}
    assert loaded_models == {
        str(local_paths[semantic_enrichment_module.SENTIMENT_MODEL_ID]),
        str(local_paths[semantic_enrichment_module.STANCE_MODEL_ID]),
        str(local_paths[semantic_enrichment_module.NER_MODEL_ID]),
    }
    assert all("revision" not in call["kwargs"] for call in [*tokenizer_calls, *sequence_calls, *token_calls])
    assert all(call["kwargs"]["local_files_only"] is True for call in [*tokenizer_calls, *sequence_calls, *token_calls])
    assert {call["task"] for call in pipeline_calls} == {
        "sentiment-analysis",
        "zero-shot-classification",
        "token-classification",
    }


def test_huggingface_runtime_loads_transformer_objects_without_pipeline_tokenizer_kwargs(monkeypatch, tmp_path):
    cache_dir = tmp_path / "hf_models"
    for repo_id, revision in [
        (semantic_enrichment_module.EMBEDDING_MODEL_ID, semantic_enrichment_module.EMBEDDING_MODEL_REVISION),
        (semantic_enrichment_module.SENTIMENT_MODEL_ID, semantic_enrichment_module.SENTIMENT_MODEL_REVISION),
        (semantic_enrichment_module.STANCE_MODEL_ID, semantic_enrichment_module.STANCE_MODEL_REVISION),
        (semantic_enrichment_module.NER_MODEL_ID, semantic_enrichment_module.NER_MODEL_REVISION),
    ]:
        (cache_dir / "local_snapshots" / f"{repo_id.replace('/', '__')}--{revision}").mkdir(parents=True)

    pipeline_calls: list[dict[str, Any]] = []
    tokenizer_calls: list[dict[str, Any]] = []
    sequence_calls: list[dict[str, Any]] = []
    token_calls: list[dict[str, Any]] = []

    class FakeSentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            tokenizer_calls.append({"model": model, "kwargs": kwargs})
            return f"tokenizer:{model}"

    class FakeSequenceModel:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            sequence_calls.append({"model": model, "kwargs": kwargs})
            return f"sequence:{model}"

    class FakeTokenModel:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            token_calls.append({"model": model, "kwargs": kwargs})
            return f"token:{model}"

    def fake_pipeline(task, **kwargs):
        pipeline_calls.append({"task": task, "kwargs": kwargs})
        if "tokenizer_kwargs" in kwargs:
            raise TypeError("pipeline should receive loaded tokenizer objects, not tokenizer_kwargs")
        return lambda *args, **pipe_kwargs: []

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            AutoModelForSequenceClassification=FakeSequenceModel,
            AutoModelForTokenClassification=FakeTokenModel,
            AutoTokenizer=FakeTokenizer,
            pipeline=fake_pipeline,
        ),
    )

    semantic_enrichment_module.HuggingFaceSemanticRuntime(cache_dir=str(cache_dir), device="cpu")

    assert len(pipeline_calls) == 3
    assert all("tokenizer_kwargs" not in call["kwargs"] for call in pipeline_calls)
    assert len(tokenizer_calls) == 3
    assert len(sequence_calls) == 2
    assert len(token_calls) == 1
    assert all(call["kwargs"]["local_files_only"] is True for call in tokenizer_calls)


def test_huggingface_runtime_entity_pipeline_does_not_receive_unsupported_truncation(monkeypatch, tmp_path):
    cache_dir = tmp_path / "hf_models"
    for repo_id, revision in [
        (semantic_enrichment_module.EMBEDDING_MODEL_ID, semantic_enrichment_module.EMBEDDING_MODEL_REVISION),
        (semantic_enrichment_module.SENTIMENT_MODEL_ID, semantic_enrichment_module.SENTIMENT_MODEL_REVISION),
        (semantic_enrichment_module.STANCE_MODEL_ID, semantic_enrichment_module.STANCE_MODEL_REVISION),
        (semantic_enrichment_module.NER_MODEL_ID, semantic_enrichment_module.NER_MODEL_REVISION),
    ]:
        (cache_dir / "local_snapshots" / f"{repo_id.replace('/', '__')}--{revision}").mkdir(parents=True)

    class FakeSentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return "tokenizer"

    class FakeSequenceModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return "sequence"

    class FakeTokenModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return "token"

    def fake_pipeline(task, **kwargs):
        if task == "token-classification":
            def ner_pipeline(_texts, **call_kwargs):
                assert "truncation" not in call_kwargs
                return [[{"word": "特朗普", "entity_group": "PER", "score": 0.99}]]

            return ner_pipeline
        return lambda *args, **pipe_kwargs: []

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            AutoModelForSequenceClassification=FakeSequenceModel,
            AutoModelForTokenClassification=FakeTokenModel,
            AutoTokenizer=FakeTokenizer,
            pipeline=fake_pipeline,
        ),
    )

    runtime = semantic_enrichment_module.HuggingFaceSemanticRuntime(cache_dir=str(cache_dir), device="cpu")

    assert runtime.extract_entities([{"text": "特朗普访华"}]) == [
        [{"entity": "特朗普", "entity_type": "person", "score": 0.99}]
    ]


def test_fake_lm_runtime_reuses_one_embedding_pass_for_all_semantic_modules():
    snapshot = _snapshot()
    runtime = FakeSemanticRuntime()

    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
        runtime=runtime,
    )

    assert runtime.encoded_texts == [row["text"] for row in semantic["layers"]["all_texts"]]
    assert semantic["runtime_status"] == "ok"
    assert semantic["runtime_backend"] == "fake_lm_encoder"
    assert semantic["model_version"] == semantic_enrichment_module.EMBEDDING_MODEL_VERSION
    assert semantic["provenance"]["embedding_reuse"] == "single_bge_pass_reused_by_semantic_modules"
    assert semantic["embedding_manifest"]["encoded_texts"] == 3
    assert semantic["embedding_manifest"]["embedding_model"] == semantic_enrichment_module.EMBEDDING_MODEL_VERSION
    assert semantic["keywords"]["main_posts"][0]["method"] == "keybert_mmr"
    assert semantic["topics"]["main_posts"]["method"] == "bertopic_lite_embedding_cluster_ctfidf"
    assert semantic["near_duplicates"]["main_posts"][0]["method"] == "embedding_cosine"
    assert semantic["layers"]["main_posts"]["sentiment"]["total_texts"] == 2
    assert semantic["layers"]["comments"]["sentiment"]["total_texts"] == 1
    assert semantic["stance"]["main_posts"]["status"] == "ok"
    assert semantic["stance"]["comments"]["status"] == "ok"
    assert semantic["cross_analysis"]["time_slices"]
    assert semantic["cross_analysis"]["platform_slices"]


def test_semantic_inference_reuses_one_real_runtime_pass_before_layer_aggregation():
    snapshot = _snapshot()
    runtime = FakeSemanticRuntime()

    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
        runtime=runtime,
    )

    assert runtime.sentiment_call_sizes == [3]
    assert runtime.stance_call_sizes == [3]
    assert runtime.entity_call_sizes == [3]
    assert semantic["sentiment"]["main_posts"]["total_texts"] == 2
    assert semantic["sentiment"]["comments"]["total_texts"] == 1
    assert semantic["stance"]["main_posts"]["status"] == "ok"
    assert semantic["stance"]["comments"]["status"] == "ok"


def test_community_comparison_prefers_coordination_community_ids():
    snapshot = _snapshot()
    snapshot.posts[0]["coordination_community_id"] = "community_alpha"
    snapshot.posts[1]["coordination_community_id"] = "community_beta"

    semantic = analyze_semantic_enrichment_snapshot(
        snapshot,
        {"primary_claim_text": "中美关系稳定前行"},
        runtime=FakeSemanticRuntime(),
    )

    comparison = semantic["community_comparison"]
    assert comparison["group_by"] == "coordination_community"
    assert {item["community_id"] for item in comparison["items"]} >= {"community_alpha", "community_beta"}


def test_propagation_path_overlay_refuses_unmatched_semantic_evidence():
    semantic = analyze_semantic_enrichment_snapshot(
        _snapshot(),
        {"primary_claim_text": "中美关系稳定前行"},
        runtime=FakeSemanticRuntime(),
    )

    overlay = propagation_path_overlay(
        {
            "evidence_refs": ["weibo:post:missing"],
            "edges": [
                {
                    "source_ref": "weibo:post:missing-source",
                    "target_ref": "weibo:comment:missing-target",
                    "evidence_ref": "weibo:comment:missing-target",
                }
            ],
        },
        semantic["_runtime_rows"],
        primary_claim_ref="claim_cctv_primary",
    )

    assert overlay["status"] == "unavailable_no_matched_evidence"
    assert overlay["evidence_refs"] == [
        "weibo:comment:missing-target",
        "weibo:post:missing",
        "weibo:post:missing-source",
    ]
    assert overlay["claim_refs"] == ["claim_cctv_primary"]
    assert "sentiment" not in overlay
    assert "stance" not in overlay
    assert "keywords" not in overlay
    assert "entities" not in overlay
    assert "evidence_examples" not in overlay
