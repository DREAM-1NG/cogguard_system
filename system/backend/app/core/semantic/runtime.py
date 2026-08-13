"""Real local-model semantic enrichment for immutable event snapshots.

This module deliberately has no rule or feature-engineering fallback.  It
either runs the configured local SentenceTransformer/Transformers models or
raises ``ModelWeightsBlockedError`` for the executor to persist as a blocked
semantic stage.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import importlib
import math
from pathlib import Path
from typing import Any, Iterable


MODEL_SPECS: dict[str, dict[str, str]] = {
    "bge_embedding": {"repo": "BAAI/bge-small-zh-v1.5", "revision": "7999e1d"},
    "sentiment": {
        "repo": "lxyuan/distilbert-base-multilingual-cased-sentiments-student",
        "revision": "cf99110",
    },
    "stance": {"repo": "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli", "revision": "0a71e92"},
    "ner": {"repo": "shibing624/bert4ner-base-chinese", "revision": "5d660ed"},
}


class ModelWeightsBlockedError(RuntimeError):
    """The semantic stage cannot truthfully run with its fixed local models."""


class SemanticEnrichmentRuntime:
    """Runs fixed local models and builds auxiliary evidence overlays only."""

    def __init__(
        self,
        *,
        model_root: str | Path = r"G:\CISCN\hf_models",
        embedding_model: Any = None,
        sentiment_pipeline: Any = None,
        stance_pipeline: Any = None,
        ner_pipeline: Any = None,
        embedding_output_root: str | Path | None = None,
    ) -> None:
        self.model_root = Path(model_root)
        self.embedding_output_root = Path(
            embedding_output_root or Path(__file__).resolve().parents[3] / "output" / "semantic_embeddings"
        )
        self.embedding_model = embedding_model or self._load_embedding_model()
        self.sentiment_pipeline = sentiment_pipeline or self._load_pipeline("sentiment", "text-classification")
        self.stance_pipeline = stance_pipeline or self._load_pipeline("stance", "text-classification")
        self.ner_pipeline = ner_pipeline or self._load_pipeline("ner", "token-classification")

    @classmethod
    def ensure_runtime_dependencies(cls) -> None:
        """Verify imports required by the fixed local semantic runtime.

        Dependency failures are part of the model-readiness contract and must
        be reported as a blocked semantic stage rather than an import crash.
        """

        for module_name in ("jieba", "numpy", "sklearn", "transformers", "torch"):
            try:
                importlib.import_module(module_name)
            except Exception as exc:
                raise ModelWeightsBlockedError(
                    f"{module_name} runtime dependency unavailable: {exc}"
                ) from exc

    def enrich(
        self,
        snapshot: Any,
        *,
        coordination: dict[str, Any] | None = None,
        propagation: dict[str, Any] | None = None,
        claim: str | None = None,
    ) -> dict[str, Any]:
        rows = [("posts", row, str(row.get("content") or "")) for row in snapshot.posts]
        rows.extend(("comments", row, str(row.get("content") or "")) for row in snapshot.comments)
        texts = [text for _, _, text in rows]
        embeddings = self._encode_texts(texts)
        embedding_manifest = self._persist_embeddings(snapshot.data_fingerprint, embeddings, texts)

        try:
            sentiment_rows = _result_rows(self.sentiment_pipeline(texts, truncation=True, batch_size=32), len(texts)) if texts else []
            entity_rows = _result_rows(
                self.ner_pipeline(texts, aggregation_strategy="simple", batch_size=32), len(texts)
            ) if texts else []
            stance_rows = self._classify_stance(texts, claim)
        except Exception as exc:
            raise ModelWeightsBlockedError(f"semantic inference failed: {exc}") from exc

        layers: dict[str, list[dict[str, Any]]] = {"posts": [], "comments": []}
        for index, (layer, row, text) in enumerate(rows):
            sentiment = _first_mapping(sentiment_rows[index])
            item_id = row.get("post_id") if layer == "posts" else row.get("comment_id")
            layers[layer].append(
                {
                    "id": str(item_id or index),
                    "author_id": str(row.get("author_id") or ""),
                    "platform": str(row.get("platform") or "unknown"),
                    "timestamp": str(row.get("timestamp") or ""),
                    "text": text,
                    "sentiment": sentiment,
                    "stance": stance_rows[index],
                    "keywords": [],
                    "topics": [],
                    "entities": _normalize_entities(entity_rows[index]),
                    "embedding_index": index,
                }
            )

        items = _all_items(layers)
        keywords = self._keywords([item["text"] for item in items], embeddings)
        topics = _topics([item["text"] for item in items], embeddings)
        for item, item_keywords, item_topic in zip(items, keywords, topics):
            item["keywords"] = item_keywords
            item["topics"] = [item_topic] if item_topic else []
        _attach_near_duplicates(items, embeddings)

        communities, unavailable_reason = _community_slices(layers, coordination or {}, snapshot)
        path_overlays, path_unavailable_reason = _path_overlays(
            snapshot,
            layers,
            propagation or {},
            claim,
        )

        return _json_primitives(
            {
                "technology": "semantic_enrichment",
                "status": "ok",
                "runtime_status": "ready",
                "runtime_backend": "transformers_sentence_transformers",
                "model_versions": {
                    name: f"{spec['repo']}@{spec['revision']}" for name, spec in MODEL_SPECS.items()
                },
                "cache_dir": str(self.model_root),
                "validation_status": "candidate_unvalidated",
                "auxiliary_only": True,
                "embedding_manifest": {
                    "count": len(embeddings),
                    "shape": [len(embeddings), len(embeddings[0]) if embeddings else 0],
                    "snapshot_fingerprint": snapshot.data_fingerprint,
                    "text_hashes": [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts],
                    "reused_for": [
                        "keywords",
                        "topics",
                        "near_duplicates",
                        "community_comparison",
                        "propagation_path_overlay",
                    ],
                    **embedding_manifest,
                },
                "layers": layers,
                "cross_analysis": {
                    "time_slices": _time_slices(layers),
                    "platform_slices": _platform_slices(layers),
                    "community_slices": communities,
                    "community_slices_unavailable_reason": unavailable_reason,
                    "propagation_path_overlays": path_overlays,
                    "propagation_path_overlays_unavailable_reason": path_unavailable_reason,
                },
            }
        )

    def _load_embedding_model(self) -> Any:
        path = self._require_weights("bge_embedding")
        try:
            # Use the same BGE checkpoint through the lightweight Transformers
            # path. This avoids importing sentence-transformers' optional
            # TensorFlow integration while still performing real LM inference.
            _patch_torch_distribution_metadata()
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
            model = AutoModel.from_pretrained(str(path), local_files_only=True)
            model.eval()

            class _BgeEncoder:
                def encode(self, texts: list[str], **_kwargs: Any) -> list[list[float]]:
                    import torch

                    with torch.no_grad():
                        encoded = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
                        output = model(**encoded).last_hidden_state
                        mask = encoded["attention_mask"].unsqueeze(-1).expand(output.size()).float()
                        pooled = (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
                    return pooled.cpu().tolist()

            return _BgeEncoder()
        except Exception as exc:
            raise ModelWeightsBlockedError(f"bge_embedding failed to load from {path}: {exc}") from exc

    def _load_pipeline(self, name: str, task: str) -> Any:
        path = self._require_weights(name)
        try:
            _patch_torch_distribution_metadata()
            from transformers import (
                AutoModelForSequenceClassification,
                AutoModelForTokenClassification,
                AutoTokenizer,
                pipeline,
            )

            tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
            model_type = AutoModelForTokenClassification if task == "token-classification" else AutoModelForSequenceClassification
            model = model_type.from_pretrained(str(path), local_files_only=True)
            return pipeline(task, model=model, tokenizer=tokenizer, device=-1)
        except Exception as exc:
            raise ModelWeightsBlockedError(f"{name} failed to load from {path}: {exc}") from exc

    def _model_path(self, name: str) -> Path:
        spec = MODEL_SPECS[name]
        local_snapshot = self.model_root / "local_snapshots" / f"{spec['repo'].replace('/', '__')}--{spec['revision']}"
        if local_snapshot.is_dir():
            return local_snapshot
        hub_root = self.model_root / f"models--{spec['repo'].replace('/', '--')}"
        ref = hub_root / "refs" / spec["revision"]
        revision = ref.read_text(encoding="utf-8").strip() if ref.is_file() else spec["revision"]
        return hub_root / "snapshots" / revision

    def _require_weights(self, name: str) -> Path:
        path = self._model_path(name)
        has_tokenizer = any((path / filename).is_file() for filename in ("tokenizer.json", "vocab.txt", "sentencepiece.bpe.model"))
        has_weights = any(path.glob("*.safetensors")) or any(path.glob("*.bin"))
        if not path.is_dir() or not (path / "config.json").is_file() or not has_tokenizer or not has_weights:
            spec = MODEL_SPECS[name]
            raise ModelWeightsBlockedError(
                f"{name}: local weights unavailable under {path}; manually download {spec['repo']}@{spec['revision']}"
            )
        return path

    def _encode_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self.embedding_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [[float(value) for value in vector] for vector in vectors]
        except Exception as exc:
            raise ModelWeightsBlockedError(f"bge_embedding inference failed: {exc}") from exc

    def _classify_stance(self, texts: list[str], claim: str | None) -> list[dict[str, Any]]:
        if not claim or not claim.strip():
            return [{"status": "blocked_missing_primary_claim", "label": None, "score": None} for _ in texts]
        raw = self.stance_pipeline(
            [{"text": text, "text_pair": claim} for text in texts], truncation=True, batch_size=32
        )
        return [
            {"status": "ready", **_first_mapping(value)}
            for value in _result_rows(raw, len(texts))
        ]

    def _keywords(self, texts: list[str], embeddings: list[list[float]]) -> list[list[dict[str, Any]]]:
        try:
            import jieba
            import numpy as np
        except ModuleNotFoundError as exc:
            raise ModelWeightsBlockedError(f"semantic runtime dependency unavailable: {exc}") from exc

        candidates = [list(dict.fromkeys(_candidate_terms(jieba.lcut(text))))[:20] for text in texts]
        unique_terms = list(dict.fromkeys(term for terms in candidates for term in terms))
        if not unique_terms:
            return [[] for _ in texts]
        try:
            term_vectors = self.embedding_model.encode(unique_terms, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            raise ModelWeightsBlockedError(f"bge keyword candidate encoding failed: {exc}") from exc
        vector_by_term = {term: np.asarray(vector, dtype=float) for term, vector in zip(unique_terms, term_vectors)}
        results: list[list[dict[str, Any]]] = []
        for terms, document in zip(candidates, embeddings):
            if not terms:
                results.append([])
                continue
            matrix = np.asarray([vector_by_term[term] for term in terms], dtype=float)
            relevance = matrix @ np.asarray(document, dtype=float)
            selected: list[int] = []
            remaining = list(range(len(terms)))
            while remaining and len(selected) < 5:
                index = max(
                    remaining,
                    key=lambda item: float(relevance[item]) - 0.35 * max(
                        (float(np.dot(matrix[item], matrix[prior])) for prior in selected), default=0.0
                    ),
                )
                selected.append(index)
                remaining.remove(index)
            results.append([{"term": terms[index], "score": round(float(relevance[index]), 6)} for index in selected])
        return results

    def _persist_embeddings(self, fingerprint: str, embeddings: list[list[float]], texts: list[str]) -> dict[str, Any]:
        import numpy as np

        self.embedding_output_root.mkdir(parents=True, exist_ok=True)
        path = self.embedding_output_root / f"{fingerprint}.npy.gz"
        with gzip.open(path, "wb") as stream:
            np.save(stream, np.asarray(embeddings, dtype=np.float32), allow_pickle=False)
        return {
            "artifact_path": str(path),
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "artifact_format": "npy.gz",
            "text_hashes_path": None,
        }


def _candidate_terms(tokens: Iterable[str]) -> Iterable[str]:
    for token in tokens:
        value = str(token).strip()
        if len(value) > 1 and not value.isspace() and not value.isdigit():
            yield value


def _patch_torch_distribution_metadata() -> None:
    """Handle the local CUDA wheel whose dist-info lacks METADATA."""
    import importlib.metadata as metadata

    if getattr(metadata, "_cogguard_torch_patch", False):
        return
    original_version = metadata.version

    def version(name: str) -> str:
        if name == "torch":
            import torch

            return str(getattr(torch, "__version__", "2.0.0")).split("+")[0]
        return original_version(name)

    metadata.version = version
    metadata._cogguard_torch_patch = True


def _result_rows(value: Any, expected: int) -> list[Any]:
    if isinstance(value, list):
        if expected == 1 and value and isinstance(value[0], dict):
            return [value]
        return value
    return [value for _ in range(expected)]


def _first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        value = value[0] if value else {}
    return dict(value) if isinstance(value, dict) else {}


def _normalize_entities(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    return [
        {
            "text": str(item.get("word") or item.get("entity") or ""),
            "label": item.get("entity_group") or item.get("entity"),
            "score": item.get("score"),
        }
        for item in (value or [])
        if isinstance(item, dict) and str(item.get("word") or item.get("entity") or "").strip()
    ]


def _all_items(layers: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [item for values in layers.values() for item in values]


def _topics(texts: list[str], embeddings: list[list[float]]) -> list[dict[str, Any] | None]:
    if not texts:
        return []
    try:
        import jieba
        import numpy as np
        from sklearn.cluster import KMeans
    except ModuleNotFoundError as exc:
        raise ModelWeightsBlockedError(f"semantic runtime dependency unavailable: {exc}") from exc

    clusters = 1 if len(texts) < 4 else min(6, max(2, int(len(texts) ** 0.5)))
    labels = KMeans(n_clusters=clusters, random_state=42, n_init=10).fit_predict(np.asarray(embeddings, dtype=float))
    by_cluster: dict[int, Counter[str]] = defaultdict(Counter)
    for label, text in zip(labels, texts):
        by_cluster[int(label)].update(_candidate_terms(jieba.lcut(text)))
    all_terms = Counter(term for counts in by_cluster.values() for term in counts.elements())
    names: dict[int, tuple[str, float]] = {}
    for label, counts in by_cluster.items():
        total = sum(counts.values()) or 1
        scored = [
            (term, (count / total) * math.log((1 + len(texts)) / (1 + all_terms[term])))
            for term, count in counts.items()
        ]
        names[label] = max(scored, key=lambda value: value[1]) if scored else (f"topic_{label}", 0.0)
    return [
        {"id": f"topic_{int(label)}", "label": names[int(label)][0], "score": round(float(names[int(label)][1]), 6)}
        for label in labels
    ]


def _attach_near_duplicates(items: list[dict[str, Any]], embeddings: list[list[float]], threshold: float = 0.92) -> None:
    import numpy as np

    matrix = np.asarray(embeddings, dtype=float)
    for index, item in enumerate(items):
        item["near_duplicates"] = [
            {"id": items[other]["id"], "similarity": round(float(np.dot(matrix[index], matrix[other])), 6)}
            for other in range(index)
            if float(np.dot(matrix[index], matrix[other])) >= threshold
        ]


def _platform_slices(layers: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _all_items(layers):
        groups[str(item["platform"])].append(item)
    return [
        {"platform": platform, "count": len(items), "sentiment": _distribution(items, "sentiment")}
        for platform, items in sorted(groups.items())
    ]


def _time_slices(layers: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    counts = Counter(str(item.get("timestamp") or "unknown")[:10] for item in _all_items(layers))
    return [{"date": date, "count": count} for date, count in sorted(counts.items())]


def _community_slices(
    layers: dict[str, list[dict[str, Any]]], coordination: dict[str, Any], snapshot: Any
) -> tuple[list[dict[str, Any]], str | None]:
    if not coordination:
        return [], "coordination_result_unavailable"
    if coordination.get("fallback") is True:
        return [], "coordination_fallback"
    verified, unavailable_reason = _load_verified_coordination_result(coordination, snapshot)
    if verified is None:
        return [], unavailable_reason or "coordination_artifact_unavailable"
    network = verified.get("network") if isinstance(verified.get("network"), dict) else {}
    clusters = network.get("clusters") if isinstance(network.get("clusters"), list) else []
    available = _all_items(layers)
    slices: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters):
        if not isinstance(cluster, dict):
            continue
        members = _cluster_members(cluster)
        rows = [item for item in available if str(item.get("author_id") or "") in set(members)]
        if not rows:
            continue
        slices.append(
            {
                "community_id": str(cluster.get("cluster_id") or cluster.get("id") or index),
                "members": members,
                "member_count": len(members),
                "item_count": len(rows),
                "sentiment_distribution": _distribution(rows, "sentiment"),
                "stance_distribution": _distribution(rows, "stance"),
                "top_keywords": _top_keywords(rows),
                "top_topics": _top_topics(rows),
                "top_entities": _top_entities(rows),
            }
        )
    return (slices, None) if slices else ([], "coordination_clusters_unavailable")


def _load_verified_coordination_result(
    coordination: dict[str, Any], snapshot: Any
) -> tuple[dict[str, Any] | None, str | None]:
    artifact_dir = str(coordination.get("artifact_dir") or "").strip()
    if not artifact_dir:
        return None, "coordination_artifact_unavailable"
    try:
        from app.core.analysis.coordination_discover_adapter import try_load_coordination_discover_result

        loaded, reason = try_load_coordination_discover_result(
            snapshot,
            {"artifact_dir": artifact_dir},
        )
    except Exception:
        return None, "coordination_artifact_unavailable"
    if isinstance(loaded, dict):
        manifest = loaded.get("artifact_manifest")
        if isinstance(manifest, dict) and manifest.get("artifact_hashes"):
            return loaded, None
        return None, "coordination_artifact_unavailable"
    if reason == "artifact_fingerprint_mismatch":
        return None, "coordination_artifact_snapshot_mismatch"
    return None, "coordination_artifact_unavailable"


def _cluster_members(cluster: dict[str, Any]) -> list[str]:
    members: list[str] = []
    for item in cluster.get("members") or []:
        value = item.get("account_id") or item.get("id") if isinstance(item, dict) else item
        value = str(value or "").strip()
        if value and value not in members:
            members.append(value)
    return members


def _distribution(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(_label(item, field) for item in items).items()))


def _label(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if isinstance(value, list):
        value = value[0] if value else {}
    return str(value.get("label") or "unknown") if isinstance(value, dict) else "unknown"


def _top_keywords(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(keyword["term"] for item in items for keyword in item["keywords"] if keyword.get("term"))
    return [{"term": term, "count": count} for term, count in counts.most_common(10)]


def _top_topics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((topic.get("id"), topic.get("label")) for item in items for topic in item["topics"] if topic.get("label"))
    return [{"id": key[0], "label": key[1], "count": count} for key, count in counts.most_common(10)]


def _top_entities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((entity.get("text"), entity.get("label")) for item in items for entity in item["entities"] if entity.get("text"))
    return [{"text": key[0], "label": key[1], "count": count} for key, count in counts.most_common(10)]


def _path_overlays(
    snapshot: Any,
    layers: dict[str, list[dict[str, Any]]],
    propagation: dict[str, Any],
    claim: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    del snapshot, layers, propagation, claim
    return [], "propagation_result_unavailable"


def _json_primitives(value: Any) -> Any:
    if isinstance(value, Counter):
        return {str(key): _json_primitives(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): _json_primitives(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_primitives(item) for item in value]
    converter = getattr(value, "item", None)
    if callable(converter) and type(value).__module__.startswith("numpy"):
        return converter()
    return value
