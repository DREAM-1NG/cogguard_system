from __future__ import annotations

import hashlib
import gzip
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MODEL_SPECS = {
    "bge_embedding": {"repo": "BAAI/bge-small-zh-v1.5", "revision": "7999e1d"},
    "sentiment": {"repo": "lxyuan/distilbert-base-multilingual-cased-sentiments-student", "revision": "cf99110"},
    "stance": {"repo": "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli", "revision": "0a71e92"},
    "ner": {"repo": "shibing624/bert4ner-base-chinese", "revision": "5d660ed"},
}


class ModelWeightsBlockedError(RuntimeError):
    pass


class SemanticEnrichmentRuntime:
    def __init__(self, *, model_root: str | Path = r"G:\CISCN\hf_models", embedding_model: Any = None,
                 sentiment_pipeline: Any = None, stance_pipeline: Any = None, ner_pipeline: Any = None,
                 embedding_output_root: str | Path | None = None) -> None:
        self.model_root = Path(model_root)
        self.embedding_output_root = Path(embedding_output_root or Path(__file__).resolve().parents[3] / "output" / "semantic_embeddings")
        self._injected = any(value is not None for value in (embedding_model, sentiment_pipeline, stance_pipeline, ner_pipeline))
        self.embedding_model = embedding_model or self._load_embedding()
        self.sentiment_pipeline = sentiment_pipeline or self._load_pipeline("sentiment", "text-classification")
        self.stance_pipeline = stance_pipeline or self._load_pipeline("stance", "text-classification")
        self.ner_pipeline = ner_pipeline or self._load_pipeline("ner", "token-classification")

    def enrich(self, snapshot: Any, *, coordination: dict[str, Any] | None = None,
               propagation: dict[str, Any] | None = None, claim: str | None = None) -> dict[str, Any]:
        rows = [("posts", row, str(row.get("content") or "")) for row in snapshot.posts]
        rows += [("comments", row, str(row.get("content") or "")) for row in snapshot.comments]
        texts = [text for _, _, text in rows]
        embeddings = self.embedding_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        embedding_list = [list(map(float, vector)) for vector in embeddings]
        embedding_manifest = self._persist_embeddings(snapshot.data_fingerprint, embedding_list, texts)
        sentiments = _as_result_list(self.sentiment_pipeline(texts, truncation=True, batch_size=32), len(texts))
        stances = self._stances(texts, claim)
        entity_rows = _as_result_list(self.ner_pipeline(texts, aggregation_strategy="simple", batch_size=32), len(texts))
        layers: dict[str, list[dict[str, Any]]] = {"posts": [], "comments": []}
        for index, (layer, row, text) in enumerate(rows):
            sentiment = sentiments[index]
            if isinstance(sentiment, list):
                sentiment = sentiment[0] if sentiment else {}
            stance = stances[index]
            entities = _normalize_entities(entity_rows[index])
            layers[layer].append({
                "id": str((row.get("post_id") if layer == "posts" else row.get("comment_id")) or index),
                "author_id": str(row.get("author_id") or ""),
                "platform": row.get("platform"), "timestamp": str(row.get("timestamp") or ""),
                "text": text, "sentiment": sentiment, "stance": stance,
                "keywords": [], "topics": [], "entities": entities,
                "embedding_index": index,
            })
        all_items = _all_items(layers)
        keyword_rows = self._keywords_from_embeddings([item["text"] for item in all_items], embedding_list)
        topic_rows = _topic_rows([item["text"] for item in all_items], embedding_list)
        for item, keywords, topic in zip(all_items, keyword_rows, topic_rows):
            item["keywords"] = keywords
            item["topics"] = [topic] if topic else []
        _attach_near_duplicates(all_items, embedding_list)
        communities, community_slices_unavailable_reason = _community_slices(
            layers,
            coordination or {},
            snapshot=snapshot,
        )
        paths = _path_overlays(snapshot, layers, propagation or {}, claim) or _observed_path_overlays(snapshot, layers, claim)
        artifact = {
            "runtime_status": "ready", "runtime_backend": "transformers_sentence_transformers",
            "model_versions": {key: f"{spec['repo']}@{spec['revision']}" for key, spec in MODEL_SPECS.items()},
            "cache_dir": str(self.model_root), "validation_status": "candidate_unvalidated",
            "embedding_manifest": {"count": len(embedding_list), "shape": [len(embedding_list), len(embedding_list[0]) if embedding_list else 0],
                                    "snapshot_fingerprint": snapshot.data_fingerprint,
                                    "text_hashes": [hashlib.sha256(text.encode()).hexdigest() for text in texts], **embedding_manifest,
                                    "reused_for": ["keywords", "topics", "near_duplicates", "community_comparison", "propagation_path_overlay"]},
            "layers": layers,
            "cross_analysis": {
                "time_slices": _time_slices(layers),
                "platform_slices": _platform_slices(layers),
                "community_slices": communities,
                "community_slices_unavailable_reason": community_slices_unavailable_reason,
                "propagation_path_overlays": paths,
            },
        }
        return _json_primitives(artifact)

    def _load_embedding(self):
        self._require_weights("bge_embedding")
        from sentence_transformers import SentenceTransformer
        spec = MODEL_SPECS["bge_embedding"]
        return SentenceTransformer(str(self._model_path("bge_embedding")), local_files_only=True)

    def _load_pipeline(self, key: str, task: str):
        self._require_weights(key)
        from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer, pipeline
        path = str(self._model_path(key))
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        model_class = AutoModelForTokenClassification if task == "token-classification" else AutoModelForSequenceClassification
        model = model_class.from_pretrained(path, local_files_only=True)
        return pipeline(task, model=model, tokenizer=tokenizer)

    def _model_path(self, key: str) -> Path:
        repo = MODEL_SPECS[key]["repo"]
        local_snapshot = self.model_root / "local_snapshots" / f"{repo.replace('/', '__')}--{MODEL_SPECS[key]['revision']}"
        if local_snapshot.is_dir():
            return local_snapshot
        directory = self.model_root / ("models--" + repo.replace("/", "--"))
        ref = directory / "refs" / MODEL_SPECS[key]["revision"]
        commit = ref.read_text(encoding="utf-8").strip() if ref.is_file() else MODEL_SPECS[key]["revision"]
        return directory / "snapshots" / commit

    def _require_weights(self, key: str) -> None:
        path = self._model_path(key)
        if not path.is_dir() or not (path / "config.json").is_file() or not any(path.glob("*.safetensors")) and not any(path.glob("*.bin")):
            raise ModelWeightsBlockedError(f"{key}: local weights unavailable under {path}; download revision {MODEL_SPECS[key]['revision']} manually")

    def _stance(self, text: str, claim: str | None):
        if not claim:
            return {"status": "blocked_missing_primary_claim", "label": None, "score": None}
        result = self.stance_pipeline({"text": text, "text_pair": claim}, truncation=True)
        if isinstance(result, dict):
            result = result
        elif isinstance(result, list):
            result = result[0] if result else {}
        if isinstance(result, list):
            result = result[0] if result else {}
        return {"status": "ready", **result}

    def _stances(self, texts: list[str], claim: str | None):
        if not claim:
            return [{"status": "blocked_missing_primary_claim", "label": None, "score": None} for _ in texts]
        raw = self.stance_pipeline([{"text": text, "text_pair": claim} for text in texts], truncation=True, batch_size=32)
        values = _as_result_list(raw, len(texts))
        result = []
        for value in values:
            if isinstance(value, list): value = value[0] if value else {}
            result.append({"status": "ready", **(value if isinstance(value, dict) else {})})
        return result

    def _keywords_from_embeddings(self, texts, embeddings):
        import jieba
        import numpy as np
        candidates_by_text = []
        all_candidates = []
        for text in texts:
            candidates = [term for term in jieba.lcut(text) if len(term.strip()) > 1 and not term.isspace()]
            unique = list(dict.fromkeys(candidates))[:20]
            candidates_by_text.append(unique)
            all_candidates.extend(unique)
        unique_candidates = list(dict.fromkeys(all_candidates))
        candidate_vectors = self.embedding_model.encode(
            unique_candidates,
            normalize_embeddings=True,
            show_progress_bar=False,
        ) if unique_candidates else []
        candidate_by_term = {
            term: np.asarray(vector, dtype=float)
            for term, vector in zip(unique_candidates, candidate_vectors)
        }
        result = []
        for unique, vector in zip(candidates_by_text, embeddings):
            if not unique:
                result.append([])
                continue
            vectors = np.asarray([candidate_by_term[term] for term in unique], dtype=float)
            doc = np.asarray(vector, dtype=float)
            scores = vectors @ doc
            selected = []
            remaining = list(range(len(unique)))
            while remaining and len(selected) < 5:
                best = max(remaining, key=lambda idx: float(scores[idx]) - 0.35 * max((float(np.dot(vectors[idx], vectors[item])) for item in selected), default=0.0))
                selected.append(best)
                remaining.remove(best)
            result.append([{"term": unique[index], "score": round(float(scores[index]), 6)} for index in selected])
        return result

    def _persist_embeddings(self, fingerprint: str, embeddings: list[list[float]], texts: list[str]) -> dict[str, Any]:
        import numpy as np
        self.embedding_output_root.mkdir(parents=True, exist_ok=True)
        path = self.embedding_output_root / f"{fingerprint}.npy.gz"
        # `np.savez_compressed` allocates another full compression buffer. A
        # stream keeps the real BGE matrix persisted on CPU-only demo hosts.
        with gzip.open(path, "wb") as stream:
            np.save(stream, np.asarray(embeddings, dtype=np.float32), allow_pickle=False)
        return {
            "artifact_path": str(path),
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "artifact_format": "npy.gz",
            "text_hashes_path": None,
        }


