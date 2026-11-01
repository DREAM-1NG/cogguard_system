# -*- coding: utf-8 -*-
"""
Twitter/X GraphQL API 客户端

支持两种模式:
1. Guest Token 模式 (默认): 无需认证，可访问公开推文
2. Cookie 认证模式: 需要登录 Cookie，可访问受保护推文
"""
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote

from .twitter_types import TweetData

logger = logging.getLogger(__name__)

# Twitter/X 固定的 Bearer Token
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# GraphQL Query IDs
QUERY_IDS = {
    "TweetResultByRestId": "Xl5pC_lBk_gcO2ItU39DQw",
    "TweetDetail": "97JF30KziU00483E_8elBA",
}

# GraphQL 特性标志 (2025-01 更新)
FEATURES = {
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    # 2025-01 新增必需字段
    "responsive_web_jetfuel_frame": False,
    "responsive_web_grok_analysis_button_from_backend": False,
    "responsive_web_profile_redirect_enabled": False,
    "rweb_video_screen_enabled": False,
    "responsive_web_grok_show_grok_translated_post": False,
    "responsive_web_grok_analyze_post_followups_enabled": False,
    "responsive_web_grok_imagine_annotation_enabled": False,
    "responsive_web_grok_share_attachment_enabled": False,
    "responsive_web_grok_image_annotation_enabled": False,
    "premium_content_api_read_enabled": False,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
}


@dataclass
class TwitterCredentials:
    """Twitter 认证凭据 (可选，用于访问受保护推文)"""
    auth_token: str
    ct0: str  # CSRF token
    full_cookie: str = ""  # 完整的 Cookie 字符串

    @classmethod
    def from_cookie_string(cls, cookie_str: str) -> "TwitterCredentials":
        """从完整 Cookie 字符串中解析凭据"""
        cookies = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()

        auth_token = cookies.get("auth_token", "")
        ct0 = cookies.get("ct0", "")

        if not auth_token or not ct0:
            raise ValueError(
                "Cookie 中缺少 auth_token 或 ct0，请确保已登录 x.com 并粘贴完整的 Cookie"
            )

        return cls(auth_token=auth_token, ct0=ct0, full_cookie=cookie_str)

    @classmethod
    def from_env(cls) -> Optional["TwitterCredentials"]:
        """从环境变量获取凭据"""
        # 优先检查完整 Cookie
        cookie_str = os.environ.get("TWITTER_COOKIE", "")
        if cookie_str:
            try:
                return cls.from_cookie_string(cookie_str)
            except ValueError:
                pass

        # 回退到分开的环境变量
        auth_token = os.environ.get("TWITTER_AUTH_TOKEN", "")
        ct0 = os.environ.get("TWITTER_CT0", "")

        if auth_token and ct0:
            return cls(auth_token=auth_token, ct0=ct0)

        return None


