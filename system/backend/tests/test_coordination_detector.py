import pandas as pd

from app.core.coordination.detector import detect_groups


def test_detect_groups_counts_unique_contents_for_min_participation():
    df = pd.DataFrame(
        [
            {"object_id": "obj-a", "account_id": "u1", "content_id": "u1-c1", "timestamp_share": 0},
            {"object_id": "obj-b", "account_id": "u1", "content_id": "u1-c1", "timestamp_share": 0},
            {"object_id": "obj-a", "account_id": "u2", "content_id": "u2-c1", "timestamp_share": 5},
            {"object_id": "obj-b", "account_id": "u2", "content_id": "u2-c2", "timestamp_share": 10},
        ]
    )

    result = detect_groups(df, time_window=60, min_participation=2)

    assert result.empty


def test_detect_groups_requires_both_accounts_to_remain_active_after_refilter():
    df = pd.DataFrame(
        [
            {"object_id": "obj-a", "account_id": "u1", "content_id": "u1-c1", "timestamp_share": 0},
            {"object_id": "obj-dead", "account_id": "u1", "content_id": "u1-c2", "timestamp_share": 1},
            {"object_id": "obj-a", "account_id": "u2", "content_id": "u2-c1", "timestamp_share": 5},
            {"object_id": "obj-b", "account_id": "u2", "content_id": "u2-c2", "timestamp_share": 6},
            {"object_id": "obj-b", "account_id": "u3", "content_id": "u3-c1", "timestamp_share": 7},
            {"object_id": "obj-c", "account_id": "u3", "content_id": "u3-c2", "timestamp_share": 8},
            {"object_id": "obj-c", "account_id": "u4", "content_id": "u4-c1", "timestamp_share": 9},
        ]
    )

    result = detect_groups(df, time_window=60, min_participation=2)

    assert result.empty
