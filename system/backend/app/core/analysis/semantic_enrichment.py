"""Model-backed semantic enrichment for case-oriented analysis runs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

from app.core.analysis.contracts import EventSnapshot

EMBEDDING_MODEL_VERSION = "BAAI/bge-small-zh-v1.5@7999e1d"
SENTIMENT_MODEL_VERSION = "lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110"
STANCE_MODEL_VERSION = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92"
NER_MODEL_VERSION = "shibing624/bert4ner-base-chinese@5d660ed"

EMBEDDING_MODEL_ID = EMBEDDING_MODEL_VERSION.split("@", 1)[0]
EMBEDDING_MODEL_REVISION = EMBEDDING_MODEL_VERSION.split("@", 1)[1]
SENTIMENT_MODEL_ID = SENTIMENT_MODEL_VERSION.split("@", 1)[0]
SENTIMENT_MODEL_REVISION = SENTIMENT_MODEL_VERSION.split("@", 1)[1]
STANCE_MODEL_ID = STANCE_MODEL_VERSION.split("@", 1)[0]
STANCE_MODEL_REVISION = STANCE_MODEL_VERSION.split("@", 1)[1]
NER_MODEL_ID = NER_MODEL_VERSION.split("@", 1)[0]
NER_MODEL_REVISION = NER_MODEL_VERSION.split("@", 1)[1]

MODEL_STATUS = "candidate_unvalidated"
TECHNOLOGY = "semantic_enrichment"
HF_CACHE_DIR = r"G:\CISCN\hf_models"
TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_]{1,}")
STOP_TERMS = {
    "一个",
    "一些",
    "我们",
    "他们",
    "这个",
    "那个",
    "进行",
    "相关",
    "大量",
    "网友",
}
DOES_NOT_MODIFY = [
    "coordination_discover",
    "propagation_analysis",
    "student",
    "teacher",
]


class SemanticModelUnavailable(RuntimeError):
    """Raised when required model bytes or inference dependencies are unavailable."""

    def __init__(self, message: str, *, missing: list[str] | None = None) -> None:
        self.blocker = {
            "code": "semantic_model_unavailable",
            "message": message,
            "missing_models": list(missing or []),
            "cache_dir": HF_CACHE_DIR,
            "manual_resolution": (
                "Run system/backend/scripts/prefetch_semantic_models.py, or manually snapshot_download "
                "the listed HuggingFace revisions into G:\\CISCN\\hf_models, then retry."
            ),
        }
        super().__init__(message)


class SemanticRuntime(Protocol):
    runtime_backend: str
    cache_dir: str
    device: str
    model_versions: dict[str, str]

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def classify_sentiment(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

    def classify_stance(self, rows: list[dict[str, Any]], primary_claim: str) -> list[dict[str, Any]]:
        ...

    def extract_entities(self, rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        ...


def _local_snapshot_dir(repo_id: str, revision: str, cache_dir: str = HF_CACHE_DIR) -> Path:
    return Path(cache_dir) / "local_snapshots" / f"{repo_id.replace('/', '__')}--{revision}"


def _model_source(repo_id: str, revision: str, cache_dir: str = HF_CACHE_DIR) -> tuple[str, str | None, bool]:
    local_snapshot = _local_snapshot_dir(repo_id, revision, cache_dir)
    if local_snapshot.exists():
        return str(local_snapshot), None, True
    return repo_id, revision, False


def _from_pretrained_kwargs(
    *,
    revision: str | None,
    cache_dir: str,
    local_files_only: bool,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"cache_dir": cache_dir}
    if local_files_only:
        kwargs["local_files_only"] = True
    if revision is not None:
        kwargs["revision"] = revision
    return kwargs


class HuggingFaceSemanticRuntime:
    """Real local HuggingFace-backed runtime.

    This runtime fails closed. It does not fall back to lexical rules when model
    loading or inference fails.
    """

    runtime_backend = "huggingface_lm_encoder"
    cache_dir = HF_CACHE_DIR

    def __init__(self, *, cache_dir: str = HF_CACHE_DIR, device: str | None = None) -> None:
        self.cache_dir = cache_dir
        self.device = device or _default_device()
        self.model_versions = {
            "embedding": EMBEDDING_MODEL_VERSION,
            "sentiment": SENTIMENT_MODEL_VERSION,
            "stance": STANCE_MODEL_VERSION,
            "ner": NER_MODEL_VERSION,
        }
        try:
            from sentence_transformers import SentenceTransformer
            from transformers import (
                AutoModelForSequenceClassification,
                AutoModelForTokenClassification,
                AutoTokenizer,
                pipeline,
            )
        except Exception as exc:  # pragma: no cover - depends on local installation
            raise SemanticModelUnavailable(
                f"Semantic model dependencies are unavailable: {exc}",
                missing=["sentence-transformers", "transformers"],
            ) from exc

        try:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            embedding_model, embedding_revision, embedding_is_local = _model_source(
                EMBEDDING_MODEL_ID,
                EMBEDDING_MODEL_REVISION,
                cache_dir,
            )
            sentiment_model, sentiment_revision, sentiment_is_local = _model_source(
                SENTIMENT_MODEL_ID,
                SENTIMENT_MODEL_REVISION,
                cache_dir,
            )
            stance_model, stance_revision, stance_is_local = _model_source(
                STANCE_MODEL_ID,
                STANCE_MODEL_REVISION,
                cache_dir,
            )
            ner_model, ner_revision, ner_is_local = _model_source(
                NER_MODEL_ID,
                NER_MODEL_REVISION,
                cache_dir,
            )
            embedding_kwargs: dict[str, Any] = {
                "cache_folder": cache_dir,
                "device": self.device,
            }
            if embedding_revision is not None:
                embedding_kwargs["revision"] = embedding_revision
            self.embedding_model = SentenceTransformer(
                embedding_model,
                **embedding_kwargs,
            )
            device_index = 0 if self.device.startswith("cuda") else -1
            sentiment_load_kwargs = _from_pretrained_kwargs(
                revision=sentiment_revision,
                cache_dir=cache_dir,
                local_files_only=sentiment_is_local,
            )
            sentiment_tokenizer = AutoTokenizer.from_pretrained(sentiment_model, **sentiment_load_kwargs)
            sentiment_classifier = AutoModelForSequenceClassification.from_pretrained(
                sentiment_model,
                **sentiment_load_kwargs,
            )
            self.sentiment_pipe = pipeline(
                "sentiment-analysis",
                model=sentiment_classifier,
                tokenizer=sentiment_tokenizer,
                device=device_index,
            )
            stance_load_kwargs = _from_pretrained_kwargs(
                revision=stance_revision,
                cache_dir=cache_dir,
                local_files_only=stance_is_local,
            )
            stance_tokenizer = AutoTokenizer.from_pretrained(stance_model, **stance_load_kwargs)
            stance_classifier = AutoModelForSequenceClassification.from_pretrained(
                stance_model,
                **stance_load_kwargs,
            )
            self.stance_pipe = pipeline(
                "zero-shot-classification",
                model=stance_classifier,
                tokenizer=stance_tokenizer,
                device=device_index,
            )
            ner_load_kwargs = _from_pretrained_kwargs(
                revision=ner_revision,
                cache_dir=cache_dir,
                local_files_only=ner_is_local,
            )
            ner_tokenizer = AutoTokenizer.from_pretrained(ner_model, **ner_load_kwargs)
            ner_classifier = AutoModelForTokenClassification.from_pretrained(ner_model, **ner_load_kwargs)
            self.ner_pipe = pipeline(
                "token-classification",
                model=ner_classifier,
                tokenizer=ner_tokenizer,
                aggregation_strategy="simple",
                device=device_index,
            )
        except Exception as exc:  # pragma: no cover - depends on model bytes/network
            raise SemanticModelUnavailable(
                f"Required semantic model weights could not be loaded: {exc}",
                missing=list(self.model_versions.values()),
            ) from exc

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self.embedding_model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def classify_sentiment(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        outputs = self.sentiment_pipe(
            [row["text"] for row in rows],
            truncation=True,
            batch_size=32,
        )
        return [_normalize_label_score(item) for item in outputs]

    def classify_stance(self, rows: list[dict[str, Any]], primary_claim: str) -> list[dict[str, Any]]:
        if not rows:
            return []
        candidate_labels = ["support", "neutral", "deny"]
        outputs = self.stance_pipe(
            [row["text"] for row in rows],
            candidate_labels=candidate_labels,
            hypothesis_template=f"This text is {{}} of the claim: {primary_claim}",
            truncation=True,
            batch_size=16,
        )
        normalized = []
        for output in outputs if isinstance(outputs, list) else [outputs]:
            labels = list(output.get("labels") or [])
            scores = list(output.get("scores") or [])
            label = labels[0] if labels else "neutral"
            score = float(scores[0]) if scores else 0.0
            normalized.append({"label": _stance_label(label), "score": round(score, 4)})
        return normalized

    def extract_entities(self, rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        if not rows:
            return []
        outputs = self.ner_pipe([row["text"] for row in rows], batch_size=32)
        if rows and outputs and isinstance(outputs[0], dict):
            outputs = [outputs]
        return [
            [
                {
                    "entity": str(item.get("word") or item.get("entity_group") or "").strip(),
                    "entity_type": _entity_type(str(item.get("entity_group") or item.get("entity") or "named_entity")),
                    "score": round(float(item.get("score") or 0.0), 4),
                }
                for item in row_output
                if str(item.get("word") or "").strip()
            ]
            for row_output in outputs
        ]


class SemanticEnrichmentEngine:
    """Semantic engine used by AnalysisExecutor."""

    def __init__(self, runtime: SemanticRuntime | None = None) -> None:
        self.runtime = runtime

    async def analyze(self, snapshot: EventSnapshot, options: dict[str, Any]) -> dict[str, Any]:
        runtime = self.runtime or HuggingFaceSemanticRuntime()
        return analyze_semantic_enrichment_snapshot(snapshot, options, runtime=runtime)


def semantic_model_blocker(exc: SemanticModelUnavailable | Exception) -> dict[str, Any]:
    if isinstance(exc, SemanticModelUnavailable):
        return _semantic_blocker(dict(exc.blocker))
    return {
        **_semantic_blocker(
            {
                "code": "semantic_model_unavailable",
                "message": str(exc),
                "missing_models": [
                    EMBEDDING_MODEL_VERSION,
                    SENTIMENT_MODEL_VERSION,
                    STANCE_MODEL_VERSION,
                    NER_MODEL_VERSION,
                ],
                "cache_dir": HF_CACHE_DIR,
                "manual_resolution": (
                    "Run system/backend/scripts/prefetch_semantic_models.py, or manually snapshot_download "
                    "the listed HuggingFace revisions into G:\\CISCN\\hf_models, then retry."
                ),
            }
        )
    }


def _semantic_blocker(blocker: dict[str, Any]) -> dict[str, Any]:
    return {
        "blocker_id": "blocker_semantic_model_unavailable",
        "scope": "semantic_enrichment",
        "operation": "semantic_enrichment",
        "severity": "blocking",
        "missing_platforms": [],
        **blocker,
    }


def blocked_semantic_artifact(snapshot: EventSnapshot, exc: SemanticModelUnavailable | Exception) -> dict[str, Any]:
    blocker = semantic_model_blocker(exc)
    payload = {
        "schema_version": "cogguard.semantic_enrichment.v2",
        "technology": TECHNOLOGY,
        "status": "blocked",
        "runtime_status": "blocked",
        "runtime_backend": "unavailable",
        "model_status": "model_unavailable",
        "model_version": EMBEDDING_MODEL_VERSION,
        "model_versions": _model_versions(),
        "candidate_models": _model_versions(),
        "validation_status": MODEL_STATUS,
        "snapshot_id": snapshot.snapshot_id,
        "event_id": snapshot.event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "platforms": list(snapshot.platforms),
            "main_posts": len(snapshot.posts),
            "comments": len(snapshot.comments),
            "total_texts": len(snapshot.posts) + len(snapshot.comments),
        },
        "semantic_blocker": blocker,
        "active_blockers": [blocker],
        "sentiment": _empty_layers(),
        "keywords": {"main_posts": [], "comments": []},
        "topics": {"main_posts": _empty_topics(), "comments": _empty_topics()},
        "entities": {"main_posts": [], "comments": []},
        "stance": {
            "status": "blocked",
            "code": blocker["code"],
            "message": blocker["message"],
        },
        "near_duplicates": {"main_posts": [], "comments": []},
        "community_comparison": {"group_by": "unavailable", "status": "blocked", "items": []},
        "cross_analysis": {
            "time_slices": [],
            "platform_slices": [],
            "community_slices": [],
            "propagation_path_overlays": [],
        },
        "decision_support": _blocked_decision_support(blocker),
        "layers": {
            "main_posts": {},
            "comments": {},
            "all_texts": [],
        },
        "embedding_manifest": {
            "status": "blocked",
            "embedding_model": EMBEDDING_MODEL_VERSION,
            "encoded_texts": 0,
            "cache_dir": HF_CACHE_DIR,
        },
        "provenance": {
            "embedding_reuse": "blocked_no_successful_embedding_pass",
            "device": "unavailable",
            "score_policy": "semantic_artifacts_are_evidence_overlay_only",
            "does_not_modify": DOES_NOT_MODIFY,
            "manual_resolution": blocker["manual_resolution"],
        },
        "claimability": "non_claimable",
    }
    refresh_semantic_artifact_hash(payload)
    return payload


def analyze_semantic_enrichment_snapshot(
    snapshot: EventSnapshot,
    options: dict[str, Any] | None = None,
    *,
    runtime: SemanticRuntime | None = None,
) -> dict[str, Any]:
    """Return case-facing semantic artifacts without changing core risk scores.

    A model runtime is required. This function intentionally fails closed
    instead of silently falling back to lexical rules.
    """

    if runtime is None:
        raise SemanticModelUnavailable(
            "Semantic enrichment requires the configured HuggingFace model runtime; no rule fallback is allowed.",
            missing=[
                EMBEDDING_MODEL_VERSION,
                SENTIMENT_MODEL_VERSION,
                STANCE_MODEL_VERSION,
                NER_MODEL_VERSION,
            ],
        )

    options = dict(options or {})
    primary_claim = _primary_claim_text(options)
    main_posts = _content_rows(snapshot.posts, content_kind="main_post")
    comments = _content_rows(snapshot.comments, content_kind="comment")
    all_rows = [*main_posts, *comments]
    embeddings = _encode_once(runtime, all_rows)
    _attach_embeddings(all_rows, embeddings)

    _attach_sentiment_predictions(all_rows, runtime=runtime)
    sentiment = {
        "summary": _sentiment_summary(all_rows),
        "main_posts": _sentiment_summary(main_posts),
        "comments": _sentiment_summary(comments),
    }
    keywords = {
        "main_posts": _keywords(main_posts),
        "comments": _keywords(comments),
    }
    topics = {
        "main_posts": _topics(main_posts),
        "comments": _topics(comments),
    }
    _attach_entity_predictions(all_rows, runtime=runtime)
    entities = {
        "main_posts": _entities(main_posts),
        "comments": _entities(comments),
    }
    near_duplicates = {
        "main_posts": _near_duplicates(main_posts),
        "comments": _near_duplicates(comments),
    }
    community_comparison = _community_comparison(main_posts, comments)
    stance = _stance(all_rows, primary_claim, runtime=runtime)
    cross_analysis = {
        "time_slices": _time_slices(all_rows),
        "platform_slices": _platform_slices(all_rows),
        "community_slices": community_comparison.get("items", []),
        "propagation_path_overlays": [],
    }
    decision_support = _decision_support(
        rows=all_rows,
        sentiment=sentiment,
        keywords=keywords,
        topics=topics,
        entities=entities,
        stance=stance,
        near_duplicates=near_duplicates,
        community_comparison=community_comparison,
        primary_claim_ref="claim_cctv_primary" if primary_claim else None,
    )
    status = "partial" if stance.get("status") == "blocked" else "ok"

    payload = {
        "schema_version": "cogguard.semantic_enrichment.v2",
        "technology": TECHNOLOGY,
        "status": status,
        "runtime_status": "ok",
        "runtime_backend": str(runtime.runtime_backend),
        "model_status": MODEL_STATUS,
        "model_version": EMBEDDING_MODEL_VERSION,
        "model_versions": dict(runtime.model_versions),
        "candidate_models": dict(runtime.model_versions),
        "validation_status": MODEL_STATUS,
        "snapshot_id": snapshot.snapshot_id,
        "event_id": snapshot.event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "platforms": list(snapshot.platforms),
            "main_posts": len(main_posts),
            "comments": len(comments),
            "total_texts": len(all_rows),
        },
        "sentiment": sentiment,
        "keywords": keywords,
        "topics": topics,
        "entities": entities,
        "stance": stance,
        "near_duplicates": near_duplicates,
        "community_comparison": community_comparison,
        "cross_analysis": cross_analysis,
        "decision_support": decision_support,
        "layers": {
            "main_posts": {
                "sentiment": sentiment["main_posts"],
                "keywords": keywords["main_posts"],
                "topics": topics["main_posts"],
                "entities": entities["main_posts"],
                "stance": stance.get("main_posts"),
                "near_duplicates": near_duplicates["main_posts"],
            },
            "comments": {
                "sentiment": sentiment["comments"],
                "keywords": keywords["comments"],
                "topics": topics["comments"],
                "entities": entities["comments"],
                "stance": stance.get("comments"),
                "near_duplicates": near_duplicates["comments"],
            },
            "all_texts": [_row_manifest(row) for row in all_rows],
        },
        "embedding_manifest": {
            "status": "ok",
            "embedding_model": dict(runtime.model_versions).get("embedding", EMBEDDING_MODEL_VERSION),
            "encoded_texts": len(all_rows),
            "content_hashes": [row["content_hash"] for row in all_rows],
            "cache_dir": str(runtime.cache_dir),
            "reuse_policy": "single_encode_pass",
        },
        "provenance": {
            "embedding_reuse": "single_bge_pass_reused_by_semantic_modules",
            "device": str(runtime.device),
            "cache_dir": str(runtime.cache_dir),
            "score_policy": "semantic_artifacts_are_evidence_overlay_only",
            "does_not_modify": DOES_NOT_MODIFY,
        },
        "claimability": "non_claimable",
    }
    refresh_semantic_artifact_hash(payload)
    payload["_runtime_rows"] = all_rows
    return payload


def _content_rows(rows: Iterable[dict[str, Any]], *, content_kind: str) -> list[dict[str, Any]]:
    normalized = []
    id_key = "post_id" if content_kind == "main_post" else "comment_id"
    for row in rows:
        text = _text(row.get("content") or row.get("text") or row.get("title") or "")
        if not text:
            continue
        content_id = str(row.get(id_key) or row.get("post_id") or "").strip()
        normalized.append(
            {
                "content_id": content_id,
                "content_kind": content_kind,
                "post_id": str(row.get("post_id") or "").strip(),
                "author_id": str(row.get("author_id") or "").strip(),
                "author_name": str(row.get("author_name") or row.get("nickname") or row.get("author_id") or "").strip(),
                "platform": str(row.get("platform") or "unknown").strip(),
                "timestamp": str(row.get("timestamp") or row.get("created_at") or ""),
                "text": text,
                "tokens": _tokens(text),
                "coordination_community_id": _coordination_community_id(row),
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return normalized


def _encode_once(runtime: SemanticRuntime, rows: list[dict[str, Any]]) -> list[list[float]]:
    texts = [row["text"] for row in rows]
    try:
        embeddings = runtime.encode_texts(texts)
    except SemanticModelUnavailable:
        raise
    except Exception as exc:
        raise SemanticModelUnavailable(
            f"Semantic embedding inference failed: {exc}",
            missing=[EMBEDDING_MODEL_VERSION],
        ) from exc
    if len(embeddings) != len(rows):
        raise SemanticModelUnavailable(
            "Semantic embedding runtime returned a vector count that does not match input texts.",
            missing=[EMBEDDING_MODEL_VERSION],
        )
    return [_normalize_vector(vector) for vector in embeddings]


def _attach_embeddings(rows: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
    for row, embedding in zip(rows, embeddings, strict=True):
        row["embedding"] = embedding


def _attach_sentiment_predictions(rows: list[dict[str, Any]], *, runtime: SemanticRuntime) -> None:
    predictions = runtime.classify_sentiment(rows)
    if len(predictions) != len(rows):
        raise SemanticModelUnavailable("Sentiment runtime returned a prediction count that does not match input texts.")
    for row, prediction in zip(rows, predictions, strict=True):
        row["sentiment_label"] = _sentiment_label(str(prediction.get("label") or "neutral"))
        row["sentiment_score"] = round(float(prediction.get("score") or 0.0), 4)


def _sentiment_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {"positive": [], "negative": [], "neutral": []}
    score_total = 0.0
    for row in rows:
        label = str(row.get("sentiment_label") or "neutral")
        score = float(row.get("sentiment_score") or 0.0)
        counts[label] += 1
        score_total += score
        if len(examples[label]) < 3:
            examples[label].append(_example(row, score=score))
    total = len(rows)
    return {
        "total_texts": total,
        "distribution": {key: counts.get(key, 0) for key in ("positive", "neutral", "negative")},
        "average_score": round(score_total / total, 4) if total else 0.0,
        "examples": examples,
        "method": "transformers_text_classification",
        "model_version": SENTIMENT_MODEL_VERSION,
    }


def _keywords(rows: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    if not rows:
        return []
    try:
        import numpy as np
    except Exception:  # pragma: no cover - numpy is a SentenceTransformers dependency
        np = None
    document_embedding = _mean_embedding([row["embedding"] for row in rows])
    candidate_counts: Counter[str] = Counter()
    candidate_docs: Counter[str] = Counter()
    candidate_examples: dict[str, str] = {}
    term_embedding_sums: dict[str, Any] = {}
    term_embedding_counts: Counter[str] = Counter()
    for row in rows:
        candidates = [token for token in row["tokens"] if token not in STOP_TERMS and len(token) >= 2]
        candidate_counts.update(candidates)
        unique_candidates = set(candidates)
        candidate_docs.update(unique_candidates)
        for term in unique_candidates:
            candidate_examples.setdefault(term, row["text"][:120])
            if np is None:
                continue
            if term not in term_embedding_sums:
                term_embedding_sums[term] = np.asarray(row["embedding"], dtype=float)
            else:
                term_embedding_sums[term] += np.asarray(row["embedding"], dtype=float)
            term_embedding_counts[term] += 1
    scored = []
    for term, count in candidate_counts.items():
        if np is None:
            term_embedding = _term_embedding(term, rows)
        else:
            term_embedding = (term_embedding_sums[term] / term_embedding_counts[term]).tolist()
        relevance = _cosine(document_embedding, term_embedding)
        idf = math.log((1 + len(rows)) / (1 + candidate_docs[term])) + 1
        scored.append(
            {
                "term": term,
                "score": round(max(relevance, 0.0) * float(count) * idf, 4),
                "count": int(count),
                "document_count": int(candidate_docs[term]),
                "method": "keybert_mmr",
                "example": candidate_examples.get(term, ""),
                "_embedding": term_embedding,
            }
        )
    selected = _mmr_select(scored, limit=limit)
    for item in selected:
        item.pop("_embedding", None)
    return selected


def _topics(rows: list[dict[str, Any]], *, limit: int = 6) -> dict[str, Any]:
    if not rows:
        return _empty_topics(method="bertopic_lite_embedding_cluster_ctfidf")
    grouped = _cluster_rows(rows, limit=limit)
    topics = []
    for index, members in enumerate(sorted(grouped, key=len, reverse=True)[:limit], 1):
        keywords = _ctfidf_keywords(members, rows, limit=5)
        topics.append(
            {
                "topic_id": f"topic_{index}",
                "label": keywords[0] if keywords else "general_discussion",
                "size": len(members),
                "keywords": keywords,
                "representative_text": members[0]["text"][:160],
            }
        )
    return {
        "topic_count": len(topics),
        "method": "bertopic_lite_embedding_cluster_ctfidf",
        "items": topics,
    }


def _attach_entity_predictions(rows: list[dict[str, Any]], *, runtime: SemanticRuntime) -> None:
    outputs = runtime.extract_entities(rows)
    if len(outputs) != len(rows):
        raise SemanticModelUnavailable("NER runtime returned a prediction count that does not match input texts.")
    for row, row_entities in zip(rows, outputs, strict=True):
        row["entity_predictions"] = [
            {
                "entity": str(item.get("entity") or "").strip(),
                "entity_type": _entity_type(str(item.get("entity_type") or item.get("entity_group") or "named_entity")),
                "score": round(float(item.get("score") or 0.0), 4),
            }
            for item in row_entities
            if str(item.get("entity") or "").strip()
        ]


def _entities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    platforms: dict[tuple[str, str], set[str]] = defaultdict(set)
    scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        row_entities = row.get("entity_predictions") or []
        row_entity_names: list[str] = []
        for item in row_entities:
            entity = str(item.get("entity") or "").strip()
            if not entity:
                continue
            entity_type = _entity_type(str(item.get("entity_type") or item.get("entity_group") or "named_entity"))
            row_entity_names.append(entity)
            key = (entity, entity_type)
            counts[key] += 1
            platforms[key].add(row["platform"])
            scores[key].append(float(item.get("score") or 0.0))
        row["entity_names"] = row_entity_names
    return [
        {
            "entity": entity,
            "count": int(count),
            "platforms": sorted(platforms[(entity, entity_type)]),
            "entity_type": entity_type,
            "score": round(sum(scores[(entity, entity_type)]) / max(len(scores[(entity, entity_type)]), 1), 4),
            "method": "transformers_token_classification",
        }
        for (entity, entity_type), count in counts.most_common(20)
    ]


def _stance(rows: list[dict[str, Any]], primary_claim: str | None, *, runtime: SemanticRuntime) -> dict[str, Any]:
    if not primary_claim:
        blocked = {
            "status": "blocked",
            "code": "blocked_missing_primary_claim",
            "message": "Stance requires an approved Primary Claim; other semantic artifacts remain available.",
        }
        return {**blocked, "main_posts": blocked, "comments": blocked}
    _attach_stance_predictions(rows, runtime=runtime, primary_claim=primary_claim)
    all_summary = _stance_summary(rows)
    main_posts = _stance_summary([row for row in rows if row["content_kind"] == "main_post"])
    comments = _stance_summary([row for row in rows if row["content_kind"] == "comment"])
    return {
        "status": "ok",
        "primary_claim_hash": hashlib.sha256(primary_claim.encode("utf-8")).hexdigest(),
        "distribution": all_summary["distribution"],
        "examples": all_summary["examples"],
        "method": "transformers_nli",
        "model_version": STANCE_MODEL_VERSION,
        "main_posts": main_posts,
        "comments": comments,
    }


def _attach_stance_predictions(rows: list[dict[str, Any]], *, runtime: SemanticRuntime, primary_claim: str) -> None:
    predictions = runtime.classify_stance(rows, primary_claim)
    if len(predictions) != len(rows):
        raise SemanticModelUnavailable("Stance runtime returned a prediction count that does not match input texts.")
    for row, prediction in zip(rows, predictions, strict=True):
        row["stance_label"] = _stance_label(str(prediction.get("label") or "neutral"))
        row["stance_score"] = round(float(prediction.get("score") or 0.0), 4)


def _stance_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    distribution: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for row in rows:
        label = str(row.get("stance_label") or "neutral")
        score = float(row.get("stance_score") or 0.0)
        distribution[label] += 1
        if len(examples) < 5:
            examples.append({**_example(row, score=score), "stance": label})
    return {
        "status": "ok",
        "distribution": dict(distribution),
        "examples": examples,
        "method": "transformers_nli",
    }


def _near_duplicates(rows: list[dict[str, Any]], *, threshold: float = 0.88) -> list[dict[str, Any]]:
    if len(rows) < 2:
        return []
    try:
        import numpy as np
    except Exception:  # pragma: no cover - numpy is a SentenceTransformers dependency
        np = None
    if np is not None:
        vectors = np.asarray([row["embedding"] for row in rows], dtype=float)
        groups: list[list[dict[str, Any]]] = []
        used: set[int] = set()
        block_size = 128
        for block_start in range(0, len(rows), block_size):
            block_end = min(block_start + block_size, len(rows))
            similarities = vectors[block_start:block_end] @ vectors.T
            for offset, index in enumerate(range(block_start, block_end)):
                if index in used:
                    continue
                candidate_indexes = np.flatnonzero(similarities[offset, index + 1 :] >= threshold) + index + 1
                members = [rows[index]]
                used.add(index)
                for candidate_index in candidate_indexes.tolist():
                    if candidate_index not in used:
                        members.append(rows[candidate_index])
                        used.add(candidate_index)
                if len(members) > 1:
                    groups.append(members)
        return [
            {
                "group_id": f"near_duplicate_{index}",
                "size": len(members),
                "content_ids": [member["content_id"] for member in members],
                "representative_text": members[0]["text"][:160],
                "method": "embedding_cosine",
                "threshold": threshold,
            }
            for index, members in enumerate(groups[:20], 1)
        ]
    groups: list[list[dict[str, Any]]] = []
    used: set[int] = set()
    for index, row in enumerate(rows):
        if index in used:
            continue
        group = [row]
        used.add(index)
        for other_index, other in enumerate(rows[index + 1 :], start=index + 1):
            if other_index in used:
                continue
            if _cosine(row["embedding"], other["embedding"]) >= threshold:
                group.append(other)
                used.add(other_index)
        if len(group) > 1:
            groups.append(group)
    return [
        {
            "group_id": f"near_duplicate_{index}",
            "size": len(members),
            "content_ids": [member["content_id"] for member in members],
            "representative_text": members[0]["text"][:160],
            "method": "embedding_cosine",
            "threshold": threshold,
        }
        for index, members in enumerate(groups[:20], 1)
    ]


def _community_comparison(main_posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [*main_posts, *comments]
    community_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        community_id = str(row.get("coordination_community_id") or "").strip()
        if community_id:
            community_rows[community_id].append(row)
    if community_rows:
        return {
            "group_by": "coordination_community",
            "items": _community_items(community_rows),
        }
    return {
        "group_by": "coordination_community",
        "status": "unavailable_missing_coordination_community",
        "items": [],
        "message": "Coordination community ids were not present; no platform fallback is used.",
    }


def _community_items(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {
            "community_id": community,
            "texts": len(rows),
            "top_keywords": [item["term"] for item in _keywords(rows, limit=5)],
            "sentiment": _distribution_from_rows(rows, "sentiment_label"),
            "platforms": sorted({row["platform"] for row in rows}),
            "method": "coordination_community_embedding_overlay",
        }
        for community, rows in sorted(grouped.items())
    ]


def _decision_support(
    *,
    rows: list[dict[str, Any]],
    sentiment: dict[str, Any],
    keywords: dict[str, Any],
    topics: dict[str, Any],
    entities: dict[str, Any],
    stance: dict[str, Any],
    near_duplicates: dict[str, Any],
    community_comparison: dict[str, Any],
    primary_claim_ref: str | None,
) -> dict[str, Any]:
    total_texts = len(rows)
    covered_texts = len([row for row in rows if row.get("text")])
    coverage_ratio = round(covered_texts / total_texts, 4) if total_texts else 0.0
    stance_available = stance.get("status") == "ok"
    module_coverage = {
        "sentiment": _module_status(sentiment["summary"]["total_texts"], total_texts),
        "keywords": _module_status(len(keywords["main_posts"]) + len(keywords["comments"]), total_texts),
        "topics": _module_status(
            topics["main_posts"]["topic_count"] + topics["comments"]["topic_count"],
            total_texts,
        ),
        "entities": _module_status(len(entities["main_posts"]) + len(entities["comments"]), total_texts),
        "stance": {
            "status": "available" if stance_available else "blocked",
            "covered": covered_texts if stance_available else 0,
            "total": total_texts,
            "block_code": None if stance_available else stance.get("code"),
        },
        "near_duplicates": _module_status(
            len(near_duplicates["main_posts"]) + len(near_duplicates["comments"]),
            total_texts,
            allow_empty_available=True,
        ),
        "community_comparison": (
            _module_status(len(community_comparison["items"]), total_texts)
            if community_comparison.get("items")
            else {"status": "unavailable", "covered": 0, "total": total_texts, "block_code": community_comparison.get("status")}
        ),
    }
    confidence_score = _semantic_confidence_score(
        total_texts=total_texts,
        coverage_ratio=coverage_ratio,
        stance_available=stance_available,
        platform_count=len({row["platform"] for row in rows}),
    )
    return {
        "coverage": {
            "total_texts": total_texts,
            "covered_texts": covered_texts,
            "coverage_ratio": coverage_ratio,
            "main_posts": sentiment["main_posts"]["total_texts"],
            "comments": sentiment["comments"]["total_texts"],
        },
        "confidence": {
            "status": MODEL_STATUS,
            "level": _confidence_level(confidence_score),
            "score": confidence_score,
            "basis": "real model inference coverage, stance availability, and platform diversity",
        },
        "module_coverage": module_coverage,
        "platform_slices": _platform_slices(rows),
        "time_slices": _time_slices(rows),
        "review_hints": _review_hints(
            sentiment=sentiment,
            stance=stance,
            near_duplicates=near_duplicates,
            community_comparison=community_comparison,
        ),
        "action_recommendations": _action_recommendations(
            rows=rows,
            sentiment=sentiment,
            stance=stance,
            near_duplicates=near_duplicates,
            community_comparison=community_comparison,
            primary_claim_ref=primary_claim_ref,
        ),
        "operator_prompt": "Use semantic outputs as triage hints, not as risk-score inputs.",
    }


def _blocked_decision_support(blocker: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage": {"total_texts": 0, "covered_texts": 0, "coverage_ratio": 0.0, "main_posts": 0, "comments": 0},
        "confidence": {"status": "blocked", "level": "blocked", "score": 0.0, "basis": blocker["code"]},
        "module_coverage": {
            module: {"status": "blocked", "covered": 0, "total": 0, "block_code": blocker["code"]}
            for module in ("sentiment", "keywords", "topics", "entities", "stance", "near_duplicates", "community_comparison")
        },
        "platform_slices": [],
        "time_slices": [],
        "review_hints": [blocker["message"]],
        "action_recommendations": [],
        "operator_prompt": "Semantic models are unavailable; pull required weights before review.",
    }


def _module_status(count: int, total_texts: int, *, allow_empty_available: bool = False) -> dict[str, Any]:
    if count > 0 or (allow_empty_available and total_texts > 0):
        status = "available"
    elif total_texts:
        status = "empty"
    else:
        status = "missing_input"
    return {"status": status, "covered": min(count, total_texts), "total": total_texts}


def _semantic_confidence_score(*, total_texts: int, coverage_ratio: float, stance_available: bool, platform_count: int) -> float:
    if total_texts <= 0:
        return 0.0
    score = 0.35 + 0.35 * coverage_ratio
    if stance_available:
        score += 0.15
    if platform_count > 1:
        score += 0.1
    return round(min(score, 0.95), 4)


def _confidence_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _platform_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    platform_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        platform_rows[row["platform"]].append(row)
    return [
        {
            "platform": platform,
            "texts": len(members),
            "top_keywords": [item["term"] for item in _keywords(members, limit=5)],
            "sentiment": _distribution_from_rows(members, "sentiment_label"),
        }
        for platform, members in sorted(platform_rows.items())
    ]


def _time_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_date_slice(row.get("timestamp"))].append(row)
    return [
        {
            "time": time_key,
            "texts": len(members),
            "sentiment": _distribution_from_rows(members, "sentiment_label"),
            "top_keywords": [item["term"] for item in _keywords(members, limit=5)],
        }
        for time_key, members in sorted(grouped.items())
    ]


def _date_slice(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return "unknown_time"


def _review_hints(
    *,
    sentiment: dict[str, Any],
    stance: dict[str, Any],
    near_duplicates: dict[str, Any],
    community_comparison: dict[str, Any],
) -> list[str]:
    hints = ["Keep semantic evidence advisory until local calibration passes."]
    distribution = sentiment["summary"]["distribution"]
    if distribution.get("negative", 0) > distribution.get("positive", 0):
        hints.append("Review negative sentiment examples before public-response action.")
    if stance.get("status") == "blocked":
        hints.append("Approve a Primary Claim before using stance as a review hint.")
    if near_duplicates["main_posts"] or near_duplicates["comments"]:
        hints.append("Inspect near-duplicate groups for templated amplification.")
    if not community_comparison.get("items"):
        hints.append("Coordination community ids are unavailable; run Coordination Discover before community comparison.")
    return hints


def _action_recommendations(
    *,
    rows: list[dict[str, Any]],
    sentiment: dict[str, Any],
    stance: dict[str, Any],
    near_duplicates: dict[str, Any],
    community_comparison: dict[str, Any],
    primary_claim_ref: str | None,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    evidence_refs = ["semantic_case_workbench_demo"]
    if primary_claim_ref:
        evidence_refs.append(primary_claim_ref)
    recommendation = {
        "recommendation_id": "semantic_action_review_public_response",
        "action_id": "action_review_public_response",
        "label": "Review public response posture",
        "status": MODEL_STATUS,
        "score_policy": "evidence_overlay_only",
        "evidence_refs": evidence_refs,
        "rationale": (
            "Sentiment, stance, near duplicates, and community comparison should be reviewed "
            "before public-response action."
        ),
        "does_not_modify": DOES_NOT_MODIFY,
        "signals": {
            "sentiment_distribution": sentiment["summary"]["distribution"],
            "stance_status": stance.get("status"),
            "near_duplicate_groups": len(near_duplicates["main_posts"]) + len(near_duplicates["comments"]),
            "community_count": len(community_comparison.get("items", [])),
        },
    }
    if stance.get("status") == "blocked":
        recommendation["rationale"] = (
            "Sentiment and community comparison remain available; approve a Primary Claim before "
            "using stance as an actioning signal."
        )
    return [recommendation]


def propagation_path_overlay(path: dict[str, Any], rows: list[dict[str, Any]], *, primary_claim_ref: str | None = None) -> dict[str, Any]:
    refs = _propagation_evidence_refs(path)
    matched = [
        row
        for row in rows
        if str(row.get("content_id") or "") in refs
        or _semantic_row_content_ref(row) in refs
    ]
    if not matched:
        return {
            "status": "unavailable_no_matched_evidence",
            "texts": 0,
            "claim_refs": [primary_claim_ref] if primary_claim_ref else [],
            "evidence_refs": sorted(refs),
            "score_policy": "evidence_overlay_only",
        }
    return {
        "status": "available",
        "texts": len(matched),
        "sentiment": _distribution_from_rows(matched, "sentiment_label"),
        "stance": _distribution_from_rows(matched, "stance_label"),
        "keywords": [item["term"] for item in _keywords(matched, limit=5)],
        "entities": sorted({entity for row in matched for entity in row.get("entity_names", [])})[:8],
        "platforms": sorted({row["platform"] for row in matched}),
        "time_range": _time_range(matched),
        "claim_refs": [primary_claim_ref] if primary_claim_ref else [],
        "evidence_refs": sorted(ref for ref in refs if ref),
        "evidence_examples": [_example(row) for row in matched[:5]],
        "score_policy": "evidence_overlay_only",
    }


def _propagation_evidence_refs(path: dict[str, Any]) -> set[str]:
    refs = {
        str(path.get(key) or "").strip()
        for key in ("evidence_ref", "source_ref", "target_ref")
        if str(path.get(key) or "").strip()
    }
    refs.update(str(ref).strip() for ref in path.get("evidence_refs") or [] if str(ref).strip())
    for edge in path.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        refs.update(
            str(edge.get(key) or "").strip()
            for key in ("evidence_ref", "source_ref", "target_ref")
            if str(edge.get(key) or "").strip()
        )
    return refs


def _semantic_row_content_ref(row: dict[str, Any]) -> str:
    platform = str(row.get("platform") or "unknown").strip() or "unknown"
    content_id = str(row.get("content_id") or "").strip()
    content_kind = "post" if row.get("content_kind") == "main_post" else "comment"
    return f"{platform}:{content_kind}:{content_id}" if content_id else ""


def _primary_claim_text(options: dict[str, Any]) -> str | None:
    for key in ("primary_claim", "primary_claim_text", "approved_primary_claim"):
        value = options.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("excerpt") or value.get("claim_text") or value.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _tokens(text: str) -> list[str]:
    jieba_tokens = _jieba_tokens(text)
    tokens = [token.lower() for token in jieba_tokens if len(token.strip()) >= 2]
    tokens.extend(token.lower() for token in TOKEN_PATTERN.findall(text))
    deduped = []
    seen = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return deduped or [char for char in text if "\u4e00" <= char <= "\u9fff"]


def _jieba_tokens(text: str) -> list[str]:
    try:
        import jieba

        return [str(token).strip() for token in jieba.cut(text) if str(token).strip()]
    except Exception:
        return TOKEN_PATTERN.findall(text)


def _example(row: dict[str, Any], *, score: float | None = None) -> dict[str, Any]:
    payload = {
        "content_id": row["content_id"],
        "content_kind": row["content_kind"],
        "platform": row["platform"],
        "author_id": row["author_id"],
        "excerpt": row["text"][:120],
    }
    if score is not None:
        payload["score"] = round(float(score), 4)
    return payload


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _row_manifest(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": row["content_id"],
        "content_kind": row["content_kind"],
        "post_id": row["post_id"],
        "platform": row["platform"],
        "author_id": row["author_id"],
        "timestamp": row["timestamp"],
        "text": row["text"],
        "content_hash": row["content_hash"],
        "coordination_community_id": row.get("coordination_community_id"),
        "sentiment_label": row.get("sentiment_label"),
        "sentiment_score": row.get("sentiment_score"),
        "stance_label": row.get("stance_label"),
        "stance_score": row.get("stance_score"),
        "entity_names": list(row.get("entity_names") or []),
    }


def _normalize_vector(vector: Any) -> list[float]:
    values = [float(value) for value in list(vector)]
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        return values
    return [value / norm for value in values]


def _mean_embedding(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        return []
    width = len(embeddings[0])
    return _normalize_vector([sum(vector[index] for vector in embeddings) / len(embeddings) for index in range(width)])


def _term_embedding(term: str, rows: list[dict[str, Any]]) -> list[float]:
    matched = [row["embedding"] for row in rows if term in row["tokens"]]
    return _mean_embedding(matched or [row["embedding"] for row in rows])


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    width = min(len(left), len(right))
    return float(sum(left[index] * right[index] for index in range(width)))


def _mmr_select(scored: list[dict[str, Any]], *, limit: int, diversity: float = 0.35) -> list[dict[str, Any]]:
    remaining = sorted(scored, key=lambda item: item["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    while remaining and len(selected) < limit:
        if not selected:
            selected.append(remaining.pop(0))
            continue
        best_index = 0
        best_score = -10.0
        for index, item in enumerate(remaining):
            novelty_penalty = max(_cosine(item["_embedding"], selected_item["_embedding"]) for selected_item in selected)
            mmr_score = (1 - diversity) * float(item["score"]) - diversity * novelty_penalty
            if mmr_score > best_score:
                best_index = index
                best_score = mmr_score
        selected.append(remaining.pop(best_index))
    return selected


def _cluster_rows(rows: list[dict[str, Any]], *, limit: int) -> list[list[dict[str, Any]]]:
    if len(rows) <= 2:
        return [[row] for row in rows]
    try:
        from sklearn.cluster import MiniBatchKMeans

        cluster_count = max(1, min(limit, int(math.sqrt(len(rows))) + 1, len(rows)))
        model = MiniBatchKMeans(n_clusters=cluster_count, n_init=3, random_state=42)
        labels = model.fit_predict([row["embedding"] for row in rows])
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row, label in zip(rows, labels, strict=False):
            grouped[int(label)].append(row)
        return list(grouped.values())
    except Exception:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["tokens"][0] if row["tokens"] else "general_discussion"].append(row)
        return list(grouped.values())


def _ctfidf_keywords(members: list[dict[str, Any]], corpus: list[dict[str, Any]], *, limit: int) -> list[str]:
    member_counts: Counter[str] = Counter(token for row in members for token in row["tokens"] if token not in STOP_TERMS)
    corpus_docs: Counter[str] = Counter()
    for row in corpus:
        corpus_docs.update(set(token for token in row["tokens"] if token not in STOP_TERMS))
    scored = []
    for token, count in member_counts.items():
        idf = math.log((1 + len(corpus)) / (1 + corpus_docs[token])) + 1
        scored.append((token, count * idf))
    return [token for token, _score in sorted(scored, key=lambda item: item[1], reverse=True)[:limit]]


def _distribution_from_rows(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key) or "unknown") for row in rows))


def _sentiment_label(label: str) -> str:
    text = label.lower()
    if "pos" in text or text in {"5 stars", "4 stars"}:
        return "positive"
    if "neg" in text or text in {"1 star", "2 stars"}:
        return "negative"
    return "neutral"


def _stance_label(label: str) -> str:
    text = label.lower()
    if any(value in text for value in ("support", "entail")):
        return "support"
    if any(value in text for value in ("deny", "refute", "contradict")):
        return "deny"
    return "neutral"


def _normalize_label_score(item: dict[str, Any]) -> dict[str, Any]:
    return {"label": _sentiment_label(str(item.get("label") or "neutral")), "score": round(float(item.get("score") or 0.0), 4)}


def _entity_type(value: str) -> str:
    text = value.lower()
    if text in {"loc", "location", "gpe", "country", "location_or_country"}:
        return "location_or_country"
    if text in {"org", "organization"}:
        return "organization"
    if text in {"per", "person"}:
        return "person"
    if text in {"topic"}:
        return "topic"
    return "named_entity"


def _coordination_community_id(row: dict[str, Any]) -> str:
    for key in ("coordination_community_id", "community_id", "cluster_id", "coordination_cluster_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    raw = row.get("coordination") or row.get("coordination_metadata") or {}
    if isinstance(raw, dict):
        for key in ("community_id", "cluster_id"):
            value = str(raw.get(key) or "").strip()
            if value:
                return value
    return ""


def _time_range(rows: list[dict[str, Any]]) -> dict[str, str | None]:
    values = sorted(str(row.get("timestamp") or "") for row in rows if row.get("timestamp"))
    return {"start": values[0] if values else None, "end": values[-1] if values else None}


def _empty_layers() -> dict[str, Any]:
    empty = {"total_texts": 0, "distribution": {"positive": 0, "neutral": 0, "negative": 0}, "average_score": 0.0, "examples": {}}
    return {"summary": empty, "main_posts": empty, "comments": empty}


def _empty_topics(*, method: str = "bertopic_lite_embedding_cluster_ctfidf") -> dict[str, Any]:
    return {"topic_count": 0, "method": method, "items": []}


def _model_versions() -> dict[str, str]:
    return {
        "embedding": EMBEDDING_MODEL_VERSION,
        "sentiment": SENTIMENT_MODEL_VERSION,
        "stance": STANCE_MODEL_VERSION,
        "ner": NER_MODEL_VERSION,
    }


def _default_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def refresh_semantic_artifact_hash(payload: dict[str, Any]) -> None:
    payload["artifact_sha256"] = _sha256(payload)


def _sha256(payload: dict[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in {"_runtime_rows", "artifact_sha256", "generated_at"}
    }
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def set_hf_cache_env(cache_dir: str = HF_CACHE_DIR) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", cache_dir)
    os.environ.setdefault("TRANSFORMERS_CACHE", cache_dir)
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", cache_dir)


__all__ = [
    "EMBEDDING_MODEL_VERSION",
    "HF_CACHE_DIR",
    "HuggingFaceSemanticRuntime",
    "NER_MODEL_VERSION",
    "SENTIMENT_MODEL_VERSION",
    "SemanticEnrichmentEngine",
    "SemanticModelUnavailable",
    "STANCE_MODEL_VERSION",
    "analyze_semantic_enrichment_snapshot",
    "blocked_semantic_artifact",
    "propagation_path_overlay",
    "refresh_semantic_artifact_hash",
    "semantic_model_blocker",
    "set_hf_cache_env",
]