class TwitterClient:
    """Twitter GraphQL API 客户端

    支持两种模式:
    1. Guest Token 模式 (默认): 无需认证，可访问公开推文
    2. Cookie 认证模式: 需要登录 Cookie，可访问受保护推文
    """

    BASE_URL = "https://x.com/i/api/graphql"
    GUEST_TOKEN_URL = "https://api.x.com/1.1/guest/activate.json"

    def __init__(self, credentials: Optional[TwitterCredentials] = None):
        self.credentials = credentials
        self.guest_token: Optional[str] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_guest_token(self) -> str:
        """获取 guest token"""
        if self.guest_token:
            return self.guest_token

        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            import requests as curl_requests

        response = curl_requests.post(
            self.GUEST_TOKEN_URL,
            headers={"authorization": f"Bearer {BEARER_TOKEN}"},
            timeout=15,
            impersonate="chrome" if hasattr(curl_requests, "post") else None,
        )

        if response.status_code != 200:
            raise RuntimeError(f"获取 guest token 失败: HTTP {response.status_code}")

        data = response.json()
        self.guest_token = data.get("guest_token", "")
        if not self.guest_token:
            raise RuntimeError("获取 guest token 失败: 响应中没有 token")

        self.logger.debug("Got guest token: %s", self.guest_token)
        return self.guest_token

    def _build_guest_headers(self) -> Dict[str, str]:
        """构建 Guest Token 模式的请求头"""
        return {
            "authorization": f"Bearer {BEARER_TOKEN}",
            "x-guest-token": self._get_guest_token(),
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "origin": "https://x.com",
            "referer": "https://x.com/",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
        }

    def _build_auth_headers(self) -> Dict[str, str]:
        """构建 Cookie 认证模式的请求头"""
        if not self.credentials:
            raise ValueError("Cookie 认证模式需要提供凭据")

        cookie = self.credentials.full_cookie if self.credentials.full_cookie else f"auth_token={self.credentials.auth_token}; ct0={self.credentials.ct0}"
        return {
            "authorization": f"Bearer {BEARER_TOKEN}",
            "x-csrf-token": self.credentials.ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
            "cookie": cookie,
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "origin": "https://x.com",
            "referer": "https://x.com/",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
        }

    def _build_tweet_result_url(self, tweet_id: str) -> str:
        """构建 TweetResultByRestId GraphQL 请求 URL"""
        variables = {
            "tweetId": tweet_id,
            "withCommunity": False,
            "includePromotedContent": False,
            "withVoice": False,
        }

        params = {
            "variables": json.dumps(variables, separators=(",", ":")),
            "features": json.dumps(FEATURES, separators=(",", ":")),
        }

        query_string = "&".join(f"{k}={quote(v)}" for k, v in params.items())
        query_id = QUERY_IDS["TweetResultByRestId"]
        return f"{self.BASE_URL}/{query_id}/TweetResultByRestId?{query_string}"

    def get_tweet(self, tweet_id: str) -> TweetData:
        """获取推文详情

        优先使用 Guest Token 模式访问公开推文，
        如果失败且提供了认证凭据，则尝试认证模式。
        """
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            import requests as curl_requests

        url = self._build_tweet_result_url(tweet_id)
        self.logger.info("Fetching tweet %s", tweet_id)

        last_error = None
        last_data = None

        # 首先尝试 Guest Token 模式
        try:
            headers = self._build_guest_headers()
            response = curl_requests.get(
                url,
                headers=headers,
                timeout=15,
                impersonate="chrome" if hasattr(curl_requests, "get") else None,
            )

            if response.status_code == 200:
                data = response.json()
                last_data = data
                tweet_result = data.get("data", {}).get("tweetResult", {})
                if tweet_result and tweet_result.get("result"):
                    return TweetData.from_tweet_result(tweet_result)
                # 空结果，可能是私密推文，尝试认证模式
                self.logger.debug("Empty result with guest token, trying auth mode")
            else:
                self.logger.debug("Guest token request failed: HTTP %s", response.status_code)
        except Exception as e:
            last_error = str(e)
            self.logger.debug("Guest token mode failed: %s", last_error)

        # 如果有认证凭据，尝试认证模式
        if self.credentials:
            self.logger.info("Trying authenticated mode for tweet %s", tweet_id)
            headers = self._build_auth_headers()
            response = curl_requests.get(
                url,
                headers=headers,
                timeout=15,
                impersonate="chrome" if hasattr(curl_requests, "get") else None,
            )

            if response.status_code == 401:
                raise ValueError("认证失败，请检查 Cookie 是否有效或是否已过期")
            elif response.status_code == 403:
                raise ValueError("访问被拒绝，可能需要重新登录 x.com")
            elif response.status_code != 200:
                raise RuntimeError(f"请求失败: HTTP {response.status_code}")

            data = response.json()
            last_data = data
            tweet_result = data.get("data", {}).get("tweetResult", {})
            if tweet_result and tweet_result.get("result"):
                return TweetData.from_tweet_result(tweet_result)

        # 检查是否有 API 错误
        if last_data and "errors" in last_data:
            error_msg = last_data["errors"][0].get("message", "Unknown error")
            raise ValueError(f"API 错误: {error_msg}")

        # 如果有之前的错误，包含在消息中
        if last_error:
            raise ValueError(f"找不到推文 {tweet_id}: {last_error}")

        raise ValueError(f"找不到推文 {tweet_id}，可能已被删除或设为私密")


def extract_tweet_id(url: str) -> str:
    """从 Twitter/X URL 中提取推文 ID"""
    patterns = [
        r"(?:twitter|x)\.com/\w+/status/(\d+)",
        r"(?:twitter|x)\.com/i/web/status/(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(f"无法从 URL 中提取推文 ID: {url}")
