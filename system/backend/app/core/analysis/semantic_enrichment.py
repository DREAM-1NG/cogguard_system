"""Offline-safe prototype semantic evidence enrichment for case projections.

This module is intentionally auxiliary: its candidates never alter review,
coordination, propagation, or risk conclusions.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Callable, Iterable, Mapping, Sequence


MODEL_CANDIDATES = {
    "embedding": "BAAI/bge-small-zh-v1.5@7999e1d",
    "sentiment": "lxyuan/distilbert-base-multilingual-cased-sentiments-student@cf99110",
    "stance": "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli@0a71e92",
    "ner": "shibing624/bert4ner-base-chinese@5d660ed",
}
_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+")
_ENTITY_PATTERN = re.compile(r"(?:[\u4e00-\u9fff]{2,}(?:公司|大学|政府|医院|集团|部门|委员会|市|省|县))")
_POSITIVE_TERMS = frozenset({"支持", "真实", "可靠", "证实", "感谢", "积极"})
_NEGATIVE_TERMS = frozenset({"虚假", "不实", "谣言", "不可信", "质疑", "风险", "攻击"})


@dataclass(frozen=True, slots=True)
class SemanticScope:
    """A deterministic, optional evidence subset for semantic candidates."""

    start_at: str | None = None
    end_at: str | None = None
    platforms: tuple[str, ...] = ()
    coordination_community_ids: tuple[str, ...] = ()
    propagation_path_ids: tuple[str, ...] = ()

    def canonical(self) -> dict[str, Any]:
        return {
            "start_at": self.start_at,
            "end_at": self.end_at,
            "platforms": sorted(set(self.platforms)),
            "coordination_community_ids": sorted(set(self.coordination_community_ids)),
            "propagation_path_ids": sorted(set(self.propagation_path_ids)),
        }


def build_semantic_scope_hash(scope: SemanticScope) -> str:
    return _hash_payload(scope.canonical())


def build_semantic_input_hash(records: Iterable[Mapping[str, Any]]) -> str:
    canonical_records = [_canonical_record(record) for record in records]
    return _hash_payload(sorted(canonical_records, key=lambda item: _canonical_json(item)))


def filter_semantic_records(
    records: Iterable[Mapping[str, Any]], scope: SemanticScope
) -> list[dict[str, Any]]:
    """Filter source evidence without interpreting it or changing its meaning."""
    selected: list[dict[str, Any]] = []
    platforms = set(scope.platforms)
    communities = set(scope.coordination_community_ids)
    paths = set(scope.propagation_path_ids)
    for source in records:
        record = dict(source)
        created_at = str(record.get("created_at") or "")
        if scope.start_at and (not created_at or created_at < scope.start_at):
            continue
        if scope.end_at and (not created_at or created_at > scope.end_at):
            continue
        if platforms and str(record.get("platform") or "") not in platforms:
            continue
        if communities and str(record.get("coordination_community_id") or "") not in communities:
            continue
        if paths and str(record.get("propagation_path_id") or "") not in paths:
            continue
        selected.append(record)
    return sorted(selected, key=lambda record: (str(record.get("id") or ""), _canonical_json(record)))


def stratify_semantic_records(records: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    strata = {"posts": [], "comments": []}
    for record in records:
        record_type = str(record.get("record_type") or record.get("type") or "post").lower()
        strata["comments" if record_type == "comment" else "posts"].append(dict(record))
    return strata


class SemanticEnrichmentEngine:
    """Produces unvalidated semantic candidates with offline deterministic fallback."""

    def __init__(
        self,
        *,
        allow_model_loading: bool = False,
        embedding_encoder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
    ) -> None:
        self._allow_model_loading = allow_model_loading
        self._embedding_encoder = embedding_encoder
        self._embedding_cache: dict[str, list[float]] = {}
        self._model_attempted = False
        self._model_available = embedding_encoder is not None

    def enrich(
        self,
        records: Iterable[Mapping[str, Any]],
        scope: SemanticScope,
        *,
        primary_claim: str | None = None,
    ) -> dict[str, Any]:
        filtered = filter_semantic_records(records, scope)
        strata = stratify_semantic_records(filtered)
        texts = [str(record.get("text") or "") for record in filtered]
        embeddings = self._embed_texts(texts)
        scope_hash = build_semantic_scope_hash(scope)
        input_hash = build_semantic_input_hash(filtered)
        degraded = not self._model_available
        metadata = _candidate_metadata(scope_hash, input_hash, len(filtered), degraded)
        outputs = {
            "sentiment": {**metadata, "model_manifest": {"candidate": MODEL_CANDIDATES["sentiment"]}, "items": _sentiment_items(filtered)},
            "keywords": {**metadata, "model_manifest": {"candidate": MODEL_CANDIDATES["embedding"]}, "items": _keywords(filtered, embeddings)},
            "topics": {**metadata, "model_manifest": {"candidate": MODEL_CANDIDATES["embedding"]}, "items": _topics(filtered, embeddings)},
            "entities": {**metadata, "model_manifest": {"candidate": MODEL_CANDIDATES["ner"]}, "items": _entities(filtered)},
            "stance": _stance_output(primary_claim, filtered, embeddings, metadata),
        }
        return {
            "schema": "cogguard.semantic_enrichment.mvp.v1",
            "status": "candidate_unvalidated",
            "auxiliary_only": True,
            "degraded": degraded,
            "scope": scope.canonical(),
            "scope_hash": scope_hash,
            "input_hash": input_hash,
            "strata": {name: {"count": len(rows)} for name, rows in strata.items()},
            "outputs": outputs,
            "shared_embedding_projections": _embedding_projections(filtered, embeddings),
        }

    def _embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        missing = [text for text in dict.fromkeys(texts) if text not in self._embedding_cache]
        if missing:
            encoder = self._embedding_encoder or self._load_embedding_encoder()
            vectors = encoder(missing) if encoder else [_hashed_embedding(text) for text in missing]
            self._embedding_cache.update({text: [float(value) for value in vector] for text, vector in zip(missing, vectors)})
        return [self._embedding_cache[text] for text in texts]

    def _load_embedding_encoder(self) -> Callable[[Sequence[str]], Sequence[Sequence[float]]] | None:
        if self._model_attempted or not self._allow_model_loading:
            return None
        self._model_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("BAAI/bge-small-zh-v1.5", revision="7999e1d", device="cpu")
            self._model_available = True
            return lambda texts: model.encode(list(texts), normalize_embeddings=True).tolist()
        except Exception:
            return None


def merge_semantics_into_case_projection(
    case_projection: Mapping[str, Any], semantic_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Attach auxiliary candidates without changing existing case-projection values."""
    merged = dict(case_projection)
    merged["semantic_enrichment"] = dict(semantic_payload)
    return merged


