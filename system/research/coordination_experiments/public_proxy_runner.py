from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from .runner import CANONICAL_REPRODUCTION_OUTPUT_ROOT


PUBLIC_PROXY_SCHEMA_VERSION = "cogguard.public-coordination-proxy/v1"
PUBLIC_PROXY_METHODS = (
    "system_weighted_evidence",
    "edgebank_binary",
    "unweighted_count",
    "recency_decay",
    "relation_max",
)

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?<!\w)#([\w_]{2,80})", re.UNICODE)
_MENTION_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{2,80})")
_RELATION_WEIGHTS = {
    "url_share": 1.0,
    "hashtag_share": 0.6,
    "retweet_target": 0.9,
    "reply_target": 0.8,
    "quote_target": 0.7,
    "mention_target": 0.4,
}
_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %H:%M",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def _parse_timestamp(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        pass
    for fmt in _TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            continue
    return None


def _tokenize_list_cell(value: str) -> tuple[str, ...]:
    value = (value or "").strip()
    if not value:
        return ()
    cleaned = value.strip("[](){}")
    pieces = re.split(r"[\s,;|]+", cleaned)
    result: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        token = piece.strip().strip("\"'").strip()
        if not token:
            continue
        if token not in seen:
            seen.add(token)
            result.append(token)
    return tuple(result)


def _object_id(prefix: str, value: str) -> str:
    normalized = value.strip().lower()
    return f"{prefix}:{normalized}"


