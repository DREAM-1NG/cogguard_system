"""Local training utilities for Weibo bot detection.

This module turns the vendored Botection corpus into a reproducible local
training baseline. It intentionally stays small and deterministic:

- input is the labeled Weibo corpus shipped with the repository
- features are bag-of-words text plus compact profile/activity metadata
- output is a joblib artifact with the fitted pipeline and metadata
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from xml.etree import ElementTree
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_DATASET_ROOT = Path(r"G:\CISCN\_tmp\Botection")
DEFAULT_OUTPUT_DIR = Path(r"G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\weibo_bot_detection")


@dataclass(slots=True)
class WeiboPostCorpus:
    """One account-level training row."""

    uid: str
    label: int
    text: str
    post_count: int
    avg_text_length: float
    unique_text_ratio: float
    duplicate_text_ratio: float
    url_marker_count: int
    mention_count: int
    hashtag_count: int
    emoji_marker_count: int
    char_count: int
    file_hash: str


def train_weibo_bot_model(
    dataset_root: str | Path = DEFAULT_DATASET_ROOT,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    test_size: float = 0.2,
    random_state: int = 42,
    max_features: int = 5000,
) -> dict[str, Any]:
    """Train a local Weibo bot detector on the vendored labeled corpus."""

    dataset_root = Path(dataset_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_weibo_corpus(dataset_root)
    if not rows:
        raise ValueError(f"no labeled Weibo samples found under {dataset_root}")

    frame = pd.DataFrame([asdict(row) for row in rows])
    train_frame, test_frame = train_test_split(
        frame,
        test_size=test_size,
        random_state=random_state,
        stratify=frame["label"],
    )

    pipeline = _build_pipeline(max_features=max_features)
    pipeline.fit(train_frame, train_frame["label"])
    probabilities = pipeline.predict_proba(test_frame)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    metrics = {
        "accuracy": float(accuracy_score(test_frame["label"], predictions)),
        "macro_f1": float(f1_score(test_frame["label"], predictions, average="macro")),
        "roc_auc": float(roc_auc_score(test_frame["label"], probabilities)),
        "classification_report": classification_report(
            test_frame["label"],
            predictions,
            output_dict=True,
            zero_division=0,
        ),
    }

    artifact = {
        "schema": "cogguard.weibo-bot-detection.v1",
        "dataset_root": str(dataset_root.resolve()),
        "row_count": int(len(frame)),
        "train_count": int(len(train_frame)),
        "test_count": int(len(test_frame)),
        "random_state": int(random_state),
        "test_size": float(test_size),
        "feature_set": {
            "text": "tfidf_unigram_bigram",
            "metadata": [
                "post_count",
                "avg_text_length",
                "unique_text_ratio",
                "duplicate_text_ratio",
                "url_marker_count",
                "mention_count",
                "hashtag_count",
                "emoji_marker_count",
                "char_count",
            ],
        },
        "metrics": metrics,
    }

    artifact_path = output_dir / "weibo_bot_detector.joblib"
    joblib.dump({"pipeline": pipeline, "artifact": artifact}, artifact_path)
    summary_path = output_dir / "weibo_bot_detector.json"
    summary_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        **artifact,
        "artifact_path": str(artifact_path),
        "summary_path": str(summary_path),
    }


def load_weibo_bot_model(artifact_path: str | Path) -> dict[str, Any]:
    """Load a previously trained Weibo bot detection artifact."""

    payload = joblib.load(Path(artifact_path))
    if not isinstance(payload, dict) or "pipeline" not in payload:
        raise ValueError(f"invalid artifact payload: {artifact_path}")
    return payload


def load_weibo_corpus(dataset_root: Path) -> list[WeiboPostCorpus]:
    """Load uid-level labeled samples and aggregate each account's posts."""

    label_paths = [
        dataset_root / "dataset" / "bot label.xlsx",
        dataset_root / "dataset" / "final data.xlsx",
        dataset_root / "textual_network_training" / "final data.xlsx",
    ]
    label_path = next((path for path in label_paths if path.exists()), None)
    if label_path is None:
        raise FileNotFoundError(f"could not find labeled workbook under {dataset_root}")

    workbook_rows = _read_workbook_rows(label_path)
    data_dir_candidates = [
        dataset_root / "dataset" / "data",
        dataset_root / "textual_network_training" / "data",
        dataset_root / "textual_network_training" / "baby data",
    ]
    data_dir = next((path for path in data_dir_candidates if path.exists()), None)
    if data_dir is None:
        raise FileNotFoundError(f"could not find txt corpus directory under {dataset_root}")

    samples: list[WeiboPostCorpus] = []
    for uid, label in workbook_rows:
        post_path = data_dir / f"{uid}.txt"
        if not post_path.exists():
            continue
        text = post_path.read_text(encoding="utf-8", errors="ignore")
        cleaned = _normalize_text(text)
        posts = [line for line in cleaned.split("\n") if line.strip()]
        if not posts:
            continue
        sample = WeiboPostCorpus(
            uid=str(uid),
            label=int(label),
            text=cleaned,
            post_count=len(posts),
            avg_text_length=float(np.mean([len(post) for post in posts])),
            unique_text_ratio=float(len(set(posts)) / max(len(posts), 1)),
            duplicate_text_ratio=float(1.0 - len(set(posts)) / max(len(posts), 1)),
            url_marker_count=_count_occurrences(cleaned, "httpurl"),
            mention_count=_count_occurrences(cleaned, "@user"),
            hashtag_count=_count_occurrences(cleaned, "#"),
            emoji_marker_count=_count_occurrences(cleaned, "eeeee"),
            char_count=len(cleaned),
            file_hash=_sha256_text(text),
        )
        samples.append(sample)
    return samples