def _candidate_metadata(scope_hash: str, input_hash: str, count: int, degraded: bool) -> dict[str, Any]:
    return {
        "status": "candidate_unvalidated",
        "auxiliary_only": True,
        "degraded": degraded,
        "coverage": {"record_count": count, "text_coverage": 1.0 if count else 0.0},
        "confidence": 0.35 if degraded else 0.6,
        "scope_hash": scope_hash,
        "input_hash": input_hash,
    }


def _sentiment_items(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for record in records:
        text = str(record.get("text") or "")
        positive = sum(term in text for term in _POSITIVE_TERMS)
        negative = sum(term in text for term in _NEGATIVE_TERMS)
        label = "positive" if positive > negative else "negative" if negative > positive else "neutral"
        items.append({"record_id": str(record.get("id") or ""), "label": label, "score": round(abs(positive - negative) / max(1, positive + negative), 3)})
    return items


def _keywords(records: Sequence[Mapping[str, Any]], embeddings: Sequence[Sequence[float]]) -> list[dict[str, Any]]:
    counts = Counter(token for record in records for token in _tokens(str(record.get("text") or "")))
    if not counts:
        return []
    document = _mean_vector(embeddings)
    ranked = []
    selected: list[list[float]] = []
    for token, frequency in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        vector = _hashed_embedding(token)
        relevance = _cosine(document, vector)
        diversity = max((_cosine(vector, previous) for previous in selected), default=0.0)
        ranked.append((0.72 * relevance - 0.28 * diversity, token, frequency, vector))
    results = []
    for score, token, frequency, vector in sorted(ranked, key=lambda row: (-row[0], row[1]))[:8]:
        selected.append(vector)
        results.append({"term": token, "score": round(score, 4), "frequency": frequency})
    return results


def _topics(records: Sequence[Mapping[str, Any]], embeddings: Sequence[Sequence[float]]) -> list[dict[str, Any]]:
    groups: dict[int, list[int]] = defaultdict(list)
    for index, vector in enumerate(embeddings):
        groups[_vector_bucket(vector)].append(index)
    topics = []
    for topic_id, indexes in sorted(groups.items()):
        words = Counter(token for index in indexes for token in _tokens(str(records[index].get("text") or "")))
        c_tf_idf = sorted(words.items(), key=lambda item: (-item[1] / max(1, len(indexes)), item[0]))[:5]
        topics.append({"topic_id": f"topic-{topic_id}", "record_ids": [str(records[index].get("id") or "") for index in indexes], "terms": [term for term, _ in c_tf_idf]})
    return topics


def _entities(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(entity for record in records for entity in _ENTITY_PATTERN.findall(str(record.get("text") or "")))
    return [{"text": text, "label": "heuristic_organization_or_location", "count": count} for text, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _stance_output(primary_claim: str | None, records: Sequence[Mapping[str, Any]], embeddings: Sequence[Sequence[float]], metadata: Mapping[str, Any]) -> dict[str, Any]:
    if not primary_claim or not primary_claim.strip():
        return {**metadata, "status": "blocked_missing_primary_claim", "model_manifest": {"candidate": MODEL_CANDIDATES["stance"]}, "items": []}
    claim_terms = set(_tokens(primary_claim))
    items = []
    for record, vector in zip(records, embeddings):
        text = str(record.get("text") or "")
        overlap = len(claim_terms & set(_tokens(text)))
        contradiction = any(term in text for term in ("不", "虚假", "谣言", "不可信"))
        label = "contradicts" if contradiction else "supports" if overlap else "unrelated"
        items.append({"record_id": str(record.get("id") or ""), "label": label, "score": round(min(1.0, 0.3 + 0.15 * overlap + 0.1 * _cosine(vector, _hashed_embedding(primary_claim))), 3)})
    return {**metadata, "model_manifest": {"candidate": MODEL_CANDIDATES["stance"]}, "items": items}


def _embedding_projections(records: Sequence[Mapping[str, Any]], embeddings: Sequence[Sequence[float]]) -> dict[str, Any]:
    duplicate_pairs = []
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            similarity = _cosine(embeddings[left], embeddings[right])
            if similarity >= 0.9:
                duplicate_pairs.append({"record_ids": [str(records[left].get("id") or ""), str(records[right].get("id") or "")], "similarity": round(similarity, 4)})
    communities: dict[str, list[Sequence[float]]] = defaultdict(list)
    for record, embedding in zip(records, embeddings):
        community = str(record.get("coordination_community_id") or "unassigned")
        communities[community].append(embedding)
    centroids = {name: _mean_vector(vectors) for name, vectors in communities.items()}
    differences = [{"community_ids": [left, right], "cosine_distance": round(1 - _cosine(centroids[left], centroids[right]), 4)} for left in sorted(centroids) for right in sorted(centroids) if left < right]
    return {"near_duplicates": duplicate_pairs, "community_differences": differences}


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


def _hashed_embedding(text: str, dimensions: int = 16) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokens(text) or [text]:
        digest = sha256(token.encode("utf-8")).digest()
        for index in range(dimensions):
            vector[index] += (digest[index] / 127.5) - 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        return [0.0] * 16
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(len(vectors[0]))]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def _vector_bucket(vector: Sequence[float]) -> int:
    return int(sum((index + 1) * value for index, value in enumerate(vector)) * 10) % 3


def _canonical_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in record.items() if str(key) not in {"_id", "updated_at"}}


def _hash_payload(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