def _all_items(layers):
    return [item for values in layers.values() for item in values]


def _as_result_list(value: Any, length: int) -> list[Any]:
    if isinstance(value, list):
        if length == 1 and value and isinstance(value[0], dict): return [value]
        return value
    return [value for _ in range(length)]


def _normalize_entities(raw: Any):
    if isinstance(raw, dict): raw = [raw]
    if isinstance(raw, list) and raw and isinstance(raw[0], list): raw = raw[0]
    return [{"text": str(item.get("word") or item.get("entity") or ""), "label": item.get("entity_group") or item.get("entity"), "score": item.get("score")} for item in (raw or []) if isinstance(item, dict) and str(item.get("word") or item.get("entity") or "").strip()]


def _topic_rows(texts, embeddings):
    if not texts:
        return []
    from sklearn.cluster import KMeans
    import jieba
    import numpy as np
    clusters = 1 if len(texts) < 4 else min(6, max(2, int(len(texts) ** 0.5)))
    labels = KMeans(n_clusters=clusters, random_state=42, n_init=10).fit_predict(np.asarray(embeddings, dtype=float))
    terms_by_label = defaultdict(Counter)
    for label, text in zip(labels, texts):
        terms_by_label[int(label)].update(term for term in jieba.lcut(text) if len(term.strip()) > 1)
    total = sum(terms_by_label.values(), Counter())
    names = {}
    scores = {}
    for label, counts in terms_by_label.items():
        candidates = [(term, (count / max(1, sum(counts.values()))) * math.log((1 + len(texts)) / (1 + total[term]))) for term, count in counts.items()]
        term, score = max(candidates, key=lambda item: item[1]) if candidates else (f"topic_{label}", 0.0)
        names[label], scores[label] = term, score
    return [{"id": f"topic_{int(label)}", "label": names[int(label)], "score": round(float(scores[int(label)]), 6)} for label in labels]


