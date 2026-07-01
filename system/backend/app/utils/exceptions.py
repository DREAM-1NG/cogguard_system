"""全局异常定义与处理器。

定义业务异常层次结构（AppException 及其子类），并提供 FastAPI
全局异常处理器，将异常转换为统一的 JSON 响应格式。
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """业务异常基类，携带 HTTP 状态码和错误消息。"""
    def __init__(self, code: int = 400, msg: str = "Bad Request"):
        self.code = code
        self.msg = msg


class NotFoundError(AppException):
    def __init__(self, msg: str = "Resource not found"):
        super().__init__(code=404, msg=msg)


class AuthError(AppException):
    def __init__(self, msg: str = "Authentication failed"):
        super().__init__(code=401, msg=msg)


class ForbiddenError(AppException):
    def __init__(self, msg: str = "Permission denied"):
        super().__init__(code=403, msg=msg)


class ConflictError(AppException):
    def __init__(self, msg: str = "Resource already exists"):
        super().__init__(code=409, msg=msg)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "data": None, "msg": exc.msg},
    )


async def generic_exception_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": 500, "data": None, "msg": "服务暂不可用，请稍后重试"},
    )
