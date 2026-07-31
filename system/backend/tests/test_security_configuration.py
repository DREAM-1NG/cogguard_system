from __future__ import annotations

import pytest

from app.config import Settings


def test_local_settings_use_ephemeral_jwt_and_disable_preview_by_default():
    settings = Settings(_env_file=None)

    assert settings.BACKEND_ENV == "local"
    assert settings.BACKEND_DEBUG is False
    assert settings.JWT_SECRET_KEY
    assert settings.preview_auth_allowed is False
    assert settings.DEFAULT_ADMIN_PASSWORD == ""


def test_preview_requires_explicit_local_configuration():
    settings = Settings(
        _env_file=None,
        BACKEND_ENV="local",
        BACKEND_DEBUG=True,
        PREVIEW_AUTH_ENABLED=True,
        PREVIEW_AUTH_TOKEN="local-only-random-token",
        JWT_SECRET_KEY="local-random-secret",
    )

    assert settings.preview_auth_allowed is True


def test_production_rejects_missing_jwt_and_admin_seed():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None, BACKEND_ENV="production", JWT_SECRET_KEY="")

    with pytest.raises(ValueError, match="DEFAULT_ADMIN_PASSWORD"):
        Settings(
            _env_file=None,
            BACKEND_ENV="production",
            JWT_SECRET_KEY="production-random-secret",
            DEFAULT_ADMIN_PASSWORD="",
        )


def test_production_disables_preview_even_when_token_is_present():
    settings = Settings(
        _env_file=None,
        BACKEND_ENV="production",
        BACKEND_DEBUG=True,
        PREVIEW_AUTH_ENABLED=True,
        PREVIEW_AUTH_TOKEN="configured-token",
        JWT_SECRET_KEY="production-random-secret",
        DEFAULT_ADMIN_PASSWORD="configured-admin-password",
    )

    assert settings.preview_auth_allowed is False
