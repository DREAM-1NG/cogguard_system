from app.core.account_profiler import build_account_profiles


def _post(account_id: str, *, profile=None, raw_data=None, platform="weibo"):
    return {
        "event_id": "event-1",
        "platform": platform,
        "post_id": f"{account_id}-1",
        "author_id": account_id,
        "author_name": f"name-{account_id}",
        "timestamp": "2026-05-21T00:00:00+00:00",
        "content": "hello",
        "author_profile": profile or {},
        "raw_data": raw_data or {},
        "likes": 0,
        "reposts": 0,
        "comments_count": 0,
        "hashtags": [],
        "url": "",
    }


def test_account_profile_uses_collected_profile_url():
    profiles = build_account_profiles([
        _post("123", profile={"profile_url": "https://weibo.com/u/123"})
    ])

    assert profiles[0]["user_url"] == "https://weibo.com/u/123"


def test_account_profile_builds_platform_user_url_when_missing():
    profiles = build_account_profiles([_post("456")])

    assert profiles[0]["user_url"] == "https://weibo.com/u/456"


def test_account_profile_builds_non_weibo_user_urls_when_missing():
    xhs_profile = build_account_profiles([_post("xhs-user", platform="xhs")])[0]
    douyin_profile = build_account_profiles([_post("douyin-user", platform="douyin")])[0]

    assert xhs_profile["user_url"] == "https://www.xiaohongshu.com/user/profile/xhs-user"
    assert douyin_profile["user_url"] == "https://www.douyin.com/user/douyin-user"


def test_account_profiles_do_not_merge_equal_ids_across_platforms():
    profiles = build_account_profiles(
        [
            _post("same-id", platform="weibo"),
            _post("same-id", platform="douyin"),
        ]
    )

    assert {(profile["platform"], profile["account_id"]) for profile in profiles} == {
        ("weibo", "same-id"),
        ("douyin", "same-id"),
    }
