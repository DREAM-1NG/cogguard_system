"""统一 API 响应格式工具。

所有接口返回 ``{"code": 0, "data": ..., "msg": "ok"}`` 格式，
code=0 表示成功，非零表示具体错误码。
"""

from typing import Any


def success(data: Any = None, msg: str = "ok") -> dict:
    """构造成功响应。"""
    return {"code": 0, "data": data, "msg": msg}


def error(code: int = 400, msg: str = "error", data: Any = None) -> dict:
    """构造错误响应。"""
    return {"code": code, "data": data, "msg": msg}
