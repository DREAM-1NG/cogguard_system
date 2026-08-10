"""Strict BotRHG corpus loaders for paper-faithful dataset adaptation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import tarfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .contracts import DatasetManifest
from .datasets import load_approved_account_corpus
from .strict_contracts import StrictAccountRecord, StrictCorpus, StrictGraph, StrictRelationEdge
from .strict_features import STRICT_CATEGORICAL_FIELDS, STRICT_NUMERIC_FIELDS, feature_coverage, linearize_account_text, normalize_nlpcc_text, parse_timestamp, sample_texts

__all__ = [
    "load_strict_cresci_2015_corpus",
    "load_strict_cresci_2017_corpus",
    "load_strict_midterm_2018_corpus",
    "load_strict_approved_account_corpus",
    "load_strict_social_corpus",
]


def load_strict_social_corpus(
    dataset_name: str,
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> StrictCorpus:
    """Load one supported public corpus using the strict BotRHG contract."""

    normalized = dataset_name.strip().lower().replace("-", "_")
    loaders = {
        "cresci_2015": load_strict_cresci_2015_corpus,
        "cresci_2017": load_strict_cresci_2017_corpus,
        "midterm_2018": load_strict_midterm_2018_corpus,
        "approved_account_corpus": load_strict_approved_account_corpus,
    }
    try:
        loader = loaders[normalized]
    except KeyError as error:
        valid = ", ".join(sorted(loaders))
        raise ValueError(f"unsupported strict social-bot dataset: {dataset_name}. Expected one of: {valid}") from error
    return loader(dataset_root, max_posts_per_account=max_posts_per_account)


def load_strict_approved_account_corpus(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> StrictCorpus:
    """Adapt the governed Chinese approved corpus without inventing features."""

    samples, manifest = load_approved_account_corpus(
        dataset_root,
        max_posts_per_account=max_posts_per_account,
    )
    records = [
        StrictAccountRecord(
            account_id=sample.account_id,
            label=sample.label,
            text=sample.text,
            post_count=sample.post_count,
            source_file_hash=sample.source_file_hash,
            source_encoding=sample.source_encoding,
            dataset_name=sample.dataset_name,
            source_label=sample.source_label,
            metadata=sample.metadata,
            split_group=sample.split_group,
            numeric_features={},
            categorical_features={},
        )
        for sample in samples
    ]
    return StrictCorpus(
        records=records,
        graph=StrictGraph(
            node_ids=tuple(record.account_id for record in records),
            edges=(),
            relation_types=(),
            available=False,
        ),
        manifest=manifest,
    )


def load_strict_cresci_2015_corpus(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> StrictCorpus:
    archive = _resolve_archive(dataset_root, "cresci-2015.csv.tar.gz")
    records: list[StrictAccountRecord] = []
    edges: list[StrictRelationEdge] = []
    source_labels: Counter[str] = Counter()
    with tarfile.open(archive, "r:gz") as outer:
        for member in outer.getmembers():
            if not member.name.endswith(".csv.zip"):
                continue
            source_label = Path(member.name).stem.replace(".csv", "")
            nested_bytes = outer.extractfile(member).read()
            with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested:
                users_path = _member_ending(nested.namelist(), "users.csv")
                if users_path is None:
                    continue
                users = _read_profile_rows(nested, users_path)
                tweets_path = _member_ending(nested.namelist(), "tweets.csv")
                tweets_by_account, tweet_rows, tweet_stats = _read_bounded_tweets(
                    nested,
                    tweets_path,
                    max_posts_per_account=max_posts_per_account,
                ) if tweets_path is not None else (defaultdict(list), defaultdict(list), defaultdict(dict))
                source_labels[source_label] += len(users)
                for raw_id, profile in users.items():
                    text = _compose_account_text(profile, tweets_by_account.get(raw_id, []))
                    if not text:
                        continue
                    account_id = _account_id("cresci_2015", source_label, raw_id)
                    records.append(
                        StrictAccountRecord(
                            account_id=account_id,
                            label=0 if source_label in {"E13", "TFP"} else 1,
                            text=text,
                            post_count=len(tweets_by_account.get(raw_id, [])),
                            source_file_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            source_encoding="utf-8",
                            dataset_name="cresci_2015",
                            source_label=source_label,
                            metadata={"raw_account_id": raw_id, "profile_fields_available": sorted(profile)},
                            split_group=source_label,
                            numeric_features=_numeric_features(profile, tweets_by_account.get(raw_id, []), tweet_stats.get(raw_id, {})),
                            categorical_features=_categorical_features(profile, source_label),
                        )
                    )
                edges.extend(
                    _build_member_edges(
                        nested,
                        users,
                        source_label=source_label,
                        dataset_name="cresci_2015",
                        relation_files=("followers.csv", "friends.csv"),
                    )
                )
    graph = _build_graph(records, edges, available=bool(edges), relation_types=("followers", "friends"))
    manifest = _manifest(
        archive=archive,
        dataset_name="cresci_2015",
        records=records,
        label_provenance=(
            "Official CNR/Bot Repository subcorpus semantics: E13 and TFP=genuine (0); "
            "INT, FSF and TWT=fake followers (1)."
        ),
        text_provenance="users + tweets with deterministic bounded sampling",
        source_labels=source_labels,
        graph_coverage="available: followers/friends + tweet text",
    )
    return StrictCorpus(records=records, graph=graph, manifest=manifest)


def load_strict_cresci_2017_corpus(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> StrictCorpus:
    archive = _resolve_archive(dataset_root, "cresci-2017.csv.zip")
    records: list[StrictAccountRecord] = []
    edges: list[StrictRelationEdge] = []
    source_labels: Counter[str] = Counter()
    with zipfile.ZipFile(archive) as outer:
        for member in outer.infolist():
            source_label = _cresci_2017_label(member.filename)
            if source_label is None:
                continue
            with outer.open(member) as nested_stream:
                nested_bytes = nested_stream.read()
            with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested:
                users_path = _member_ending(nested.namelist(), "users.csv")
                if users_path is None:
                    continue
                users = _read_profile_rows(nested, users_path)
                tweets_path = _member_ending(nested.namelist(), "tweets.csv")
                tweets_by_account, tweet_rows, tweet_stats = _read_bounded_tweets(
                    nested,
                    tweets_path,
                    max_posts_per_account=max_posts_per_account,
                ) if tweets_path is not None else (defaultdict(list), defaultdict(list), defaultdict(dict))
            source_labels[source_label] += len(users)
            for raw_id, profile in users.items():
                text = _compose_account_text(profile, tweets_by_account.get(raw_id, []))
                if not text:
                    continue
                account_id = _account_id("cresci_2017", source_label, raw_id)
                records.append(
                    StrictAccountRecord(
                        account_id=account_id,
                        label=0 if source_label == "genuine_accounts" else 1,
                        text=text,
                        post_count=len(tweets_by_account.get(raw_id, [])),
                        source_file_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        source_encoding="utf-8",
                        dataset_name="cresci_2017",
                        source_label=source_label,
                        metadata={"raw_account_id": raw_id, "profile_fields_available": sorted(profile)},
                        split_group=source_label,
                        numeric_features=_numeric_features(profile, tweets_by_account.get(raw_id, []), tweet_stats.get(raw_id, {})),
                        categorical_features=_categorical_features(profile, source_label),
                    )
                )
            edges.extend(
                _build_tweet_interaction_edges(
                    tweets_by_account=tweets_by_account,
                    tweet_rows=tweet_rows,
                    dataset_name="cresci_2017",
                    source_label=source_label,
                    users=users,
                )
            )
    graph = _build_graph(records, edges, available=bool(edges), relation_types=("reply", "retweet"))
    manifest = _manifest(
        archive=archive,
        dataset_name="cresci_2017",
        records=records,
        label_provenance=(
            "Official dataset subcorpus semantics: genuine_accounts=human (0); "
            "fake_followers, social_spambots_* and traditional_spambots_*=bot (1)."
        ),
        text_provenance="users + tweets with deterministic bounded sampling",
        source_labels=source_labels,
        graph_coverage="available: reply/retweet interactions derived from tweets",
    )
    return StrictCorpus(records=records, graph=graph, manifest=manifest)


def load_strict_midterm_2018_corpus(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> StrictCorpus:
    del max_posts_per_account
    archive = _resolve_archive(dataset_root, "midterm-2018.tar.gz")
    with tarfile.open(archive, "r:gz") as tar:
        labels = _read_midterm_labels(tar.extractfile("midterm-2018.tsv"))
        profiles = json.load(tar.extractfile("midterm-2018_processed_user_objects.json"))
    records: list[StrictAccountRecord] = []
    source_labels: Counter[str] = Counter(labels.values())
    for profile in profiles:
        raw_id = str(profile.get("user_id") or "").strip()
        if not raw_id or raw_id not in labels:
            continue
        description = str(profile.get("description") or "").strip()
        fallback = " ".join(
            str(profile.get(field) or "").strip()
            for field in ("name", "screen_name")
            if str(profile.get(field) or "").strip()
        )
        text = normalize_nlpcc_text(description or fallback)
        if not text:
            continue
        account_id = _account_id("midterm_2018", "midterm", raw_id)
        profile_fields = sorted(profile)
        records.append(
            StrictAccountRecord(
                account_id=account_id,
                label=0 if labels[raw_id] == "human" else 1,
                text=text,
                post_count=0,
                source_file_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                source_encoding="utf-8",
                dataset_name="midterm_2018",
                source_label=labels[raw_id],
                metadata={"raw_account_id": raw_id, "profile_fields_available": profile_fields},
                split_group=labels[raw_id],
                numeric_features=_numeric_features(profile, [], {}, probe_timestamp=profile.get("probe_timestamp"), user_created_at=profile.get("user_created_at")),
                categorical_features=_categorical_features(profile, labels[raw_id]),
            )
        )
    graph = _build_graph(records, [], available=False, relation_types=())
    manifest = _manifest(
        archive=archive,
        dataset_name="midterm_2018",
        records=records,
        label_provenance="Official midterm-2018.tsv account-level human/bot labels.",
        text_provenance="processed_user_objects.description, with name/screen_name fallback; no tweet corpus included",
        source_labels=source_labels,
        graph_coverage="unavailable",
    )
    return StrictCorpus(records=records, graph=graph, manifest=manifest)


def _compose_account_text(profile: dict[str, str], tweets: list[str]) -> str:
    profile_parts = [
        f"Name: {profile.get('name', '').strip()}",
        f"Screen name: {profile.get('screen_name', '').strip()}",
        f"Created at: {profile.get('created_at', '').strip()}",
        f"Followers count: {profile.get('followers_count', '').strip()}",
        f"Friends count: {profile.get('friends_count', '').strip()}",
        f"Statuses count: {profile.get('statuses_count', '').strip()}",
        f"Listed count: {profile.get('listed_count', '').strip()}",
        f"Verified: {profile.get('verified', '').strip()}",
        f"Protected: {profile.get('protected', '').strip()}",
    ]
    description = str(profile.get("description") or "").strip()
    return linearize_account_text(profile_parts, description, sample_texts(tweets, 8))


def _numeric_features(
    profile: dict[str, str],
    tweets: list[str],
    tweet_stats: dict[str, Any],
    *,
    probe_timestamp: Any | None = None,
    user_created_at: Any | None = None,
) -> dict[str, float]:
    texts = [normalize_nlpcc_text(text) for text in tweets if normalize_nlpcc_text(text)]
    duplicate_ratio = 0.0
    if texts:
        counts = Counter(texts)
        duplicate_ratio = 1.0 - len(counts) / max(len(texts), 1)
    total_chars = [len(text) for text in texts if text]
    tweet_count = float(len(texts))
    avg_tweet_length = float(sum(total_chars) / max(len(total_chars), 1)) if total_chars else 0.0
    url_rate = float(tweet_stats.get("url_rate", 0.0))
    mention_rate = float(tweet_stats.get("mention_rate", 0.0))
    hashtag_rate = float(tweet_stats.get("hashtag_rate", 0.0))
    reply_rate = float(tweet_stats.get("reply_rate", 0.0))
    retweet_rate = float(tweet_stats.get("retweet_rate", 0.0))
    followers_count = _coerce_float(profile.get("followers_count"))
    friends_count = _coerce_float(profile.get("friends_count"))
    statuses_count = _coerce_float(profile.get("statuses_count"))
    favourites_count = _coerce_float(profile.get("favourites_count"))
    listed_count = _coerce_float(profile.get("listed_count"))
    description_length = float(len(str(profile.get("description") or "").strip()))
    account_age_days = _account_age_days(probe_timestamp or profile.get("crawled_at") or profile.get("updated") or profile.get("timestamp"), user_created_at or profile.get("created_at"))
    return {
        "followers_count": followers_count,
        "friends_count": friends_count,
        "statuses_count": statuses_count,
        "favourites_count": favourites_count,
        "listed_count": listed_count,
        "post_count": tweet_count,
        "description_length": description_length,
        "avg_tweet_length": avg_tweet_length,
        "duplicate_ratio": duplicate_ratio,
        "url_rate": url_rate,
        "mention_rate": mention_rate,
        "hashtag_rate": hashtag_rate,
        "reply_rate": reply_rate,
        "retweet_rate": retweet_rate,
        "account_age_days": account_age_days,
    }


def _categorical_features(profile: dict[str, Any], source_label: str) -> dict[str, str]:
    # Dataset partition labels are provenance, never model features.
    del source_label
    return {
        "verified": _coerce_bool(profile.get("verified")),
        "protected": _coerce_bool(profile.get("protected")),
        "geo_enabled": _coerce_bool(profile.get("geo_enabled")),
        "default_profile": _coerce_bool(profile.get("default_profile")),
        "default_profile_image": _coerce_bool(profile.get("default_profile_image")),
        "profile_use_background_image": _coerce_bool(profile.get("profile_use_background_image")),
        "lang": str(profile.get("lang") or "").strip().lower(),
        "time_zone": str(profile.get("time_zone") or "").strip(),
    }


def _build_member_edges(
    archive: zipfile.ZipFile,
    users: dict[str, dict[str, str]],
    *,
    source_label: str,
    dataset_name: str,
    relation_files: tuple[str, ...],
) -> list[StrictRelationEdge]:
    edges: list[StrictRelationEdge] = []
    valid_ids = {raw_id for raw_id in users}
    for relation_file in relation_files:
        member = _member_ending(archive.namelist(), relation_file)
        if member is None:
            continue
        relation_type = relation_file.removesuffix(".csv")
        with archive.open(member) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8", errors="replace", newline=""))
            for row in reader:
                source_id = str(row.get("source_id") or row.get("source") or "").strip()
                target_id = str(row.get("target_id") or row.get("target") or "").strip()
                if not source_id or not target_id:
                    continue
                if source_id not in valid_ids or target_id not in valid_ids:
                    continue
                edges.append(
                    StrictRelationEdge(
                        source_account_id=_account_id(dataset_name, source_label, source_id),
                        target_account_id=_account_id(dataset_name, source_label, target_id),
                        relation_type=relation_type,
                    )
                )
    return edges


def _build_tweet_interaction_edges(
    *,
    tweets_by_account: dict[str, list[str]],
    tweet_rows: dict[str, list[dict[str, str]]],
    dataset_name: str,
    source_label: str,
    users: dict[str, dict[str, str]],
) -> list[StrictRelationEdge]:
    valid_ids = {raw_id for raw_id in users}
    edges: list[StrictRelationEdge] = []
    tweet_to_author: dict[str, str] = {}
    for author_id, rows in tweet_rows.items():
        for row in rows:
            tweet_id = str(row.get("id") or "").strip()
            if tweet_id:
                tweet_to_author[tweet_id] = author_id
    for author_id, rows in tweet_rows.items():
        if author_id not in valid_ids:
            continue
        for row in rows:
            reply_to = str(row.get("in_reply_to_user_id") or "").strip()
            if reply_to and reply_to in valid_ids and reply_to != author_id:
                edges.append(
                    StrictRelationEdge(
                        source_account_id=_account_id(dataset_name, source_label, author_id),
                        target_account_id=_account_id(dataset_name, source_label, reply_to),
                        relation_type="reply",
                    )
                )
            retweet_status = str(row.get("retweeted_status_id") or "").strip()
            if retweet_status and retweet_status in tweet_to_author:
                target_author = tweet_to_author[retweet_status]
                if target_author in valid_ids and target_author != author_id:
                    edges.append(
                        StrictRelationEdge(
                            source_account_id=_account_id(dataset_name, source_label, author_id),
                            target_account_id=_account_id(dataset_name, source_label, target_author),
                            relation_type="retweet",
                        )
                    )
    return edges


def _read_profile_rows(archive: zipfile.ZipFile, member: str) -> dict[str, dict[str, str]]:
    profiles: dict[str, dict[str, str]] = {}
    with archive.open(member) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8", errors="replace", newline=""))
        for row in reader:
            account_id = str(row.get("id") or row.get("user_id") or "").strip()
            if account_id:
                profiles[account_id] = {key: str(value or "").strip() for key, value in row.items()}
    return profiles


def _read_bounded_tweets(
    archive: zipfile.ZipFile,
    member: str | None,
    *,
    max_posts_per_account: int,
) -> tuple[dict[str, list[str]], dict[str, list[dict[str, str]]], dict[str, dict[str, float]]]:
    posts: dict[str, list[str]] = defaultdict(list)
    tweet_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    tweet_stats: dict[str, dict[str, float]] = defaultdict(lambda: {
        "url_rate": 0.0,
        "mention_rate": 0.0,
        "hashtag_rate": 0.0,
        "reply_rate": 0.0,
        "retweet_rate": 0.0,
        "tweet_count": 0.0,
    })
    if member is None:
        return posts, tweet_rows, tweet_stats
    limit = max(1, int(max_posts_per_account))
    seen_counts: Counter[str] = Counter()
    with archive.open(member) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8", errors="replace", newline=""))
        for row in reader:
            account_id = str(row.get("user_id") or "").strip()
            text = normalize_nlpcc_text(str(row.get("text") or "").strip())
            if not account_id or not text:
                continue
            tweet_rows[account_id].append({key: str(value or "").strip() for key, value in row.items()})
            stats = tweet_stats[account_id]
            stats["tweet_count"] += 1.0
            stats["url_rate"] += 1.0 if "HTTPURL" in text.upper() else 0.0
            stats["mention_rate"] += 1.0 if "@USER" in text.upper() else 0.0
            stats["hashtag_rate"] += 1.0 if "#HASHTAG" in text.upper() else 0.0
            stats["reply_rate"] += 1.0 if str(row.get("in_reply_to_user_id") or "").strip() else 0.0
            stats["retweet_rate"] += 1.0 if str(row.get("retweeted_status_id") or "").strip() else 0.0
            seen_counts[account_id] += 1
            bucket = posts[account_id]
            if len(bucket) < limit:
                bucket.append(text)
                continue
            digest = hashlib.sha256(f"{account_id}:{seen_counts[account_id]}:{text}".encode("utf-8")).digest()
            slot = int.from_bytes(digest[:8], "big") % seen_counts[account_id]
            if slot < limit:
                bucket[slot] = text
    for account_id, stats in tweet_stats.items():
        count = max(stats["tweet_count"], 1.0)
        for key in ("url_rate", "mention_rate", "hashtag_rate", "reply_rate", "retweet_rate"):
            stats[key] = float(stats[key] / count)
    return posts, tweet_rows, tweet_stats


def _read_midterm_labels(stream: Any) -> dict[str, str]:
    labels: dict[str, str] = {}
    for line in stream:
        decoded = line.decode("utf-8-sig", errors="replace").strip()
        if not decoded:
            continue
        fields = decoded.split("\t")
        if len(fields) != 2 or fields[1] not in {"bot", "human"}:
            raise ValueError(f"invalid Midterm-2018 label row: {decoded!r}")
        labels[fields[0].strip()] = fields[1]
    return labels


def _build_graph(
    records: list[StrictAccountRecord],
    edges: list[StrictRelationEdge],
    *,
    available: bool,
    relation_types: tuple[str, ...],
) -> StrictGraph:
    node_ids = tuple(record.account_id for record in records)
    unique_relations = relation_types or tuple(sorted({edge.relation_type for edge in edges}))
    return StrictGraph(node_ids=node_ids, edges=tuple(edges), relation_types=unique_relations, available=available and bool(edges))


def _manifest(
    *,
    archive: Path,
    dataset_name: str,
    records: list[StrictAccountRecord],
    label_provenance: str,
    text_provenance: str,
    source_labels: Counter[str],
    graph_coverage: str,
) -> DatasetManifest:
    class_counts = Counter(str(record.label) for record in records)
    return DatasetManifest(
        source_root=str(archive.parent.resolve()),
        label_file=str(archive.resolve()),
        text_directory="embedded archive members",
        data_fingerprint=_sha256(archive),
        labeled_account_count=sum(source_labels.values()),
        usable_account_count=len(records),
        skipped_empty_text_count=sum(source_labels.values()) - len(records),
        missing_text_count=0,
        class_counts=dict(sorted(class_counts.items())),
        property_field_coverage={
            **feature_coverage(records, STRICT_NUMERIC_FIELDS, numeric=True),
            **feature_coverage(records, STRICT_CATEGORICAL_FIELDS, numeric=False),
        },
        social_graph_coverage=graph_coverage,
        dataset_name=dataset_name,
        label_provenance=label_provenance,
        text_provenance=text_provenance,
        source_archive_sha256=_sha256(archive),
    )


def _resolve_archive(root: str | Path, filename: str) -> Path:
    path = Path(root)
    if path.is_file():
        return path
    candidate = path / filename
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"dataset archive not found: {candidate}")


def _member_ending(names: Iterable[str], suffix: str) -> str | None:
    return next((name for name in names if name.endswith(suffix) and "__MACOSX" not in name), None)


def _cresci_2017_label(name: str) -> str | None:
    match = re.search(
        r"(?:^|/)(genuine_accounts|fake_followers|social_spambots_[1-3]|traditional_spambots_[1-4])\.csv\.zip$",
        name,
    )
    return match.group(1) if match else None


def _account_id(dataset_name: str, source_label: str, raw_account_id: str) -> str:
    return f"{dataset_name}:{source_label}:{raw_account_id}"


def _coerce_float(value: Any) -> float:
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_bool(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return "true"
    if text in {"0", "false", "f", "no", "n"}:
        return "false"
    return text


def _account_age_days(reference: Any, created_at: Any) -> float:
    reference_ts = parse_timestamp(reference)
    created_ts = parse_timestamp(created_at)
    if reference_ts is None or created_ts is None:
        return 0.0
    delta = reference_ts - created_ts
    return float(max(delta.total_seconds() / 86400.0, 0.0))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
