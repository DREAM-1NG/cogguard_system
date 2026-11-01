"""Regression tests for the social runtime tools import boundary."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "runtimes" / "social_runtime"

IMPORT_SCRIPT = textwrap.dedent(
    """
    import sys
    import types


    def install_import_stubs():
        httpx = types.ModuleType("httpx")

        class AsyncClient:
            pass

        httpx.AsyncClient = AsyncClient
        sys.modules["httpx"] = httpx
        sys.modules["cv2"] = types.ModuleType("cv2")
        sys.modules["numpy"] = types.ModuleType("numpy")

        pil = types.ModuleType("PIL")
        pil.__path__ = []
        for name in ("Image", "ImageDraw", "ImageShow"):
            module = types.ModuleType(f"PIL.{name}")
            setattr(pil, name, module)
            sys.modules[module.__name__] = module
        sys.modules["PIL"] = pil

        playwright = types.ModuleType("playwright")
        playwright.__path__ = []
        async_api = types.ModuleType("playwright.async_api")
        async_api.Cookie = dict
        async_api.Page = object
        playwright.async_api = async_api
        sys.modules["playwright"] = playwright
        sys.modules["playwright.async_api"] = async_api


    install_import_stubs()
    first, second = sys.argv[1].split(",")
    __import__(first)
    __import__(second)

    import tools.crawler_util as crawler_util
    import tools.utils as utils

    crawler_exports = {
        "find_login_qrcode",
        "find_qrcode_img_from_canvas",
        "show_qrcode",
        "get_user_agent",
        "get_mobile_user_agent",
        "convert_cookies",
        "convert_str_cookie_to_dict",
        "match_interact_info_count",
        "format_proxy_info",
        "extract_text_from_html",
        "extract_url_params_to_dict",
    }
    utility_exports = crawler_exports | {
        "Slide",
        "get_track_simple",
        "get_tracks",
        "get_current_timestamp",
        "get_current_time",
        "get_current_time_hour",
        "get_current_date",
        "get_time_str_from_unix_time",
        "get_date_str_from_unix_time",
        "get_unix_time_from_time_str",
        "get_unix_timestamp",
        "rfc2822_to_china_datetime",
        "rfc2822_to_timestamp",
        "init_loging_config",
        "logger",
        "str2bool",
        "utils",
    }

    assert set(crawler_util.__all__) == crawler_exports
    assert set(utils.__all__) == utility_exports
    assert all(hasattr(utils, name) for name in utility_exports)
    assert utils.utils is utils
    assert not {
        "base64",
        "json",
        "httpx",
        "Image",
        "ImageDraw",
        "ImageShow",
        "Cookie",
        "Page",
        "make_async_client",
    }.intersection(vars(utils))
    """
).strip()


def test_social_runtime_tool_modules_are_order_independent():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(RUNTIME_ROOT), env.get("PYTHONPATH", "")))
    )

    for order in (
        "tools.utils,tools.crawler_util",
        "tools.crawler_util,tools.utils",
    ):
        result = subprocess.run(
            [sys.executable, "-c", IMPORT_SCRIPT, order],
            cwd=RUNTIME_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"import order {order!r} failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
