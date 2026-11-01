from pathlib import Path

from research.social_bot_detection.contracts import AccountSample
from research.social_bot_detection.dataset import normalize_account_text
from research.social_bot_detection.dataset import split_samples


def test_normalize_account_text_preserves_chinese_content_and_post_boundaries():
    text = " 第一条\r\n\r\n第二条  \t\n"
    assert normalize_account_text(text) == "第一条\n第二条"


def test_split_samples_is_stratified_and_deterministic():
    samples = [
        AccountSample(str(index), index % 2, f"文本 {index}", 1, "hash", "utf-8")
        for index in range(20)
    ]
    first = split_samples(samples, seed=7)
    second = split_samples(samples, seed=7)
    assert {key: [item.account_id for item in value] for key, value in first.items()} == {
        key: [item.account_id for item in value] for key, value in second.items()
    }
    counts = {key: len(value) for key, value in first.items()}
    assert sum(counts.values()) == len(samples)
    assert counts["train"] == 13
    assert counts["validation"] + counts["test"] == 7
    for split in first.values():
        assert {item.label for item in split} == {0, 1}