def _build_pipeline(*, max_features: int) -> Pipeline:
    metadata_features = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("scale", StandardScaler(with_mean=False)),
        ]
    )
    features = ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(
                    max_features=max_features,
                    ngram_range=(1, 2),
                    min_df=2,
                    token_pattern=r"(?u)\b\S+\b",
                ),
                "text",
            ),
            (
                "metadata",
                metadata_features,
                [
                    "post_count",
                    "avg_text_length",
                    "unique_text_ratio",
                    "duplicate_text_ratio",
                    "url_marker_count",
                    "mention_count",
                    "hashtag_count",
                    "emoji_marker_count",
                    "char_count",
                ],
            ),
        ],
        remainder="drop",
        sparse_threshold=0.3,
    )
    classifier = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        solver="liblinear",
        random_state=42,
    )
    return Pipeline([("features", features), ("classifier", classifier)])


def _read_workbook_rows(path: Path) -> list[tuple[str, int]]:
    """Read the two-column workbook without making Excel support mandatory.

    ``openpyxl`` remains an optional accelerator for local training. The
    standard-library fallback keeps corpus discovery and backend import smoke
    usable in the lean runtime image.
    """

    try:
        from openpyxl import load_workbook
    except ImportError:
        return _read_xlsx_rows_stdlib(path)

    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    rows: list[tuple[str, int]] = []
    for uid, label in worksheet.iter_rows(min_row=2, values_only=True):
        parsed = _parse_label_row(uid, label)
        if parsed is not None:
            rows.append(parsed)
    workbook.close()
    return rows


def _read_xlsx_rows_stdlib(path: Path) -> list[tuple[str, int]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("main:si", namespace):
                shared_strings.append("".join(item.itertext()).strip())
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in archive.namelist():
            raise ValueError(f"workbook has no first worksheet: {path}")
        root = ElementTree.fromstring(archive.read(sheet_name))
        rows: list[tuple[str, int]] = []
        for row_index, row in enumerate(root.findall(".//main:sheetData/main:row", namespace), start=1):
            if row_index == 1:
                continue
            cells: list[Any] = []
            for cell in row.findall("main:c", namespace):
                value = cell.find("main:v", namespace)
                if value is None:
                    cells.append(None)
                    continue
                text = value.text or ""
                if cell.attrib.get("t") == "s":
                    try:
                        text = shared_strings[int(text)]
                    except (IndexError, ValueError):
                        text = ""
                cells.append(text)
            if len(cells) >= 2:
                parsed = _parse_label_row(cells[0], cells[1])
                if parsed is not None:
                    rows.append(parsed)
        return rows


def _parse_label_row(uid: Any, label: Any) -> tuple[str, int] | None:
    if uid is None or label is None:
        return None
    try:
        return str(int(float(uid))), int(float(label))
    except (TypeError, ValueError):
        return None


def _normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"https?://\S+", " httpurl ", text)
    text = re.sub(r"@\S+", " @user ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _count_occurrences(text: str, token: str) -> int:
    return text.count(token)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
