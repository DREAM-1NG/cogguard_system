from __future__ import annotations

import pytest

from app.config import Settings


def test_local_settings_use_ephemeral_jwt_and_disable_preview_by_default():
    settings = Settings(_env_file=None)

    assert settings.BACKEND_ENV == "local"
    assert settings.BACKEND_DEBUG is False
    assert settings.JWT_SECRET_KEY
    assert all(not (field.startswith("PREVIEW") and "AUTH" in field) for field in Settings.model_fields)
    assert settings.DEFAULT_ADMIN_PASSWORD == ""


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


def test_production_uses_jwt_and_admin_seed_without_debug_bypass():
    settings = Settings(
        _env_file=None,
        BACKEND_ENV="production",
        BACKEND_DEBUG=True,
        JWT_SECRET_KEY="production-random-secret",
        DEFAULT_ADMIN_PASSWORD="configured-admin-password",
    )

    assert settings.BACKEND_ENV == "production"
    assert settings.BACKEND_DEBUG is True
    assert settings.JWT_SECRET_KEY == "production-random-secret"
