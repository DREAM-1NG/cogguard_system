"""Repository-local adapters for public social-bot detection datasets.

The adapters expose raw account text and labels only.  Profile counts,
friend/follower edges, client names, and other supplied metadata are retained
for provenance but are deliberately excluded from the BotRHG model input.
"""

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
from typing import Any, Iterable, Iterator

from .contracts import AccountSample, DatasetManifest
from .dataset import normalize_account_text

__all__ = [
    "load_approved_account_corpus",
    "load_cresci_2015_dataset",
    "load_cresci_2017_dataset",
    "load_midterm_2018_dataset",
    "load_social_dataset",
]


def load_social_dataset(
    dataset_name: str,
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> tuple[list[AccountSample], DatasetManifest]:
    """Load one supported public dataset by its canonical name."""

    loaders = {
        "botection": None,
        "cresci_2015": load_cresci_2015_dataset,
        "cresci_2017": load_cresci_2017_dataset,
        "midterm_2018": load_midterm_2018_dataset,
        "approved_account_corpus": load_approved_account_corpus,
    }
    normalized = dataset_name.strip().lower().replace("-", "_")
    if normalized == "botection":
        from .dataset import load_botection_dataset

        return load_botection_dataset(dataset_root)
    loader = loaders.get(normalized)
    if loader is None:
        raise ValueError(f"unsupported social-bot dataset: {dataset_name}")
    return loader(dataset_root, max_posts_per_account=max_posts_per_account)


def load_approved_account_corpus(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> tuple[list[AccountSample], DatasetManifest]:
    """Load a CogGuard-approved Chinese account corpus export.

    The supervised BotRHG transfer remains binary.  Approved labels with the
    `abstain` training target are retained in the manifest counts and excluded
    from the binary training samples.
    """

    del max_posts_per_account
    root = Path(dataset_root)
    label_path = root if root.is_file() else root / "approved_account_labels.jsonl"
    if not label_path.is_file():
        raise FileNotFoundError(f"approved account corpus JSONL not found: {label_path}")
    manifest_path = label_path.parent / "dataset_manifest.json"
    exported_manifest = _read_json_object(manifest_path) if manifest_path.is_file() else {}
    samples: list[AccountSample] = []
    source_labels: Counter[str] = Counter()
    skipped_abstain = 0
    skipped_empty = 0
    fingerprint = hashlib.sha256()
    with label_path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            fingerprint.update(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
            fingerprint.update(b"\n")
            target = str(payload.get("training_target") or "").strip()
            source_labels[target] += 1
            if target == "abstain":
                skipped_abstain += 1
                continue
            if target not in {"bot", "non_bot"}:
                raise ValueError(f"invalid training_target at line {line_number}: {target!r}")
            normalized = normalize_account_text(str(payload.get("text") or ""))
            if not normalized:
                skipped_empty += 1
                continue
            platform = str(payload.get("platform") or "unknown")
            event_id = str(payload.get("event_id") or "unknown")
            account_id = str(payload.get("account_id") or payload.get("case_id") or line_number)
            samples.append(
                _account_sample(
                    dataset_name="approved_account_corpus",
                    source_label=target,
                    raw_account_id=account_id,
                    label=1 if target == "bot" else 0,
                    text=normalized,
                    post_count=len(payload.get("evidence_post_ids") or []),
                    metadata={
                        "case_id": str(payload.get("case_id") or ""),
                        "event_id": event_id,
                        "platform": platform,
                        "label_id": str(payload.get("label_id") or ""),
                        "case_fingerprint": str(payload.get("case_fingerprint") or ""),
                        "provenance": payload.get("provenance") or {},
                    },
                )
            )
    class_counts = Counter(str(sample.label) for sample in samples)
    return samples, DatasetManifest(
        source_root=str(label_path.parent.resolve()),
        label_file=str(label_path.resolve()),
        text_directory="approved_account_labels.jsonl text field",
        data_fingerprint=str(exported_manifest.get("data_fingerprint") or fingerprint.hexdigest()),
        labeled_account_count=sum(source_labels.values()),
        usable_account_count=len(samples),
        skipped_empty_text_count=skipped_empty + skipped_abstain,
        missing_text_count=0,
        class_counts=dict(sorted(class_counts.items())),
        property_field_coverage={},
        social_graph_coverage="not used by the text-only approved-corpus transfer",
        dataset_name="approved_account_corpus",
        label_provenance="CogGuard analyst-approved or adjudicated account labels; abstain rows excluded from binary supervised training",
        text_provenance="approved_account_labels.jsonl text field from account cases",
        source_archive_sha256=_sha256(label_path),
    )


def load_cresci_2015_dataset(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> tuple[list[AccountSample], DatasetManifest]:
    """Load the five labeled Cresci-2015 subcorpora from the official archive.

    The official semantics are: E13 and TFP are genuine accounts; INT, FSF,
    and TWT are fake-follower accounts.  This source-level label provenance is
    recorded because the archive does not include a separate label column.
    """

    archive = _resolve_archive(dataset_root, "cresci-2015.csv.tar.gz")
    samples: list[AccountSample] = []
    source_labels: Counter[str] = Counter()
    for source_label, users, posts in _iter_cresci_2015_members(archive, max_posts_per_account):
        label = 0 if source_label in {"E13", "TFP"} else 1
        source_labels[source_label] += len(users)
        for raw_id, profile in users.items():
            text_parts = [profile.get("description", ""), *posts.get(raw_id, [])]
            text = normalize_account_text("\n".join(part for part in text_parts if part))
            if not text:
                continue
            samples.append(
                _account_sample(
                    dataset_name="cresci_2015",
                    source_label=source_label,
                    raw_account_id=raw_id,
                    label=label,
                    text=text,
                    post_count=len(posts.get(raw_id, [])),
                    metadata={"profile_fields_available": sorted(profile)},
                )
            )
    return samples, _manifest(
        archive=archive,
        dataset_name="cresci_2015",
        samples=samples,
        label_provenance=(
            "Official CNR/Bot Repository subcorpus semantics: E13 and TFP="
            "genuine (0); INT, FSF and TWT=fake followers (1)."
        ),
        text_provenance="users.description plus raw tweets.text; bounded deterministic tweet sampling",
        source_labels=source_labels,
    )


def load_cresci_2017_dataset(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> tuple[list[AccountSample], DatasetManifest]:
    """Load genuine, fake-follower, social-spambot, and traditional-spambot data."""

    archive = _resolve_archive(dataset_root, "cresci-2017.csv.zip")
    samples: list[AccountSample] = []
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
                posts = defaultdict(list)
                tweets_path = _member_ending(nested.namelist(), "tweets.csv")
                if tweets_path is not None:
                    _read_bounded_tweets(nested, tweets_path, posts, max_posts_per_account)
            label = 0 if source_label == "genuine_accounts" else 1
            source_labels[source_label] += len(users)
            for raw_id, profile in users.items():
                text_parts = [profile.get("description", ""), *posts.get(raw_id, [])]
                text = normalize_account_text("\n".join(part for part in text_parts if part))
                if not text:
                    continue
                samples.append(
                    _account_sample(
                        dataset_name="cresci_2017",
                        source_label=source_label,
                        raw_account_id=raw_id,
                        label=label,
                        text=text,
                        post_count=len(posts.get(raw_id, [])),
                        metadata={"profile_fields_available": sorted(profile)},
                    )
                )
    return samples, _manifest(
        archive=archive,
        dataset_name="cresci_2017",
        samples=samples,
        label_provenance=(
            "Official dataset subcorpus semantics: genuine_accounts=human (0); "
            "fake_followers, social_spambots_* and traditional_spambots_*=bot (1)."
        ),
        text_provenance="users.description plus raw tweets.text; bounded deterministic tweet sampling",
        source_labels=source_labels,
    )


def load_midterm_2018_dataset(
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> tuple[list[AccountSample], DatasetManifest]:
    """Load the Midterm-2018 bot/human labels and profile descriptions."""

    del max_posts_per_account
    archive = _resolve_archive(dataset_root, "midterm-2018.tar.gz")
    with tarfile.open(archive, "r:gz") as tar:
        labels = _read_midterm_labels(tar.extractfile("midterm-2018.tsv"))
        profiles = json.load(tar.extractfile("midterm-2018_processed_user_objects.json"))
    samples: list[AccountSample] = []
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
        text = normalize_account_text(description or fallback)
        if not text:
            continue
        samples.append(
            _account_sample(
                dataset_name="midterm_2018",
                source_label=labels[raw_id],
                raw_account_id=raw_id,
                label=0 if labels[raw_id] == "human" else 1,
                text=text,
                post_count=0,
                metadata={"profile_fields_available": sorted(profile)},
            )
        )
    return samples, _manifest(
        archive=archive,
        dataset_name="midterm_2018",
        samples=samples,
        label_provenance="Official midterm-2018.tsv account-level human/bot labels.",
        text_provenance="processed_user_objects.description, with name/screen_name fallback; no tweet corpus included",
        source_labels=Counter(labels.values()),
    )


def _iter_cresci_2015_members(
    archive: Path,
    max_posts_per_account: int,
) -> Iterator[tuple[str, dict[str, dict[str, str]], dict[str, list[str]]]]:
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
                posts = defaultdict(list)
                tweets_path = _member_ending(nested.namelist(), "tweets.csv")
                if tweets_path is not None:
                    _read_bounded_tweets(nested, tweets_path, posts, max_posts_per_account)
            yield source_label, users, posts


def _read_profile_rows(archive: zipfile.ZipFile, member: str) -> dict[str, dict[str, str]]:
    profiles: dict[str, dict[str, str]] = {}
    with archive.open(member) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8", errors="replace", newline=""))
        for row in reader:
            account_id = str(row.get("id") or row.get("user_id") or "").strip()
            if account_id:
                profiles[account_id] = {
                    "description": str(row.get("description") or "").strip(),
                    "name": str(row.get("name") or "").strip(),
                    "screen_name": str(row.get("screen_name") or "").strip(),
                }
    return profiles


def _read_bounded_tweets(
    archive: zipfile.ZipFile,
    member: str,
    posts: dict[str, list[str]],
    limit: int,
) -> None:
    limit = max(1, int(limit))
    seen_counts: Counter[str] = Counter()
    with archive.open(member) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8", errors="replace", newline=""))
        for row in reader:
            account_id = str(row.get("user_id") or "").strip()
            text = str(row.get("text") or "").strip()
            if not account_id or not text:
                continue
            seen_counts[account_id] += 1
            bucket = posts[account_id]
            if len(bucket) < limit:
                bucket.append(text)
                continue
            # Deterministic reservoir replacement prevents high-volume accounts
            # from retaining only their first posts without storing all tweets.
            digest = hashlib.sha256(
                f"{account_id}:{seen_counts[account_id]}:{text}".encode("utf-8")
            ).digest()
            slot = int.from_bytes(digest[:8], "big") % seen_counts[account_id]
            if slot < limit:
                bucket[slot] = text


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


def _account_sample(
    *,
    dataset_name: str,
    source_label: str,
    raw_account_id: str,
    label: int,
    text: str,
    post_count: int,
    metadata: dict[str, Any],
) -> AccountSample:
    return AccountSample(
        account_id=f"{dataset_name}:{source_label}:{raw_account_id}",
        label=label,
        text=text,
        post_count=post_count,
        source_file_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_encoding="utf-8",
        dataset_name=dataset_name,
        source_label=source_label,
        metadata={"raw_account_id": raw_account_id, **metadata},
        split_group=source_label,
    )


def _manifest(
    *,
    archive: Path,
    dataset_name: str,
    samples: list[AccountSample],
    label_provenance: str,
    text_provenance: str,
    source_labels: Counter[str],
) -> DatasetManifest:
    class_counts = Counter(str(sample.label) for sample in samples)
    return DatasetManifest(
        source_root=str(archive.parent.resolve()),
        label_file=str(archive.resolve()),
        text_directory="embedded archive members",
        data_fingerprint=_sha256(archive),
        labeled_account_count=sum(source_labels.values()),
        usable_account_count=len(samples),
        skipped_empty_text_count=sum(source_labels.values()) - len(samples),
        missing_text_count=0,
        class_counts=dict(sorted(class_counts.items())),
        property_field_coverage={},
        social_graph_coverage="not used by the text-only BotRHG transfer",
        dataset_name=dataset_name,
        label_provenance=label_provenance,
        text_provenance=text_provenance,
        source_archive_sha256=_sha256(archive),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