def _relation_objects(row: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    text = row.get("tweet_text") or row.get("content") or ""
    objects: list[tuple[str, str]] = []

    url_values = [*(_tokenize_list_cell(row.get("urls", ""))), *(_URL_RE.findall(text))]
    for key in ("tco1_step1", "tco2_step1", "tco3_step1", "article_url"):
        if row.get(key):
            url_values.extend(_URL_RE.findall(row[key]))
    for url in sorted(set(url_values)):
        objects.append(("url_share", _object_id("url", url)))

    hashtag_values = [*(_tokenize_list_cell(row.get("hashtags", ""))), *(_HASHTAG_RE.findall(text))]
    for tag in sorted(set(hashtag_values)):
        objects.append(("hashtag_share", _object_id("hashtag", tag.lstrip("#"))))

    mention_values = [*(_tokenize_list_cell(row.get("user_mentions", ""))), *(_MENTION_RE.findall(text))]
    for mention in sorted(set(mention_values)):
        objects.append(("mention_target", _object_id("mention", mention.lstrip("@"))))

    for key in ("retweet_tweetid", "retweet_userid"):
        value = row.get(key, "").strip()
        if value:
            objects.append(("retweet_target", _object_id(key, value)))
    for key in ("quoted_tweet_tweetid",):
        value = row.get(key, "").strip()
        if value:
            objects.append(("quote_target", _object_id(key, value)))
    for key in ("in_reply_to_tweetid", "in_reply_to_userid"):
        value = row.get(key, "").strip()
        if value:
            objects.append(("reply_target", _object_id(key, value)))

    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for item in objects:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return tuple(deduped)


def _first_present(row: Mapping[str, str], keys: Sequence[str]) -> str:
    for key in keys:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


@dataclass(frozen=True, slots=True)
class PublicProxyEvent:
    dataset_id: str
    account_id: str
    event_id: str
    timestamp: int
    relation_objects: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PublicProxyDatasetConfig:
    dataset_id: str
    kind: str
    path: str
    limit_rows: int
    max_files: int = 32

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id"))
        if self.kind not in {"twitter_io_zip", "russian_troll_csv_dir", "state_backed_ops_dir"}:
            raise ValueError("unknown public proxy dataset kind")
        object.__setattr__(self, "path", _text(self.path, "path"))
        if self.limit_rows <= 0 or self.max_files <= 0:
            raise ValueError("limit_rows and max_files must be positive")


def _event_from_row(dataset_id: str, row: Mapping[str, str], fallback_index: int) -> PublicProxyEvent | None:
    account_id = _first_present(row, ("userid", "external_author_id", "author", "user_screen_name"))
    timestamp_value = _first_present(row, ("tweet_time", "publish_date", "created_at"))
    timestamp = _parse_timestamp(timestamp_value)
    if not account_id or timestamp is None:
        return None
    objects = _relation_objects(row)
    if not objects:
        return None
    event_id = _first_present(row, ("tweetid", "tweet_id", "id")) or f"row-{fallback_index}"
    return PublicProxyEvent(
        dataset_id=dataset_id,
        account_id=account_id,
        event_id=event_id,
        timestamp=timestamp,
        relation_objects=objects,
    )


def _iter_csv_rows(path: Path) -> Iterable[Mapping[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as stream:
        yield from csv.DictReader(stream)


def _iter_zip_csv_rows(path: Path) -> Iterable[Mapping[str, str]]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        for name in sorted(names):
            with archive.open(name) as raw:
                text = (line.decode("utf-8-sig", errors="replace") for line in raw)
                yield from csv.DictReader(text)


def load_public_proxy_events(config: PublicProxyDatasetConfig) -> tuple[PublicProxyEvent, ...]:
    source = Path(config.path)
    if config.kind == "twitter_io_zip":
        rows = _iter_zip_csv_rows(source)
    elif config.kind == "russian_troll_csv_dir":
        files = sorted(source.glob("IRAhandle_tweets_*.csv"))[: config.max_files]
        rows = (row for file in files for row in _iter_csv_rows(file))
    else:
        candidates = sorted(source.rglob("*.csv"))[: config.max_files]

        def state_rows() -> Iterable[Mapping[str, str]]:
            for file in candidates:
                try:
                    with file.open("r", encoding="utf-8-sig", newline="", errors="replace") as stream:
                        sample = stream.readline()
                        if "tweet_time" not in sample or "tweet_text" not in sample:
                            continue
                        stream.seek(0)
                        yield from csv.DictReader(stream)
                except OSError:
                    continue

        rows = state_rows()

    events: list[PublicProxyEvent] = []
    scanned = 0
    for row in rows:
        scanned += 1
        event = _event_from_row(config.dataset_id, row, scanned)
        if event is not None:
            events.append(event)
        if scanned >= config.limit_rows:
            break
    return tuple(sorted(events, key=lambda event: (event.timestamp, event.account_id, event.event_id)))


def _split_events(events: Sequence[PublicProxyEvent], train_fraction: float) -> tuple[tuple[PublicProxyEvent, ...], tuple[PublicProxyEvent, ...], int]:
    if not 0.1 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be within [0.1, 0.9]")
    if len(events) < 10:
        raise ValueError("public proxy comparison requires at least 10 usable events")
    ordered = tuple(sorted(events, key=lambda event: event.timestamp))
    split_index = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    return ordered[:split_index], ordered[split_index:], ordered[split_index - 1].timestamp


def _pair_occurrences(
    events: Sequence[PublicProxyEvent],
    *,
    window_seconds: int,
    max_accounts_per_object: int,
) -> tuple[dict[tuple[str, str], float], dict[str, dict[tuple[str, str], float]], Counter[str], int]:
    groups: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    relation_counts: Counter[str] = Counter()
    for event in events:
        window = event.timestamp // window_seconds
        for relation, object_id in event.relation_objects:
            relation_counts[relation] += 1
            groups[(relation, object_id, window)].add(event.account_id)

    scores: dict[tuple[str, str], float] = defaultdict(float)
    relation_scores: dict[str, dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
    skipped_groups = 0
    for (relation, _object_id_value, _window), accounts in groups.items():
        if len(accounts) < 2:
            continue
        if len(accounts) > max_accounts_per_object:
            skipped_groups += 1
            continue
        weight = _RELATION_WEIGHTS.get(relation, 0.5)
        for left, right in combinations(sorted(accounts), 2):
            pair = (left, right)
            scores[pair] += weight
            relation_scores[relation][pair] += weight
    frozen_relation_scores = {relation: dict(values) for relation, values in relation_scores.items()}
    return dict(scores), frozen_relation_scores, relation_counts, skipped_groups


def _recency_pair_scores(
    events: Sequence[PublicProxyEvent],
    *,
    cutoff_timestamp: int,
    window_seconds: int,
    max_accounts_per_object: int,
    half_life_seconds: int,
) -> dict[tuple[str, str], float]:
    groups: dict[tuple[str, str, int], list[PublicProxyEvent]] = defaultdict(list)
    for event in events:
        window = event.timestamp // window_seconds
        for relation, object_id in event.relation_objects:
            groups[(relation, object_id, window)].append(event)
    scores: dict[tuple[str, str], float] = defaultdict(float)
    for (relation, _object_id_value, _window), grouped_events in groups.items():
        accounts = sorted({event.account_id for event in grouped_events})
        if len(accounts) < 2 or len(accounts) > max_accounts_per_object:
            continue
        latest_timestamp = max(event.timestamp for event in grouped_events)
        age = max(0, cutoff_timestamp - latest_timestamp)
        decay = 0.5 ** (age / half_life_seconds)
        weight = _RELATION_WEIGHTS.get(relation, 0.5) * decay
        for pair in combinations(accounts, 2):
            scores[pair] += weight
    return dict(scores)


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    order = np.argsort(-scores, kind="mergesort")
    ranked = labels[order]
    positives = int(ranked.sum())
    if positives == 0:
        return float("nan")
    hits = np.cumsum(ranked)
    precision = hits / (np.arange(len(ranked)) + 1)
    return float((precision * ranked).sum() / positives)


def _roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = int(labels.sum())
    negatives = int(len(labels) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=np.float64)
    start = 0
    while start < len(scores):
        end = start + 1
        while end < len(scores) and sorted_scores[end] == sorted_scores[start]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        ranks[order[start:end]] = average_rank
        start = end
    positive_rank_sum = float(ranks[labels == 1].sum())
    return float((positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives))


def _evaluate_scores(
    method_scores: Mapping[tuple[str, str], float],
    positives: set[tuple[str, str]],
    candidate_pairs: Sequence[tuple[str, str]],
) -> dict[str, float]:
    labels = np.asarray([1 if pair in positives else 0 for pair in candidate_pairs], dtype=np.int8)
    scores = np.asarray([float(method_scores.get(pair, 0.0)) for pair in candidate_pairs], dtype=np.float64)
    positives_count = int(labels.sum())
    k = max(1, min(len(candidate_pairs), positives_count))
    order = np.argsort(-scores, kind="mergesort")
    top = labels[order[:k]]
    recall_at_k = float(top.sum() / positives_count) if positives_count else float("nan")
    precision_at_k = float(top.mean()) if len(top) else float("nan")
    return {
        "auprc": _average_precision(labels, scores),
        "roc_auc": _roc_auc(labels, scores),
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
        "candidate_count": float(len(candidate_pairs)),
        "positive_count": float(positives_count),
    }


def _sample_candidates(
    *,
    accounts: Sequence[str],
    positives: set[tuple[str, str]],
    train_pairs: set[tuple[str, str]],
    seed: int,
    negative_multiplier: int,
) -> tuple[tuple[str, str], ...]:
    rng = random.Random(seed)
    candidate_pairs: set[tuple[str, str]] = set(train_pairs) | set(positives)
    target_negatives = max(100, min(100_000, len(positives) * negative_multiplier))
    accounts = tuple(sorted(set(accounts)))
    attempts = 0
    while len(candidate_pairs) < len(train_pairs) + len(positives) + target_negatives and attempts < target_negatives * 20:
        attempts += 1
        left, right = rng.sample(accounts, 2)
        pair = tuple(sorted((left, right)))
        if pair in positives:
            continue
        candidate_pairs.add(pair)
    return tuple(sorted(candidate_pairs))


def run_public_proxy_dataset(
    config: PublicProxyDatasetConfig,
    *,
    train_fraction: float = 0.7,
    window_seconds: int = 3600,
    max_accounts_per_object: int = 50,
    negative_multiplier: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    events = load_public_proxy_events(config)
    train_events, test_events, cutoff = _split_events(events, train_fraction)
    train_scores, train_relation_scores, train_relation_counts, train_skipped_groups = _pair_occurrences(
        train_events,
        window_seconds=window_seconds,
        max_accounts_per_object=max_accounts_per_object,
    )
    test_scores, _test_relation_scores, test_relation_counts, test_skipped_groups = _pair_occurrences(
        test_events,
        window_seconds=window_seconds,
        max_accounts_per_object=max_accounts_per_object,
    )
    positives = set(test_scores)
    accounts = tuple(event.account_id for event in events)
    candidate_pairs = _sample_candidates(
        accounts=accounts,
        positives=positives,
        train_pairs=set(train_scores),
        seed=seed,
        negative_multiplier=negative_multiplier,
    )
    if not positives:
        raise ValueError(f"{config.dataset_id} produced no future coordination proxy positives")

    recency_scores = _recency_pair_scores(
        train_events,
        cutoff_timestamp=cutoff,
        window_seconds=window_seconds,
        max_accounts_per_object=max_accounts_per_object,
        half_life_seconds=24 * 3600,
    )
    unweighted = {pair: 1.0 for pair in train_scores}
    counts = {pair: float(score > 0.0) for pair, score in train_scores.items()}
    relation_max: dict[tuple[str, str], float] = defaultdict(float)
    for relation_values in train_relation_scores.values():
        for pair, value in relation_values.items():
            relation_max[pair] = max(relation_max[pair], value)

    methods = {
        "system_weighted_evidence": train_scores,
        "edgebank_binary": unweighted,
        "unweighted_count": counts,
        "recency_decay": recency_scores,
        "relation_max": dict(relation_max),
    }
    method_metrics = {
        method_id: _evaluate_scores(scores, positives, candidate_pairs)
        for method_id, scores in methods.items()
    }
    event_range = {
        "min_timestamp": min(event.timestamp for event in events),
        "max_timestamp": max(event.timestamp for event in events),
        "cutoff_timestamp": cutoff,
    }
    payload = {
        "dataset_id": config.dataset_id,
        "source_path": config.path,
        "limit_rows": config.limit_rows,
        "max_files": config.max_files,
        "event_count": len(events),
        "account_count": len(set(accounts)),
        "train_event_count": len(train_events),
        "test_event_count": len(test_events),
        "train_pair_count": len(train_scores),
        "test_positive_pair_count": len(positives),
        "candidate_pair_count": len(candidate_pairs),
        "event_range": event_range,
        "train_relation_counts": dict(sorted(train_relation_counts.items())),
        "test_relation_counts": dict(sorted(test_relation_counts.items())),
        "train_skipped_groups": train_skipped_groups,
        "test_skipped_groups": test_skipped_groups,
        "methods": method_metrics,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def validate_public_proxy_output_dir(output_dir: str | Path) -> Path:
    candidate = Path(output_dir)
    if not candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError("output_dir must be an absolute descendant of the canonical reproduction output root")
    resolved = candidate.resolve(strict=False)
    root = CANONICAL_REPRODUCTION_OUTPUT_ROOT.resolve(strict=False)
    if resolved.drive.upper() != "G:" or root.drive.upper() != "G:":
        raise ValueError("output_dir must stay on G:")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("output_dir must stay below the canonical reproduction output root") from exc
    if resolved == root:
        raise ValueError("output_dir must be a child directory")
    return resolved


def run_public_proxy_comparison(
    configs: Sequence[PublicProxyDatasetConfig],
    output_dir: str | Path,
    *,
    train_fraction: float = 0.7,
    window_seconds: int = 3600,
    max_accounts_per_object: int = 50,
    negative_multiplier: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    output = validate_public_proxy_output_dir(output_dir)
    rows = [
        run_public_proxy_dataset(
            config,
            train_fraction=train_fraction,
            window_seconds=window_seconds,
            max_accounts_per_object=max_accounts_per_object,
            negative_multiplier=negative_multiplier,
            seed=seed,
        )
        for config in configs
    ]
    manifest = {
        "schema_version": PUBLIC_PROXY_SCHEMA_VERSION,
        "evaluation_scope": "future_coordination_pair_recovery_proxy_not_harmful_detection",
        "method_ids": list(PUBLIC_PROXY_METHODS),
        "config": {
            "train_fraction": train_fraction,
            "window_seconds": window_seconds,
            "max_accounts_per_object": max_accounts_per_object,
            "negative_multiplier": negative_multiplier,
            "seed": seed,
        },
        "rows": rows,
    }
    manifest["fingerprint"] = _fingerprint(manifest)
    _atomic_write_json(output / "public_proxy_manifest.json", manifest)

    table_rows: list[dict[str, Any]] = []
    for row in rows:
        for method_id, metrics in row["methods"].items():
            table_rows.append(
                {
                    "dataset_id": row["dataset_id"],
                    "method_id": method_id,
                    **metrics,
                    "event_count": row["event_count"],
                    "account_count": row["account_count"],
                    "train_pair_count": row["train_pair_count"],
                    "test_positive_pair_count": row["test_positive_pair_count"],
                }
            )
    csv_path = output / "public_proxy_table.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = (
            "dataset_id",
            "method_id",
            "auprc",
            "roc_auc",
            "recall_at_k",
            "precision_at_k",
            "candidate_count",
            "positive_count",
            "event_count",
            "account_count",
            "train_pair_count",
            "test_positive_pair_count",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(table_rows)
    return manifest


def default_local_public_proxy_configs(*, limit_rows: int = 50_000) -> tuple[PublicProxyDatasetConfig, ...]:
    return (
        PublicProxyDatasetConfig(
            dataset_id="twitter_io_ira_2018_10",
            kind="twitter_io_zip",
            path="G:/CISCN/dataset/twitter_io/2018_10/ira/ira_tweets_csv_hashed.zip",
            limit_rows=limit_rows,
            max_files=1,
        ),
        PublicProxyDatasetConfig(
            dataset_id="fivethirtyeight_russian_troll_tweets",
            kind="russian_troll_csv_dir",
            path="G:/CISCN/dataset/russian-troll-tweets",
            limit_rows=limit_rows,
            max_files=13,
        ),
        PublicProxyDatasetConfig(
            dataset_id="twitter_state_backed_ops_sample",
            kind="state_backed_ops_dir",
            path="G:/CISCN/dataset/TwitterStateBackedOps/datasets",
            limit_rows=limit_rows,
            max_files=16,
        ),
    )


__all__ = [
    "PUBLIC_PROXY_METHODS",
    "PUBLIC_PROXY_SCHEMA_VERSION",
    "PublicProxyDatasetConfig",
    "PublicProxyEvent",
    "default_local_public_proxy_configs",
    "load_public_proxy_events",
    "run_public_proxy_comparison",
    "run_public_proxy_dataset",
    "validate_public_proxy_output_dir",
]
