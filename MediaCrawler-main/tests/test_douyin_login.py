import pytest

from media_platform.douyin.client import DouYinClient
from media_platform.douyin.login import DouYinLogin, has_logged_in_state


class FakePage:
    def __init__(self, states, url="https://www.douyin.com/"):
        self._states = states
        self._index = 0
        self.url = url

    @property
    def state(self):
        return self._states[self._index]

    async def title(self):
        return self.state["title"]

    async def evaluate(self, script):
        return self.state.get("local_storage", {})

    def advance_state(self):
        if self._index < len(self._states) - 1:
            self._index += 1


class FakeBrowserContext:
    def __init__(self, pages, cookies=None):
        self.pages = pages
        self._cookies = cookies or []

    async def cookies(self):
        return self._cookies


def test_has_logged_in_state_rejects_weak_login_markers_without_session_cookie():
    assert not has_logged_in_state(
        {"HasUserLogin": "1"},
        {"LOGIN_STATUS": "0"},
        page_title="抖音",
        page_url="https://www.douyin.com/",
    )
    assert not has_logged_in_state(
        {},
        {"LOGIN_STATUS": "true"},
        page_title="抖音",
        page_url="https://www.douyin.com/",
    )


def test_has_logged_in_state_accepts_persisted_session_after_verification_clears():
    assert has_logged_in_state(
        {"xmst": "token"},
        {"sessionid_ss": "session-token"},
        page_title="抖音",
        page_url="https://www.douyin.com/",
    )


def test_has_logged_in_state_rejects_verification_interstitial():
    assert not has_logged_in_state(
        {"xmst": "token"},
        {"sessionid_ss": "session-token", "LOGIN_STATUS": "1"},
        page_title="验证码中间页",
        page_url="https://www.douyin.com/",
    )


@pytest.mark.asyncio
async def test_check_login_state_retries_after_slider_verification():
    page = FakePage(
        [
            {"title": "验证码中间页", "local_storage": {"xmst": "token"}},
            {"title": "抖音", "local_storage": {"HasUserLogin": "1", "xmst": "token"}},
        ]
    )
    browser_context = FakeBrowserContext(
        pages=[page],
        cookies=[{"name": "sessionid_ss", "value": "session-token"}],
    )
    login = DouYinLogin(
        login_type="qrcode",
        browser_context=browser_context,
        context_page=page,
    )

    slider_calls = []

    async def fake_check_page_display_slider(*args, **kwargs):
        slider_calls.append((args, kwargs))
        page.advance_state()

    login.check_page_display_slider = fake_check_page_display_slider  # type: ignore[method-assign]

    assert await login.check_login_state(max_attempts=3, wait_seconds=0) is True
    assert len(slider_calls) == 1


@pytest.mark.asyncio
async def test_client_pong_accepts_persisted_session_cookie():
    page = FakePage(
        [{"title": "抖音", "local_storage": {"xmst": "token"}}],
    )
    browser_context = FakeBrowserContext(
        pages=[page],
        cookies=[{"name": "sessionid_ss", "value": "session-token"}],
    )
    client = DouYinClient(
        headers={},
        playwright_page=page,
        cookie_dict={},
    )

    assert await client.pong(browser_context) is True
