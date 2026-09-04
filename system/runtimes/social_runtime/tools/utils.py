# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/utils.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


import argparse
import importlib
import logging
import sys


_LAZY_EXPORTS = {
    "find_login_qrcode": (".crawler_util", "find_login_qrcode"),
    "find_qrcode_img_from_canvas": (".crawler_util", "find_qrcode_img_from_canvas"),
    "show_qrcode": (".crawler_util", "show_qrcode"),
    "get_user_agent": (".crawler_util", "get_user_agent"),
    "get_mobile_user_agent": (".crawler_util", "get_mobile_user_agent"),
    "convert_cookies": (".crawler_util", "convert_cookies"),
    "convert_str_cookie_to_dict": (".crawler_util", "convert_str_cookie_to_dict"),
    "match_interact_info_count": (".crawler_util", "match_interact_info_count"),
    "format_proxy_info": (".crawler_util", "format_proxy_info"),
    "extract_text_from_html": (".crawler_util", "extract_text_from_html"),
    "extract_url_params_to_dict": (".crawler_util", "extract_url_params_to_dict"),
    "Slide": (".slider_util", "Slide"),
    "get_track_simple": (".slider_util", "get_track_simple"),
    "get_tracks": (".slider_util", "get_tracks"),
    "get_current_timestamp": (".time_util", "get_current_timestamp"),
    "get_current_time": (".time_util", "get_current_time"),
    "get_current_time_hour": (".time_util", "get_current_time_hour"),
    "get_current_date": (".time_util", "get_current_date"),
    "get_time_str_from_unix_time": (".time_util", "get_time_str_from_unix_time"),
    "get_date_str_from_unix_time": (".time_util", "get_date_str_from_unix_time"),
    "get_unix_time_from_time_str": (".time_util", "get_unix_time_from_time_str"),
    "get_unix_timestamp": (".time_util", "get_unix_timestamp"),
    "rfc2822_to_china_datetime": (".time_util", "rfc2822_to_china_datetime"),
    "rfc2822_to_timestamp": (".time_util", "rfc2822_to_timestamp"),
}


def init_loging_config():
    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s (%(filename)s:%(lineno)d) - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _logger = logging.getLogger("MediaCrawler")
    _logger.setLevel(level)

    # Disable httpx INFO level logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return _logger


logger = init_loging_config()


def __getattr__(name):
    if name == "utils":
        return sys.modules[__name__]
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = importlib.import_module(target[0], __package__)
    value = getattr(module, target[1])
    globals()[name] = value
    return value


__all__ = ["init_loging_config", "logger", "str2bool", "utils", *_LAZY_EXPORTS]

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')