def _attach_near_duplicates(items, embeddings, threshold: float = 0.92):
    import numpy as np
    matrix = np.asarray(embeddings, dtype=float)
    for index, item in enumerate(items):
        matches = []
        for other in range(index):
            score = float(np.dot(matrix[index], matrix[other]))
            if score >= threshold:
                matches.append({"id": items[other]["id"], "similarity": round(score, 6)})
        item["near_duplicates"] = matches


def _platform_slices(layers):
    groups = defaultdict(list)
    for item in _all_items(layers): groups[str(item.get("platform") or "unknown")].append(item)
    def label(item):
        value = item.get("sentiment")
        if isinstance(value, list):
            value = value[0] if value else {}
        return str(value.get("label")) if isinstance(value, dict) else "unknown"
    return [{"platform": key, "count": len(values), "sentiment": Counter(label(i) for i in values)} for key, values in sorted(groups.items())]


def _time_slices(layers):
    groups = defaultdict(int)
    for item in _all_items(layers): groups[str(item.get("timestamp") or "unknown")[:10]] += 1
    return [{"date": key, "count": count} for key, count in sorted(groups.items())]


def _community_slices(layers, coordination, *, snapshot):
    unavailable_reason = _community_slices_unavailable_reason(coordination, snapshot=snapshot)
    if unavailable_reason:
        return [], unavailable_reason

    network = coordination.get("network")
    clusters = network.get("clusters") if isinstance(network, dict) else None
    if not isinstance(clusters, list):
        return [], "coordination_clusters_unavailable"

    items = _all_items(layers)
    available_member_ids = {str(item.get("author_id") or "") for item in items}
    slices = []
    for index, cluster in enumerate(clusters):
        if not isinstance(cluster, dict):
            continue
        members = [member for member in _cluster_members(cluster) if member in available_member_ids]
        if not members:
            continue
        member_ids = set(members)
        member_items = [
            item for item in items
            if str(item.get("author_id") or "") in member_ids
        ]
        slices.append(
            {
                "community_id": str(cluster.get("cluster_id") or cluster.get("id") or index),
                "members": members,
                "member_count": len(members),
                "item_count": len(member_items),
                "sentiment_distribution": _label_distribution(member_items, "sentiment"),
                "stance_distribution": _label_distribution(member_items, "stance"),
                "top_keywords": _top_keywords(member_items),
                "top_topics": _top_topics(member_items),
                "top_entities": _top_entities(member_items),
            }
        )
    if not slices:
        return [], "coordination_clusters_unavailable"
    return slices, None


