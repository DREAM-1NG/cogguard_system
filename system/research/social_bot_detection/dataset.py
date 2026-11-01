"""Botection Weibo loader with deterministic provenance tracking."""

from __future__ import annotations

import hashlib
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .contracts import AccountSample, DatasetManifest

__all__ = ["load_botection_dataset", "load_social_dataset", "normalize_account_text", "split_samples"]


def load_social_dataset(
    dataset_name: str,
    dataset_root: str | Path,
    *,
    max_posts_per_account: int = 64,
) -> tuple[list[AccountSample], DatasetManifest]:
    """Dispatch to a repository-local public dataset adapter."""

    from .datasets import load_social_dataset as _load_social_dataset

    return _load_social_dataset(
        dataset_name,
        dataset_root,
        max_posts_per_account=max_posts_per_account,
    )


def load_botection_dataset(dataset_root: str | Path) -> tuple[list[AccountSample], DatasetManifest]:
    """Load labeled Botection accounts and their UTF-8 Weibo posts.

    The published corpus stores text in UTF-8 despite the surrounding legacy
    project files using mixed encodings.  Decoding is therefore explicit and
    never uses ``errors='ignore'``; invalid bytes are replaced and counted.
    """

    root = Path(dataset_root)
    label_path = _find_first(root, "dataset/bot label.xlsx", "dataset/final data.xlsx")
    text_dir = _find_directory(root, "dataset/data", "textual_network_training/data")
    if label_path is None:
        raise FileNotFoundError(f"labeled workbook not found under {root}")
    if text_dir is None:
        raise FileNotFoundError(f"account text directory not found under {root}")

    labels = _read_workbook_rows(label_path)
    samples: list[AccountSample] = []
    missing = 0
    empty = 0
    fingerprint = hashlib.sha256()
    for account_id, label in labels:
        source = text_dir / f"{account_id}.txt"
        if not source.exists():
            missing += 1
            continue
        raw = source.read_bytes()
        fingerprint.update(account_id.encode("utf-8"))
        fingerprint.update(str(label).encode("ascii"))
        fingerprint.update(hashlib.sha256(raw).digest())
        text = raw.decode("utf-8", errors="replace")
        normalized = normalize_account_text(text)
        if not normalized:
            empty += 1
            continue
        samples.append(
            AccountSample(
                account_id=account_id,
                label=label,
                text=normalized,
                post_count=len([line for line in normalized.split("\n") if line]),
                source_file_hash=hashlib.sha256(raw).hexdigest(),
                source_encoding="utf-8",
            )
        )

    counts = Counter(str(item.label) for item in samples)
    manifest = DatasetManifest(
        source_root=str(root.resolve()),
        label_file=str(label_path.resolve()),
        text_directory=str(text_dir.resolve()),
        data_fingerprint=fingerprint.hexdigest(),
        labeled_account_count=len(labels),
        usable_account_count=len(samples),
        skipped_empty_text_count=empty,
        missing_text_count=missing,
        class_counts=dict(sorted(counts.items())),
        property_field_coverage={},
        social_graph_coverage="unavailable in Botection text corpus",
        dataset_name="botection",
        label_provenance="Botection workbook label column",
        text_provenance="UTF-8 account text files",
    )
    return samples, manifest


def normalize_account_text(text: str) -> str:
    """Normalize post boundaries without converting content to hand features."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def split_samples(
    samples: list[AccountSample],
    *,
    validation_size: float = 0.15,
    test_size: float = 0.20,
    seed: int = 42,
) -> dict[str, list[AccountSample]]:
    """Create deterministic stratified train/validation/test account splits."""

    if validation_size < 0 or test_size < 0 or validation_size + test_size >= 1:
        raise ValueError("validation_size and test_size must be non-negative and sum below one")
    if len(samples) < 4:
        raise ValueError("at least four labeled accounts are required for a split")
    from sklearn.model_selection import train_test_split

    indices = list(range(len(samples)))
    labels = [item.label for item in samples]
    train_idx, holdout_idx = train_test_split(
        indices,
        test_size=validation_size + test_size,
        random_state=seed,
        stratify=labels,
    )
    holdout_labels = [labels[index] for index in holdout_idx]
    relative_test = test_size / (validation_size + test_size)
    validation_idx, test_idx = train_test_split(
        holdout_idx,
        test_size=relative_test,
        random_state=seed,
        stratify=holdout_labels,
    )
    return {
        "train": [samples[index] for index in train_idx],
        "validation": [samples[index] for index in validation_idx],
        "test": [samples[index] for index in test_idx],
    }


def _find_first(root: Path, *relative_paths: str) -> Path | None:
    for relative in relative_paths:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def _find_directory(root: Path, *relative_paths: str) -> Path | None:
    for relative in relative_paths:
        candidate = root / relative
        if candidate.is_dir():
            return candidate
    return None


def _read_workbook_rows(path: Path) -> list[tuple[str, int]]:
    try:
        from openpyxl import load_workbook
    except ImportError:
        return _read_xlsx_rows_stdlib(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    rows = [_parse_label_row(uid, label) for uid, label in workbook.active.iter_rows(min_row=2, values_only=True)]
    workbook.close()
    return [row for row in rows if row is not None]


def _read_xlsx_rows_stdlib(path: Path) -> list[tuple[str, int]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(item.itertext()).strip() for item in root.findall("main:si", namespace)]
        root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[tuple[str, int]] = []
        for row_number, row in enumerate(root.findall(".//main:sheetData/main:row", namespace), start=1):
            if row_number == 1:
                continue
            values: list[Any] = []
            for cell in row.findall("main:c", namespace):
                value = cell.find("main:v", namespace)
                text = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s":
                    try:
                        text = strings[int(text)]
                    except (IndexError, ValueError):
                        text = ""
                values.append(text)
            if len(values) >= 2:
                parsed = _parse_label_row(values[0], values[1])
                if parsed is not None:
                    rows.append(parsed)
        return rows


def _parse_label_row(account_id: Any, label: Any) -> tuple[str, int] | None:
    try:
        if account_id is None or label is None:
            return None
        return str(int(float(account_id))), int(float(label))
    except (TypeError, ValueError):
        return None
