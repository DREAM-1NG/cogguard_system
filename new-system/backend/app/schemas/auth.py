"""认证相关的请求 / 响应数据模式。"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """用户登录请求体。"""
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    """用户注册请求体。"""
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """登录 / 刷新成功后返回的令牌对。"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """令牌刷新请求体。"""
    refresh_token: str


class UserInfo(BaseModel):
    """用户信息响应体（脱敏，不含密码）。"""
    id: int
    username: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