def _community_slices_unavailable_reason(coordination, *, snapshot):
    if not isinstance(coordination, dict):
        return "coordination_result_unavailable"
    if coordination.get("fallback") is True:
        return "coordination_fallback"
    artifact_dir = str(coordination.get("artifact_dir") or "").strip()
    manifest = coordination.get("artifact_manifest")
    if not artifact_dir or not isinstance(manifest, dict):
        return "coordination_artifact_unavailable"
    if str(manifest.get("data_fingerprint") or "") != str(snapshot.data_fingerprint):
        return "coordination_artifact_snapshot_mismatch"
    return None


def _cluster_members(cluster):
    values = cluster.get("members")
    if not isinstance(values, list):
        return []
    members = []
    seen = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get("account_id") or value.get("id")
        member_id = str(value or "").strip()
        if member_id and member_id not in seen:
            members.append(member_id)
            seen.add(member_id)
    return members


def _label_distribution(items, field):
    return dict(sorted(Counter(_label(item, field) for item in items).items()))


def _top_keywords(items):
    counts = Counter(
        str(keyword.get("term") or "").strip()
        for item in items
        for keyword in item.get("keywords", [])
        if isinstance(keyword, dict) and str(keyword.get("term") or "").strip()
    )
    return [
        {"term": term, "count": count}
        for term, count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:10]
    ]


def _top_topics(items):
    counts = Counter(
        (str(topic.get("id") or ""), str(topic.get("label") or ""))
        for item in items
        for topic in item.get("topics", [])
        if isinstance(topic, dict) and str(topic.get("label") or "").strip()
    )
    return [
        {"id": topic_id, "label": label, "count": count}
        for (topic_id, label), count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0][1], entry[0][0]))[:10]
    ]


