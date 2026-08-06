from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .protocol import DatasetCapability, ResearchDatasetManifest


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


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
    try:
        document: Any = json.loads(metadata.read_text(encoding="utf-8"))
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
    if archive.stat().st_size != entry["bytes"]:
        raise ValueError("Cresci archive byte count does not match authoritative metadata")
    checksum = entry.get("sha256")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise ValueError("Cresci authoritative SHA-256 is invalid")
    label_scope = entry.get("label_scope")
    if not isinstance(label_scope, str) or not label_scope.strip():
        raise ValueError("Cresci authoritative label scope is missing")
    archive_key, metadata_key = str(archive), str(metadata)
    return ResearchDatasetManifest(
        dataset_id="cresci-2017",
        seed=seed,
        source_paths=(archive_key, metadata_key),
        source_checksums={
            archive_key: f"sha256:{checksum.lower()}",
            metadata_key: _file_sha256(metadata),
        },
        source_checksum_scope="authoritative_archive_and_metadata",
        label_semantics=label_scope.strip(),
        sample_count=0,
        source_case_ids=("cresci-2017",),
        campaign_axis=(),
        platform_axis=("twitter",),
        time_axis="not_available_for_observed_time_holdout",
        quality_markers=("sample_count_not_declared",),
        claim_markers=("not_harmful_cib_claim",),
    )


__all__ = ["build_cresci_manifest", "cresci_capability"]
