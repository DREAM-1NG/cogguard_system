"""认证模块测试。

覆盖注册、登录、Token 鉴权、Token 刷新等场景，
需要 MySQL 测试数据库（不可用时自动跳过）。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(setup_database, client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "pass123456"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["username"] == "newuser"
    assert body["data"]["role"] == "analyst"


@pytest.mark.asyncio
async def test_register_duplicate_username(setup_database, client: AsyncClient):
    payload = {"username": "dupuser", "email": "dup@example.com", "password": "pass123456"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(setup_database, client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "loginuser", "email": "login@example.com", "password": "pass123456"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "loginuser", "password": "pass123456"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]


@pytest.mark.asyncio
async def test_login_wrong_password(setup_database, client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "wrongpw", "email": "wrong@example.com", "password": "pass123456"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "wrongpw", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_profile_with_token(setup_database, client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "profuser", "email": "prof@example.com", "password": "pass123456"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "profuser", "password": "pass123456"},
    )
    token = login_resp.json()["data"]["access_token"]

    resp = await client.get(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "profuser"


@pytest.mark.asyncio
async def test_profile_without_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/profile")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_token(setup_database, client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "refreshuser", "email": "refresh@example.com", "password": "pass123456"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "refreshuser", "password": "pass123456"},
    )
    refresh_tok = login_resp.json()["data"]["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]
