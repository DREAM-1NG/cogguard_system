import asyncio
import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts.case_workbench_acceptance import run_acceptance


EXPECTED_COLUMNS = (
    "tweetid",
    "userid",
    "user_display_name",
    "user_screen_name",
    "user_reported_location",
    "user_profile_description",
    "user_profile_url",
    "follower_count",
    "following_count",
    "account_creation_date",
    "account_language",
    "tweet_language",
    "tweet_text",
    "tweet_time",
    "tweet_client_name",
    "in_reply_to_userid",
    "in_reply_to_tweetid",
    "quoted_tweet_tweetid",
    "is_retweet",
    "retweet_userid",
    "retweet_tweetid",
    "latitude",
    "longitude",
    "quote_count",
    "reply_count",
    "like_count",
    "retweet_count",
    "hashtags",
    "urls",
    "user_mentions",
    "poll_choices",
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "case_workbench"
MANIFEST_PATH = FIXTURE_DIR / "twitter_io_manifest.json"


def _write_tiny_twitter_csv(path: Path) -> None:
    empty_row = {column: "" for column in EXPECTED_COLUMNS}
    rows = [
        {
            **empty_row,
            "tweetid": "1",
            "userid": "u1",
            "tweet_text": "retweet sample",
            "is_retweet": "TRUE",
        },
        {
            **empty_row,
            "tweetid": "2",
            "userid": "u2",
            "tweet_text": "reply and quote sample",
            "in_reply_to_tweetid": "1",
            "quoted_tweet_tweetid": "9",
            "is_retweet": "false",
        },
        {
            **empty_row,
            "tweetid": "3",
            "userid": "u1",
            "tweet_text": "numeric retweet sample",
            "is_retweet": "1",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def test_manifest_records_only_expected_twitter_io_statistics():
    from app.schemas.twitter_benchmark import TwitterBenchmarkManifest

    manifest = TwitterBenchmarkManifest.model_validate_json(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest.schema_version == "cogguard.twitter_io.manifest.v1"
    assert manifest.source_path == "external/twitter_io/tweets.csv"
    assert manifest.byte_size == 25604849
    assert manifest.sha256 == "E4D12CC8F56D09FCFBEAC3B09C5D45537B8E390536E3860AFD768DDC651FB8B4"
    assert manifest.columns == EXPECTED_COLUMNS
    assert manifest.rows == 39964
    assert manifest.users == 60
    assert manifest.retweets == 16310
    assert manifest.replies == 8697
    assert manifest.quotes == 4814


def test_case_workbench_fixtures_do_not_commit_twitter_payloads_or_markdown():
    committed_payloads = [
        path
        for path in FIXTURE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".md"}
    ]

    assert committed_payloads == []


def test_scanner_counts_tiny_csv_with_stdlib_csv_and_hashlib(tmp_path):
    from scripts.verify_twitter_benchmark import scan_twitter_benchmark

    csv_path = tmp_path / "tweets.csv"
    _write_tiny_twitter_csv(csv_path)

    manifest = scan_twitter_benchmark(csv_path)

    assert manifest.source_path == str(csv_path)
    assert manifest.byte_size == csv_path.stat().st_size
    assert manifest.sha256 == _sha256(csv_path)
    assert manifest.columns == EXPECTED_COLUMNS
    assert manifest.rows == 3
    assert manifest.users == 2
    assert manifest.retweets == 2
    assert manifest.replies == 1
    assert manifest.quotes == 1


def test_verifier_rejects_statistics_mismatch(tmp_path):
    from scripts.verify_twitter_benchmark import scan_twitter_benchmark, verify_twitter_benchmark

    csv_path = tmp_path / "tweets.csv"
    _write_tiny_twitter_csv(csv_path)
    expected = scan_twitter_benchmark(csv_path).model_copy(update={"rows": 4})

    with pytest.raises(AssertionError, match="rows"):
        verify_twitter_benchmark(csv_path, expected)


def test_twitter_benchmark_manifest_remains_isolated_from_case_acceptance():
    result = asyncio.run(run_acceptance())
    manifest_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    serialized_acceptance = json.dumps(result, ensure_ascii=False).lower()
    assert "twitter" not in serialized_acceptance
    assert manifest_payload["source_path"] not in json.dumps(result, ensure_ascii=False)
