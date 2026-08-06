from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .protocol import DatasetCapability, ResearchDatasetManifest


CRESCI_2017_AUTHORITATIVE_LABEL_SCOPE = "genuine, traditional spambots, and social spambots"
CRESCI_2017_LABEL_SEMANTICS = "social_bot_classification_only:genuine|traditional_spambot|social_spambot"


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _measure_file(path: Path) -> tuple[int, str]:
    before = _file_identity(path)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if _file_identity(path) != before:
        raise ValueError("Cresci source changed during measurement")
    return size, f"sha256:{digest.hexdigest()}"


def _read_measured_bytes(path: Path) -> tuple[bytes, str]:
    before = _file_identity(path)
    with path.open("rb") as handle:
        data = handle.read()
    if _file_identity(path) != before:
        raise ValueError("Cresci source changed during measurement")
    return data, f"sha256:{hashlib.sha256(data).hexdigest()}"


def cresci_capability() -> DatasetCapability:
    return DatasetCapability(
        dataset_id="cresci-2017",
        supports_coordination_discovery=False,
        supports_external_label_evaluation=True,
        supports_campaign_holdout=False,
        supports_time_holdout=False,
        supports_social_bot_classification=True,
        supports_harmful_cib_detection=False,
        supports_campaign_io_evaluation=False,
        blocked_reasons={
            "coordination_discovery": "archive contains bot-classification records, not coordination events",
            "campaign_holdout": "authoritative metadata provides no information-operation campaign axis",
            "observed_time_holdout": "authoritative metadata provides no observed event-time protocol",
            "harmful_cib_detection": "bot labels are not harmful coordinated-influence labels",
            "campaign_io_evaluation": "dataset has no information-operation campaign labels",
        },
        claim_markers=("not_harmful_cib_claim",),
    )


def build_cresci_manifest(
    archive_path: str | Path,
    metadata_path: str | Path,
    *,
    seed: int,
) -> ResearchDatasetManifest:
    archive = Path(archive_path).resolve()
    metadata = Path(metadata_path).resolve()
    metadata_bytes, metadata_checksum = _read_measured_bytes(metadata)
    try:
        document: Any = json.loads(metadata_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("Cresci authoritative metadata is invalid JSON") from exc
    if not isinstance(document, dict) or document.get("schema") != "cogguard.social_bot_detection.dataset_manifest.v1":
        raise ValueError("unsupported Cresci authoritative metadata schema")
    datasets = document.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("Cresci authoritative metadata must contain datasets")
    matches = [entry for entry in datasets if isinstance(entry, dict) and entry.get("id") == "cresci-2017"]
    if len(matches) != 1:
        raise ValueError("authoritative metadata must contain exactly one cresci-2017 entry")
    entry = matches[0]
    if entry.get("file") != archive.name:
        raise ValueError("Cresci archive filename does not match authoritative metadata")
    if isinstance(entry.get("bytes"), bool) or not isinstance(entry.get("bytes"), int):
        raise ValueError("Cresci authoritative byte count must be an integer")
    measured_size, measured_checksum = _measure_file(archive)
    if measured_size != entry["bytes"]:
        raise ValueError("Cresci archive byte count does not match authoritative metadata")
    checksum = entry.get("sha256")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise ValueError("Cresci authoritative SHA-256 is invalid")
    try:
        int(checksum, 16)
    except ValueError as exc:
        raise ValueError("Cresci authoritative SHA-256 is invalid") from exc
    if measured_checksum[7:].casefold() != checksum.casefold():
        raise ValueError("Cresci archive SHA-256 does not match authoritative metadata")
    label_scope = entry.get("label_scope")
    if (
        not isinstance(label_scope, str)
        or label_scope.strip().casefold() != CRESCI_2017_AUTHORITATIVE_LABEL_SCOPE.casefold()
    ):
        raise ValueError("Cresci authoritative label scope must match the bot-only Cresci-2017 semantics")
    archive_key, metadata_key = str(archive), str(metadata)
    return ResearchDatasetManifest(
        dataset_id="cresci-2017",
        seed=seed,
        source_paths=(archive_key, metadata_key),
        source_checksums={
            archive_key: measured_checksum,
            metadata_key: metadata_checksum,
        },
        source_checksum_scope="authoritative_archive_and_metadata",
        label_semantics=CRESCI_2017_LABEL_SEMANTICS,
        sample_count=0,
        source_case_ids=("cresci-2017",),
        campaign_axis=(),
        platform_axis=("twitter",),
        time_axis="not_available_for_observed_time_holdout",
        quality_markers=("sample_count_not_declared",),
        claim_markers=("not_harmful_cib_claim",),
    )


__all__ = [
    "CRESCI_2017_AUTHORITATIVE_LABEL_SCOPE",
    "CRESCI_2017_LABEL_SEMANTICS",
    "build_cresci_manifest",
    "cresci_capability",
]
