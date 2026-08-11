"""Verify the archived Twitter IO benchmark CSV against its digest manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from app.schemas.twitter_benchmark import TwitterBenchmarkManifest


__all__ = [
    "load_manifest",
    "main",
    "scan_twitter_benchmark",
    "verify_twitter_benchmark",
]


_TRUTHY = {"1", "true", "t", "yes", "y"}
_COMPARABLE_FIELDS = (
    "byte_size",
    "sha256",
    "columns",
    "rows",
    "users",
    "retweets",
    "replies",
    "quotes",
)


def scan_twitter_benchmark(path: Path) -> TwitterBenchmarkManifest:
    """Scan one Twitter IO CSV and return only header, digest, and counts."""
    csv_path = Path(path)
    digest = hashlib.sha256()
    with csv_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    users: set[str] = set()
    rows = 0
    retweets = 0
    replies = 0
    quotes = 0
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        for row in reader:
            rows += 1
            user_id = (row.get("userid") or "").strip()
            if user_id:
                users.add(user_id)
            if (row.get("is_retweet") or "").strip().lower() in _TRUTHY:
                retweets += 1
            if (row.get("in_reply_to_tweetid") or "").strip():
                replies += 1
            if (row.get("quoted_tweet_tweetid") or "").strip():
                quotes += 1

    return TwitterBenchmarkManifest(
        schema_version="cogguard.twitter_io.manifest.v1",
        source_path=str(csv_path),
        byte_size=csv_path.stat().st_size,
        sha256=digest.hexdigest().upper(),
        columns=columns,
        rows=rows,
        users=len(users),
        retweets=retweets,
        replies=replies,
        quotes=quotes,
    )


def load_manifest(path: Path) -> TwitterBenchmarkManifest:
    """Load the checked-in digest-only Twitter benchmark manifest."""
    return TwitterBenchmarkManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_twitter_benchmark(path: Path, expected: TwitterBenchmarkManifest) -> TwitterBenchmarkManifest:
    """Assert that a local CSV matches the expected digest and statistics."""
    scanned = scan_twitter_benchmark(path)
    for field in _COMPARABLE_FIELDS:
        actual_value = getattr(scanned, field)
        expected_value = getattr(expected, field)
        if actual_value != expected_value:
            raise AssertionError(f"{field} mismatch: expected {expected_value!r}, got {actual_value!r}")
    return scanned


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path", required=True, type=Path, help="Path to the external Twitter IO tweets CSV")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("fixtures/case_workbench/twitter_io_manifest.json"),
        help="Path to the checked-in Twitter IO digest manifest",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    verified = verify_twitter_benchmark(args.csv_path, load_manifest(args.manifest))
    print(json.dumps(verified.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