def _top_entities(items):
    counts = Counter(
        (str(entity.get("text") or "").strip(), entity.get("label"))
        for item in items
        for entity in item.get("entities", [])
        if isinstance(entity, dict) and str(entity.get("text") or "").strip()
    )
    return [
        {"text": text, "label": label, "count": count}
        for (text, label), count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0][0], str(entry[0][1] or "")))[:10]
    ]


def _path_overlay(linked, evidence_refs, claim):
    timestamps = sorted(
        str(item.get("timestamp") or "")
        for item in linked
        if str(item.get("timestamp") or "")
    )
    return {
        "sentiment": Counter(_label(item, "sentiment") for item in linked),
        "keywords": [keyword for item in linked for keyword in item.get("keywords", [])],
        "topics": [topic for item in linked for topic in item.get("topics", [])],
        "entities": [entity for item in linked for entity in item.get("entities", [])],
        "stance": Counter(_label(item, "stance") for item in linked),
        "platforms": sorted({str(item.get("platform")) for item in linked}),
        "time_range": {"start": timestamps[0], "end": timestamps[-1]} if timestamps else None,
        "associated_claim": claim,
        "evidence_refs": evidence_refs,
    }


def _path_overlays(snapshot, layers, propagation, claim):
    by_ref = _evidence_items_by_ref(layers)
    direct_edges = {
        (str(edge.source_id), str(edge.target_id))
        for edge in snapshot.relationships
        if _is_direct_post_to_comment(edge)
    }
    overlays = []
    for index, path in enumerate(propagation.get("key_paths") or propagation.get("paths") or []):
        nodes = [str(node) for node in path.get("nodes", [])] if isinstance(path, dict) else []
        if len(nodes) != 2 or tuple(nodes) not in direct_edges:
            continue
        source, target = by_ref.get(nodes[0]), by_ref.get(nodes[1])
        if source is None or target is None:
            continue
        linked = [source, target]
        overlays.append({"path_id": str(path.get("path_id") or index), "semantic_overlay": _path_overlay(linked, nodes, claim)})
    return overlays


def _observed_path_overlays(snapshot, layers, claim):
    by_ref = _evidence_items_by_ref(layers)
    overlays = []
    for index, edge in enumerate(snapshot.relationships):
        source, target = by_ref.get(edge.source_id), by_ref.get(edge.target_id)
        if source is None or target is None or not _is_direct_post_to_comment(edge):
            continue
        linked = [source, target]
        overlays.append({"path_id": f"observed_{index}", "source": "snapshot_relationship", "semantic_overlay": _path_overlay(linked, [edge.source_id, edge.target_id], claim)})
    return overlays


def _is_direct_post_to_comment(edge):
    source_parts = str(edge.source_id or "").split(":", 2)
    target_parts = str(edge.target_id or "").split(":", 2)
    return len(source_parts) == 3 and len(target_parts) == 3 and source_parts[1] == "post" and target_parts[1] == "comment"


def _evidence_items_by_ref(layers):
    return {
        f"{item.get('platform')}:{kind}:{item['id']}": item
        for kind, items in (("post", layers["posts"]), ("comment", layers["comments"]))
        for item in items
    }


def _label(item, field):
    value = item.get(field)
    if isinstance(value, list): value = value[0] if value else {}
    return str(value.get("label")) if isinstance(value, dict) else "unknown"


def _json_primitives(value):
    """Normalize pipeline scalar types before artifact persistence.

    Transformers commonly emits NumPy scalar confidences. The runtime boundary
    must turn those into JSON primitives before the AnalysisRegistry hashes and
    chunks the artifact.
    """
    if isinstance(value, dict):
        return {str(key): _json_primitives(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_primitives(item) for item in value]
    if isinstance(value, Counter):
        return {str(key): _json_primitives(item) for key, item in value.items()}
    converter = getattr(value, "item", None)
    if callable(converter) and type(value).__module__.startswith("numpy"):
        return converter()
    return value
