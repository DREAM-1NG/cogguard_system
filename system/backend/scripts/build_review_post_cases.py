"""Convert local post-level datasets into a unified Review post-case JSONL.

The converter is read-only with respect to source datasets. It writes normalized
JSONL plus a manifest that records split counts, skipped media, and missing
content limitations. The output is a staging format for later model training and
full validation; it is not a trained-model result.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.propagation_context import build_thread_context_from_pheme


SCHEMA = "review-post-case-v1"

DEFAULT_DATASETS = [
    "MultiOFF",
    "HateXplain",
    "Jigsaw Toxicity",
    "Hateful Memes",
    "MAMI",
    "MMHS150K",
    "PHEME",
    "RumourEval 2019",
    "MOCHEG",
    "FACTIFY3M",
    "FakeSV",
    "mcfend",
    "Twitter15_16_dataset",
    "Fakeddit",
    "MuMiN",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=r"G:\CISCN\dataset")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\review_post_cases")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=DEFAULT_DATASETS,
        help=(
            "Datasets to convert. Defaults to the Review benchmark registry set. "
            "Unavailable gated datasets are reported as missing rather than fabricated."
        ),
    )
    parser.add_argument(
        "--max-per-dataset",
        type=int,
        default=0,
        help="Optional cap for quick smoke conversion. 0 means no cap.",
    )
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema": "review-post-case-manifest-v1",
        "case_schema": SCHEMA,
        "dataset_root": str(dataset_root),
        "output_dir": str(output_dir),
        "datasets": {},
        "summary": {},
    }

    converters = {
        "MultiOFF": convert_multioff,
        "PHEME": convert_pheme,
        "mcfend": convert_mcfend,
        "Twitter15_16_dataset": convert_twitter1516,
        "HateXplain": convert_hatexplain,
        "FakeSV": convert_fakesv,
        "Jigsaw Toxicity": convert_jigsaw_toxicity,
        "Hateful Memes": convert_hateful_memes,
        "MAMI": convert_mami,
        "MMHS150K": convert_mmhs150k,
        "RumourEval 2019": convert_rumoureval2019,
        "MOCHEG": convert_mocheg,
        "FACTIFY3M": convert_factify3m,
        "Fakeddit": convert_fakeddit,
        "MuMiN": convert_mumin,
    }
    for dataset in args.datasets:
        converter = converters.get(dataset)
        if converter is None:
            manifest["datasets"][dataset] = {
                "status": "unsupported",
                "error": f"Unsupported dataset: {dataset}",
            }
            continue
        output_path = output_dir / f"{safe_name(dataset)}.jsonl"
        dataset_manifest = converter(dataset_root, output_path, args.max_per_dataset)
        manifest["datasets"][dataset] = dataset_manifest

    manifest["summary"] = summarize_manifest(manifest["datasets"])
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {manifest_path}")
    return 0


def convert_multioff(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = dataset_root / "MultiOFF"
    split_dir = root / "Split Dataset"
    image_dir = root / "Labelled Images"
    split_files = {
        "train": split_dir / "Training_meme_dataset.csv",
        "validation": split_dir / "Validation_meme_dataset.csv",
        "test": split_dir / "Testing_meme_dataset.csv",
    }
    manifest = dataset_manifest("MultiOFF", root, output_path, ["meme", "img", "tweet"])
    if not root.exists():
        manifest["status"] = "missing"
        manifest["missing"].append(str(root))
        return manifest

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for split, csv_path in split_files.items():
            for row in iter_csv_rows(csv_path):
                image_name = row.get("image_name", "").strip()
                image_path = image_dir / image_name if image_name else None
                media_available = bool(image_path and image_path.exists())
                label = normalize_binary_label(row.get("label", ""), positive_values={"offensive"})
                case = {
                    **base_case("MultiOFF", split, f"multioff::{split}::{image_name}"),
                    "source_id": image_name,
                    "text": row.get("sentence", "").strip(),
                    "labels": {
                        "harmfulness": "harmful" if label == "positive" else "non_harmful",
                        "harm_type": ["offensive"] if label == "positive" else [],
                        "raw_label": row.get("label", "").strip(),
                    },
                    "views": {
                        "tweet": {"available": bool(row.get("sentence", "").strip())},
                        "meme": {"available": media_available and bool(row.get("sentence", "").strip())},
                        "img": {
                            "available": media_available,
                            "media_path": str(image_path) if image_path else "",
                        },
                        "video": {"available": False},
                    },
                    "claim_context": {"available": False},
                    "metadata": {
                        "task": "meme_offensive_detection",
                        "media_missing": not media_available,
                    },
                }
                write_case(out, case)
                update_manifest(manifest, case)
                if not media_available:
                    manifest["media_missing_examples"].append(image_name)
                if reached_limit(manifest, max_cases):
                    finalize_manifest(manifest)
                    return manifest
    finalize_manifest(manifest)
    return manifest


def convert_mcfend(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = dataset_root / "mcfend"
    news_path = root / "news.csv"
    manifest = dataset_manifest("mcfend", root, output_path, ["tweet", "img"])
    if not news_path.exists():
        manifest["status"] = "missing"
        manifest["missing"].append(str(news_path))
        return manifest

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for row in iter_csv_rows(news_path):
            news_id = row.get("news_id", "").strip()
            title = row.get("title", "").strip()
            content = row.get("content", "").strip()
            text = "\n".join(part for part in (title, content) if part)
            raw_label = row.get("label", "").strip()
            harmful = raw_label in {"谣言", "假", "fake", "rumor", "rumour"}
            pic_url = row.get("pic_url", "").strip()
            case = {
                **base_case("mcfend", "all", f"mcfend::{news_id}"),
                "source_id": news_id,
                "text": text,
                "labels": {
                    "harmfulness": "harmful" if harmful else "non_harmful",
                    "harm_type": ["misinformation"] if harmful else [],
                    "raw_label": raw_label,
                },
                "views": {
                    "tweet": {"available": bool(text)},
                    "meme": {"available": False},
                    "img": {"available": bool(pic_url), "media_url": pic_url},
                    "video": {"available": False},
                },
                "claim_context": {
                    "available": True,
                    "claim_text": title,
                    "evidence_text": content[:800],
                },
                "metadata": {
                    "task": "chinese_fake_news_detection",
                    "platform": row.get("platform", "").strip(),
                    "publish_time": row.get("publish_time", "").strip(),
                    "url": row.get("url", "").strip(),
                    "hashtag": row.get("hashtag", "").strip(),
                },
            }
            write_case(out, case)
            update_manifest(manifest, case)
            if reached_limit(manifest, max_cases):
                finalize_manifest(manifest)
                return manifest
    finalize_manifest(manifest)
    return manifest


def convert_pheme(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = dataset_root / "PHEME" / "all-rnr-annotated-threads"
    manifest = dataset_manifest("PHEME", root, output_path, ["tweet"])
    if not root.exists():
        manifest["status"] = "missing"
        manifest["missing"].append(str(root))
        return manifest

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for event_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("._")):
            event_name = event_dir.name.replace("-all-rnr-threads", "")
            for class_dir_name, rumour_label in (("rumours", "rumour"), ("non-rumours", "non_rumour")):
                class_dir = event_dir / class_dir_name
                if not class_dir.exists():
                    continue
                for thread_dir in sorted(p for p in class_dir.iterdir() if p.is_dir() and not p.name.startswith("._")):
                    annotation = read_json(thread_dir / "annotation.json")
                    source_tweets = sorted(
                        p
                        for p in (thread_dir / "source-tweets").glob("*.json")
                        if not p.name.startswith("._")
                    )
                    if not source_tweets:
                        continue
                    tweet = read_json(source_tweets[0])
                    reaction_paths = sorted(
                        p
                        for p in (thread_dir / "reactions").glob("*.json")
                        if not p.name.startswith("._")
                    )
                    reactions = [read_json(path) for path in reaction_paths]
                    text = str(tweet.get("text", "")).strip()
                    veracity = pheme_veracity(annotation, rumour_label)
                    harmful = rumour_label == "rumour" and veracity in {"false", "unverified"}
                    thread_context = build_thread_context_from_pheme(
                        tweet,
                        reactions,
                        event_name=event_name,
                        tree_id=thread_dir.name,
                        rumour_label=rumour_label,
                        veracity=veracity,
                    )
                    case = {
                        **base_case("PHEME", event_name, f"pheme::{event_name}::{thread_dir.name}"),
                        "source_id": str(tweet.get("id_str") or thread_dir.name),
                        "text": text,
                        "labels": {
                            "harmfulness": "harmful" if harmful else "non_harmful",
                            "harm_type": ["misinformation"] if harmful else [],
                            "rumour_label": rumour_label,
                            "veracity": veracity,
                            "raw_annotation": annotation,
                        },
                        "views": {
                            "tweet": {"available": bool(text)},
                            "meme": {"available": False},
                            "img": {"available": False},
                            "video": {"available": False},
                        },
                        "claim_context": {
                            "available": bool(annotation.get("category")),
                            "claim_text": str(annotation.get("category", "")),
                            "evidence_links": annotation.get("links", []),
                        },
                        "metadata": {
                            "task": "rumour_thread_veracity",
                            "event": event_name,
                            "created_at": tweet.get("created_at", ""),
                            "reaction_count": count_files(thread_dir / "reactions", {".json"}),
                        },
                        "thread_context": thread_context,
                    }
                    write_case(out, case)
                    update_manifest(manifest, case)
                    if reached_limit(manifest, max_cases):
                        finalize_manifest(manifest)
                        return manifest
    finalize_manifest(manifest)
    return manifest


def convert_twitter1516(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = dataset_root / "Twitter15_16_dataset"
    manifest = dataset_manifest("Twitter15_16_dataset", root, output_path, ["tweet"])
    manifest["notes"].append(
        "Local copy lacks source_tweets.txt, so converted cases contain labels and tree ids but no post text."
    )
    if not root.exists():
        manifest["status"] = "missing"
        manifest["missing"].append(str(root))
        return manifest

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for subset in ("twitter15", "twitter16"):
            label_path = root / subset / "label.txt"
            for raw_label, source_id in iter_colon_label_rows(label_path):
                tree_path = root / subset / "tree" / f"{source_id}.txt"
                harmful = raw_label in {"false", "unverified"}
                case = {
                    **base_case("Twitter15_16_dataset", subset, f"twitter1516::{subset}::{source_id}"),
                    "source_id": source_id,
                    "text": "",
                    "labels": {
                        "harmfulness": "harmful" if harmful else "non_harmful",
                        "harm_type": ["misinformation"] if harmful else [],
                        "rumour_label": raw_label,
                    },
                    "views": {
                        "tweet": {"available": False, "missing_reason": "source_tweets.txt absent"},
                        "meme": {"available": False},
                        "img": {"available": False},
                        "video": {"available": False},
                    },
                    "claim_context": {"available": False},
                    "metadata": {
                        "task": "rumour_event_classification",
                        "tree_path": str(tree_path),
                        "tree_available": tree_path.exists(),
                    },
                }
                write_case(out, case)
                update_manifest(manifest, case)
                if not case["views"]["tweet"]["available"]:
                    manifest["text_missing"] += 1
                if reached_limit(manifest, max_cases):
                    finalize_manifest(manifest)
                    return manifest
    finalize_manifest(manifest)
    return manifest


def convert_hatexplain(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "HateXplain",
            dataset_root / "hatexplain",
            dataset_root / "review_public" / "HateXplain",
            dataset_root / "review_public" / "hatexplain",
        ]
    )
    manifest = dataset_manifest("HateXplain", root, output_path, ["tweet"])
    data_path = root / "Data" / "dataset.json"
    split_path = root / "Data" / "post_id_divisions.json"
    if not data_path.exists() or not split_path.exists():
        manifest["status"] = "missing"
        if not data_path.exists():
            manifest["missing"].append(str(data_path))
        if not split_path.exists():
            manifest["missing"].append(str(split_path))
        return manifest

    data = read_json(data_path)
    divisions = read_json(split_path)
    id_to_split = {
        post_id: split
        for split, post_ids in divisions.items()
        for post_id in post_ids
    }

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for post_id, row in data.items():
            split = id_to_split.get(post_id, "unassigned")
            tokens = [str(token) for token in row.get("post_tokens") or []]
            text = " ".join(tokens)
            labels = [
                str(item.get("label", "")).strip().lower()
                for item in row.get("annotators") or []
                if item.get("label")
            ]
            majority_label = majority_vote(labels, default="normal")
            harmful = majority_label in {"hatespeech", "offensive"}
            target_groups = sorted(
                {
                    str(target)
                    for item in row.get("annotators") or []
                    for target in item.get("target", [])
                    if str(target).strip() and str(target) != "None"
                }
            )
            rationale_tokens = hatexplain_rationale_tokens(tokens, row.get("rationales") or [])
            case = {
                **base_case("HateXplain", split, f"hatexplain::{post_id}"),
                "source_id": post_id,
                "language": "en",
                "text": text,
                "labels": {
                    "harmfulness": "harmful" if harmful else "non_harmful",
                    "harm_type": [majority_label] if harmful else [],
                    "raw_label": majority_label,
                    "annotator_label_distribution": dict(Counter(labels)),
                    "target_groups": target_groups,
                    "rationale_tokens": rationale_tokens,
                },
                "views": {
                    "tweet": {"available": bool(text)},
                    "meme": {"available": False},
                    "img": {"available": False},
                    "video": {"available": False},
                },
                "claim_context": {"available": False},
                "metadata": {
                    "task": "explainable_hate_speech_detection",
                    "annotator_count": len(row.get("annotators") or []),
                    "rationale_annotator_count": len(row.get("rationales") or []),
                    "token_count": len(tokens),
                },
            }
            write_case(out, case)
            update_manifest(manifest, case)
            if not text:
                manifest["text_missing"] += 1
            if reached_limit(manifest, max_cases):
                finalize_manifest(manifest)
                return manifest
    finalize_manifest(manifest)
    return manifest


def convert_fakesv(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "FakeSV",
            dataset_root / "fakesv",
            dataset_root / "review_public" / "FakeSV",
            dataset_root / "review_public" / "fakesv",
        ]
    )
    dataset_dir = root / "dataset"
    data_path = dataset_dir / "data.json"
    temporal_dir = dataset_dir / "data-split" / "temporal"
    split_files = {
        "train": temporal_dir / "vid_time3_train.txt",
        "validation": temporal_dir / "vid_time3_val.txt",
        "test": temporal_dir / "vid_time3_test.txt",
    }
    manifest = dataset_manifest("FakeSV", root, output_path, ["tweet", "video"])
    manifest["notes"].append(
        "Public repository provides video IDs, keywords, labels, and official splits. "
        "Raw videos or pre-extracted audiovisual features require the upstream data agreement / external downloads."
    )
    if not data_path.exists():
        manifest["status"] = "missing"
        manifest["missing"].append(str(data_path))
        return manifest

    split_by_video_id = {}
    for split, path in split_files.items():
        for video_id in read_id_lines(path):
            split_by_video_id[video_id] = split

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for row in iter_jsonl(data_path):
            video_id = str(row.get("video_id", "")).strip()
            if not video_id:
                continue
            raw_label = str(row.get("annotation", "")).strip()
            split = split_by_video_id.get(video_id, "unassigned")
            keywords = str(row.get("keywords", "")).strip()
            harmful = raw_label in {"假", "辟谣", "fake", "rumor", "rumour"}
            case = {
                **base_case("FakeSV", split, f"fakesv::{video_id}"),
                "source_id": video_id,
                "language": "zh",
                "text": keywords,
                "labels": {
                    "harmfulness": "harmful" if harmful else "non_harmful",
                    "harm_type": ["misinformation"] if harmful else [],
                    "veracity": fakesv_veracity(raw_label),
                    "raw_label": raw_label,
                },
                "views": {
                    "tweet": {"available": bool(keywords), "source": "keywords"},
                    "meme": {"available": False},
                    "img": {"available": False},
                    "video": {
                        "available": True,
                        "video_id": video_id,
                        "video_binary_available": False,
                        "decodable_content": ["keywords"],
                    },
                },
                "claim_context": {
                    "available": bool(keywords),
                    "claim_text": keywords,
                    "evidence_text": "",
                },
                "metadata": {
                    "task": "short_video_fake_news_detection",
                    "split_source": "official_temporal_time3" if split != "unassigned" else "not_in_temporal_split",
                    "video_binary_available": False,
                    "feature_download_required": True,
                },
            }
            write_case(out, case)
            update_manifest(manifest, case)
            if reached_limit(manifest, max_cases):
                finalize_manifest(manifest)
                return manifest
    finalize_manifest(manifest)
    return manifest


def convert_jigsaw_toxicity(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "Jigsaw Toxicity",
            dataset_root / "jigsaw",
            dataset_root / "jigsaw-toxic-comment-classification-challenge",
            dataset_root / "review_public" / "Jigsaw Toxicity",
            dataset_root / "review_public" / "jigsaw",
        ]
    )
    manifest = dataset_manifest("Jigsaw Toxicity", root, output_path, ["tweet"])
    manifest["notes"].append("Requires Kaggle terms/token before local conversion.")
    train_path = first_existing_file(
        [
            root / "train.csv",
            root / "jigsaw-toxic-comment-train.csv",
            root / "jigsaw-toxic-comment-classification-challenge" / "train.csv",
        ]
    )
    if not train_path.exists():
        return missing_manifest(manifest, [root / "train.csv"])

    toxic_columns = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]
    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for row in iter_csv_rows(train_path):
            comment_id = first_text(row, ["id", "comment_id"])
            text = first_text(row, ["comment_text", "text", "content"])
            active_types = [
                column
                for column in toxic_columns
                if str(row.get(column, "")).strip() in {"1", "1.0", "true", "True"}
            ]
            harmful = bool(active_types)
            case = {
                **base_case("Jigsaw Toxicity", "train", f"jigsaw::{comment_id or manifest['case_count']}"),
                "source_id": comment_id,
                "language": "en",
                "text": text,
                "labels": {
                    "harmfulness": "harmful" if harmful else "non_harmful",
                    "harm_type": active_types,
                    "raw_label": {column: row.get(column, "") for column in toxic_columns},
                },
                "views": {
                    "tweet": {"available": bool(text)},
                    "meme": {"available": False},
                    "img": {"available": False},
                    "video": {"available": False},
                },
                "claim_context": {"available": False},
                "metadata": {"task": "text_toxicity_classification", "source_file": str(train_path)},
            }
            write_case(out, case)
            update_manifest(manifest, case)
            if not text:
                manifest["text_missing"] += 1
            if reached_limit(manifest, max_cases):
                finalize_manifest(manifest)
                return manifest
    finalize_manifest(manifest)
    return manifest


def convert_mami(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "MAMI",
            dataset_root / "mami",
            dataset_root / "review_public" / "MAMI",
            dataset_root / "review_public" / "mami",
        ]
    )
    manifest = dataset_manifest("MAMI", root, output_path, ["tweet", "meme", "img"])
    manifest["notes"].append(
        "Official repository contains baselines/evaluation only unless the requested data package "
        "has been unpacked with train.csv, test.csv/ref, and TRAINING images."
    )
    train_path = root / "train.csv"
    test_path = root / "test.csv"
    image_dir = root / "TRAINING"
    truth_path = first_existing_file([root / "ref" / "truth.txt", root / "truth.txt"])
    if not train_path.exists() or not image_dir.exists():
        missing = [path for path in [train_path, image_dir, test_path, truth_path] if not path.exists()]
        return missing_manifest(manifest, missing)

    test_truth = read_mami_truth(truth_path)
    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for split, csv_path in [("train", train_path), ("test", test_path)]:
            if not csv_path.exists():
                continue
            for row in iter_delimited_rows(csv_path, delimiter="\t"):
                file_name = first_text(row, ["file_name", "filename", "file"])
                if not file_name:
                    continue
                text = first_text(row, ["Text Transcription", "text", "transcription"])
                label_payload = mami_labels_from_row(row, test_truth.get(file_name, {}))
                if not label_payload:
                    continue
                harmful = label_payload["misogynous"] == 1
                image_path = image_dir / file_name
                media_available = image_path.exists()
                harm_types = [
                    name
                    for name in ["shaming", "stereotype", "objectification", "violence"]
                    if label_payload.get(name) == 1
                ]
                if harmful and not harm_types:
                    harm_types = ["misogyny"]
                case = {
                    **base_case("MAMI", split, f"mami::{split}::{file_name}"),
                    "source_id": file_name,
                    "language": "en",
                    "text": text,
                    "labels": {
                        "harmfulness": "harmful" if harmful else "non_harmful",
                        "harm_type": harm_types,
                        "raw_label": label_payload,
                    },
                    "views": {
                        "tweet": {"available": bool(text)},
                        "meme": {"available": media_available and bool(text)},
                        "img": {"available": media_available, "media_path": str(image_path) if media_available else ""},
                        "video": {"available": False},
                    },
                    "claim_context": {"available": False},
                    "metadata": {
                        "task": "multimedia_automatic_misogyny_identification",
                        "media_missing": not media_available,
                        "source_file": str(csv_path),
                    },
                }
                write_case(out, case)
                update_manifest(manifest, case)
                if not media_available:
                    manifest["media_missing_examples"].append(file_name)
                if not text:
                    manifest["text_missing"] += 1
                if reached_limit(manifest, max_cases):
                    finalize_manifest(manifest)
                    return manifest
    finalize_manifest(manifest)
    return manifest


def convert_hateful_memes(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "Hateful Memes",
            dataset_root / "hateful_memes",
            dataset_root / "hateful-memes",
            dataset_root / "review_public" / "Hateful Memes",
            dataset_root / "review_public" / "hateful_memes",
        ]
    )
    manifest = dataset_manifest("Hateful Memes", root, output_path, ["tweet", "meme", "img"])
    manifest["notes"].append("Requires Meta/Facebook AI dataset access; expected jsonl files include img, text, label.")
    split_files = {
        "train": first_existing_file([root / "train.jsonl", root / "train_seen.jsonl"]),
        "validation": first_existing_file([root / "dev_seen.jsonl", root / "dev.jsonl"]),
        "test": first_existing_file([root / "test_seen.jsonl", root / "test.jsonl"]),
    }
    if not split_files["train"].exists():
        return missing_manifest(manifest, [root / "train.jsonl", root / "img"])

    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for split, path in split_files.items():
            for row in iter_jsonl(path):
                source_id = str(row.get("id") or row.get("img") or manifest["case_count"])
                text = str(row.get("text") or "").strip()
                raw_label = row.get("label")
                if raw_label is None:
                    continue
                harmful = str(raw_label).strip() in {"1", "true", "True", "hateful"}
                image_rel = str(row.get("img") or "").strip()
                image_path = root / image_rel if image_rel else root / "img" / f"{source_id}.png"
                media_available = image_path.exists()
                case = {
                    **base_case("Hateful Memes", split, f"hatefulmemes::{split}::{source_id}"),
                    "source_id": source_id,
                    "language": "en",
                    "text": text,
                    "labels": {
                        "harmfulness": "harmful" if harmful else "non_harmful",
                        "harm_type": ["hateful_meme"] if harmful else [],
                        "raw_label": raw_label,
                    },
                    "views": {
                        "tweet": {"available": bool(text)},
                        "meme": {"available": media_available and bool(text)},
                        "img": {"available": media_available, "media_path": str(image_path) if media_available else ""},
                        "video": {"available": False},
                    },
                    "claim_context": {"available": False},
                    "metadata": {"task": "hateful_meme_detection", "media_missing": not media_available},
                }
                write_case(out, case)
                update_manifest(manifest, case)
                if not media_available:
                    manifest["media_missing_examples"].append(image_rel or source_id)
                if reached_limit(manifest, max_cases):
                    finalize_manifest(manifest)
                    return manifest
    finalize_manifest(manifest)
    return manifest


def convert_mmhs150k(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "MMHS150K",
            dataset_root / "mmhs150k",
            dataset_root / "multimodal-hate-speech",
            dataset_root / "review_public" / "MMHS150K",
        ]
    )
    manifest = dataset_manifest("MMHS150K", root, output_path, ["tweet", "img"])
    manifest["notes"].append("Expected Kaggle/author mirror files with tweet text/label and aligned images.")
    candidate_files = [
        root / "MMHS150K_GT.json",
        root / "MMHS150K_GT.jsonl",
        root / "train.csv",
        root / "mmhs150k.csv",
    ]
    data_path = first_existing_file(candidate_files)
    if not data_path.exists():
        return missing_manifest(manifest, candidate_files[:2])

    image_dirs = [root / "img_resized", root / "images", root / "img"]
    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        rows = iter_mmhs_rows(data_path)
        for row in rows:
            source_id = first_text(row, ["tweet_id", "id", "image_id"])
            text = first_text(row, ["tweet_text", "text", "full_text"])
            raw_label = first_text(row, ["label", "class", "annotation"])
            harmful = raw_label.lower() not in {"0", "normal", "none", "non_hateful", "non-hateful", "not_hate"}
            image_path = find_media_path(image_dirs, [source_id, first_text(row, ["image", "img", "image_name"])])
            media_available = bool(image_path)
            case = {
                **base_case("MMHS150K", first_text(row, ["split"]) or "all", f"mmhs150k::{source_id or manifest['case_count']}"),
                "source_id": source_id,
                "language": "en",
                "text": text,
                "labels": {
                    "harmfulness": "harmful" if harmful else "non_harmful",
                    "harm_type": ["hate_speech"] if harmful else [],
                    "raw_label": raw_label,
                },
                "views": {
                    "tweet": {"available": bool(text)},
                    "meme": {"available": False},
                    "img": {"available": media_available, "media_path": str(image_path) if image_path else ""},
                    "video": {"available": False},
                },
                "claim_context": {"available": False},
                "metadata": {"task": "multimodal_hate_speech_detection", "media_missing": not media_available},
            }
            write_case(out, case)
            update_manifest(manifest, case)
            if not media_available:
                manifest["media_missing_examples"].append(source_id)
            if reached_limit(manifest, max_cases):
                finalize_manifest(manifest)
                return manifest
    finalize_manifest(manifest)
    return manifest


def convert_fakeddit(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "Fakeddit",
            dataset_root / "fakeddit",
            dataset_root / "review_public" / "Fakeddit",
            dataset_root / "review_public" / "fakeddit",
        ]
    )
    manifest = dataset_manifest("Fakeddit", root, output_path, ["tweet", "img"])
    manifest["notes"].append(
        "GitHub clone only contains downloader code. Full conversion requires v2.0 TSV files, preferably multimodal_only_samples, and downloaded images."
    )
    candidate_tsvs = [
        root / "multimodal_only_samples" / "all_train.tsv",
        root / "all_train.tsv",
        root / "train.tsv",
    ]
    train_path = first_existing_file(candidate_tsvs)
    if not train_path.exists():
        return missing_manifest(manifest, candidate_tsvs[:2])

    split_files = {
        "train": train_path,
        "validation": first_existing_file([root / "multimodal_only_samples" / "all_validate.tsv", root / "validate.tsv", root / "dev.tsv"]),
        "test": first_existing_file([root / "multimodal_only_samples" / "all_test_public.tsv", root / "test.tsv"]),
    }
    image_dirs = [root / "images", root / "public_image_set", root / "multimodal_only_samples" / "images"]
    with output_path.open("w", encoding="utf-8", newline="\n") as out:
        for split, path in split_files.items():
            if not path.exists():
                continue
            for row in iter_delimited_rows(path, delimiter="\t"):
                source_id = first_text(row, ["id", "submission_id", "author"])
                text = first_text(row, ["clean_title", "title", "text"])
                raw_label = first_text(row, ["2_way_label", "3_way_label", "6_way_label", "label"])
                harmful = fakeddit_is_harmful(raw_label)
                image_name = first_text(row, ["image_id", "image", "image_url"])
                image_path = find_media_path(image_dirs, [image_name, source_id])
                media_available = bool(image_path)
                case = {
                    **base_case("Fakeddit", split, f"fakeddit::{split}::{source_id or manifest['case_count']}"),
                    "source_id": source_id,
                    "language": "en",
                    "text": text,
                    "labels": {
                        "harmfulness": "harmful" if harmful else "non_harmful",
                        "harm_type": ["misinformation"] if harmful else [],
                        "raw_label": raw_label,
                    },
                    "views": {
                        "tweet": {"available": bool(text)},
                        "meme": {"available": False},
                        "img": {"available": media_available, "media_path": str(image_path) if image_path else ""},
                        "video": {"available": False},
                    },
                    "claim_context": {"available": bool(text), "claim_text": text},
                    "metadata": {"task": "multimodal_fake_news_detection", "media_missing": not media_available},
                }
                write_case(out, case)
                update_manifest(manifest, case)
                if not media_available:
                    manifest["media_missing_examples"].append(image_name or source_id)
                if reached_limit(manifest, max_cases):
                    finalize_manifest(manifest)
                    return manifest
    finalize_manifest(manifest)
    return manifest


def convert_rumoureval2019(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "RumourEval2019",
            dataset_root / "RumourEval 2019",
            dataset_root / "rumoureval",
            dataset_root / "review_public" / "RumourEval2019",
        ]
    )
    manifest = dataset_manifest("RumourEval 2019", root, output_path, ["tweet"])
    manifest["notes"].append(
        "Baseline GitHub is not enough. Download official CodaLab train/test data before conversion."
    )
    required = [root / "rumoureval-2019-training-data", root / "rumoureval-2019-test-data"]
    return missing_manifest(manifest, [path for path in required if not path.exists()] or required)


def convert_mocheg(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "MOCHEG",
            dataset_root / "Mocheg",
            dataset_root / "mocheg",
            dataset_root / "review_public" / "Mocheg",
        ]
    )
    manifest = dataset_manifest("MOCHEG", root, output_path, ["tweet", "img"])
    manifest["notes"].append(
        "Official implementation clone is present locally, but MOCHEG v1 data requires the upstream Google Form."
    )
    required = [root / "Corpus2.csv", root / "train", root / "dev", root / "test"]
    return missing_manifest(manifest, [path for path in required if not path.exists()] or required)


def convert_factify3m(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "FACTIFY3M",
            dataset_root / "factify3m",
            dataset_root / "review_public" / "FACTIFY3M",
        ]
    )
    manifest = dataset_manifest("FACTIFY3M", root, output_path, ["tweet", "img"])
    manifest["notes"].append(
        "No public local data package is available; older Factify baseline repo does not contain FACTIFY3M train/validation/test files."
    )
    required = [root / "train", root / "validation", root / "test"]
    return missing_manifest(manifest, [path for path in required if not path.exists()] or required)


def convert_mumin(dataset_root: Path, output_path: Path, max_cases: int) -> dict[str, Any]:
    root = first_existing_path(
        [
            dataset_root / "MuMiN",
            dataset_root / "mumin",
            dataset_root / "review_public" / "MuMiN",
            dataset_root / "review_public" / "mumin",
        ]
    )
    manifest = dataset_manifest("MuMiN", root, output_path, ["tweet", "img"])
    manifest["notes"].append("MuMiN requires dataset-site download/build steps and platform-term checks before conversion.")
    return missing_manifest(manifest, [root])


def base_case(dataset: str, split: str, case_id: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "case_id": case_id,
        "dataset": dataset,
        "split": split,
        "source_id": "",
        "language": "unknown",
        "text": "",
        "labels": {},
        "views": {
            "tweet": {"available": False},
            "meme": {"available": False},
            "img": {"available": False},
            "video": {"available": False},
        },
        "claim_context": {"available": False},
        "metadata": {},
    }


def dataset_manifest(dataset: str, source_path: Path, output_path: Path, views: list[str]) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "status": "unknown",
        "source_path": str(source_path),
        "output_path": str(output_path),
        "views": views,
        "case_count": 0,
        "split_counts": {},
        "label_counts": {},
        "view_available_counts": {view: 0 for view in ["tweet", "meme", "img", "video"]},
        "media_missing_examples": [],
        "text_missing": 0,
        "missing": [],
        "notes": [],
    }


def missing_manifest(manifest: dict[str, Any], missing_paths: list[Path]) -> dict[str, Any]:
    manifest["status"] = "missing"
    for path in missing_paths:
        text = str(path)
        if text not in manifest["missing"]:
            manifest["missing"].append(text)
    return manifest


def write_case(out, case: dict[str, Any]) -> None:
    out.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")


def update_manifest(manifest: dict[str, Any], case: dict[str, Any]) -> None:
    manifest["case_count"] += 1
    manifest["split_counts"][case["split"]] = manifest["split_counts"].get(case["split"], 0) + 1
    harmfulness = case.get("labels", {}).get("harmfulness", "unknown")
    manifest["label_counts"][harmfulness] = manifest["label_counts"].get(harmfulness, 0) + 1
    for view, view_info in case.get("views", {}).items():
        if view_info.get("available"):
            manifest["view_available_counts"][view] = manifest["view_available_counts"].get(view, 0) + 1


def finalize_manifest(manifest: dict[str, Any]) -> None:
    if manifest["status"] in {"missing", "unsupported"}:
        return
    if manifest["case_count"] == 0:
        manifest["status"] = "empty"
    elif manifest.get("media_missing_examples") or manifest.get("text_missing"):
        manifest["status"] = "partial"
    else:
        manifest["status"] = "converted"
    manifest["media_missing_examples"] = manifest["media_missing_examples"][:20]


def summarize_manifest(datasets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(item.get("status", "unknown") for item in datasets.values())
    case_count = sum(int(item.get("case_count", 0)) for item in datasets.values())
    return {
        "dataset_count": len(datasets),
        "case_count": case_count,
        "status_counts": dict(status_counts),
        "converted": sorted(name for name, item in datasets.items() if item.get("status") == "converted"),
        "partial": sorted(name for name, item in datasets.items() if item.get("status") == "partial"),
        "missing": sorted(name for name, item in datasets.items() if item.get("status") == "missing"),
        "note": (
            "Conversion normalizes local data into review-post-case-v1. It does not train "
            "or evaluate MV-PostGuard."
        ),
    }


def iter_csv_rows(path: Path) -> Iterable[dict[str, str]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def iter_delimited_rows(path: Path, *, delimiter: str) -> Iterable[dict[str, str]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            yield row


def iter_colon_label_rows(path: Path) -> Iterable[tuple[str, str]]:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" not in line:
            continue
        label, source_id = line.split(":", 1)
        yield label.strip(), source_id.strip()


def normalize_binary_label(value: str, positive_values: set[str]) -> str:
    return "positive" if value.strip().lower() in {item.lower() for item in positive_values} else "negative"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def iter_mmhs_rows(path: Path) -> Iterable[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        yield from iter_jsonl(path)
        return
    if suffix == ".json":
        data = read_json(path)
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    yield {"tweet_id": key, **value}
                else:
                    yield {"tweet_id": key, "label": value}
        return
    yield from iter_csv_rows(path)


def read_id_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]


def fakesv_veracity(raw_label: str) -> str:
    if raw_label == "真":
        return "true"
    if raw_label == "假":
        return "false"
    if raw_label == "辟谣":
        return "debunking"
    return "unknown"


def pheme_veracity(annotation: dict[str, Any], rumour_label: str) -> str:
    if rumour_label != "rumour":
        return "non_rumour"
    if str(annotation.get("true", "")).strip() == "1":
        return "true"
    if str(annotation.get("misinformation", "")).strip() == "1":
        return "false"
    return "unverified"


def first_existing_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def first_existing_file(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return paths[0]


def first_text(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def read_mami_truth(path: Path) -> dict[str, dict[str, int]]:
    truth: dict[str, dict[str, int]] = {}
    if not path.exists():
        return truth
    columns = ["misogynous", "shaming", "stereotype", "objectification", "violence"]
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 2:
            continue
        values = {}
        for name, raw in zip(columns, parts[1:]):
            values[name] = 1 if raw.strip() in {"1", "1.0", "true", "True"} else 0
        truth[parts[0].strip()] = values
    return truth


def mami_labels_from_row(row: dict[str, Any], fallback: dict[str, int]) -> dict[str, int]:
    columns = ["misogynous", "shaming", "stereotype", "objectification", "violence"]
    labels: dict[str, int] = {}
    for column in columns:
        raw = row.get(column)
        if raw is None or str(raw).strip() == "":
            if column in fallback:
                labels[column] = fallback[column]
            continue
        labels[column] = 1 if str(raw).strip() in {"1", "1.0", "true", "True"} else 0
    return labels


def find_media_path(root_dirs: list[Path], candidates: list[str]) -> Path | None:
    suffixes = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    cleaned = [str(candidate).strip() for candidate in candidates if str(candidate).strip()]
    for value in cleaned:
        candidate_path = Path(value)
        names = [candidate_path.name] if candidate_path.name else [value]
        if candidate_path.is_absolute() and candidate_path.exists():
            return candidate_path
        for root in root_dirs:
            for name in names:
                direct = root / name
                if direct.exists():
                    return direct
                stem = Path(name).stem or name
                for suffix in suffixes:
                    maybe = root / f"{stem}{suffix}"
                    if maybe.exists():
                        return maybe
    return None


def fakeddit_is_harmful(raw_label: str) -> bool:
    value = str(raw_label).strip().lower()
    if value in {"", "none", "nan"}:
        return False
    if value in {"0", "true", "real", "1"}:
        return False
    if value in {"fake", "false", "2", "3", "4", "5"}:
        return True
    try:
        return int(float(value)) > 1
    except ValueError:
        return value not in {"non_harmful", "non-harmful", "reliable"}


def majority_vote(values: list[str], *, default: str) -> str:
    if not values:
        return default
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]


def hatexplain_rationale_tokens(tokens: list[str], rationales: list[list[int]]) -> list[str]:
    if not tokens or not rationales:
        return []
    votes = [0] * len(tokens)
    for rationale in rationales:
        for index, value in enumerate(rationale[: len(tokens)]):
            if value:
                votes[index] += 1
    threshold = max(1, len(rationales) // 2 + len(rationales) % 2)
    return [token for token, vote in zip(tokens, votes) if vote >= threshold]


def count_files(path: Path, suffixes: set[str]) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file() and p.suffix.lower() in suffixes)


def reached_limit(manifest: dict[str, Any], max_cases: int) -> bool:
    return max_cases > 0 and manifest["case_count"] >= max_cases


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
