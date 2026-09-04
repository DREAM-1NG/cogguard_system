"""Product-safe contracts for the authenticated system operations page."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ServicePurpose = Literal["text_review", "media_verification", "source_retrieval"]


class ServiceConfigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    purpose: ServicePurpose
    endpoint: str = ""
    service_identifier: str = ""
    protocol: str = "chat_completions"
    credential: str | None = None
    supports_media: bool = False


class ServiceActivationRequest(BaseModel):
    enabled: bool = True


__all__ = [
    "ServiceActivationRequest",
    "ServiceConfigCreateRequest",
    "ServicePurpose",
]
