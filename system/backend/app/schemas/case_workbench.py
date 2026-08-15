from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CaseLifecycle(StrEnum):
    DRAFT="draft"; COLLECTING="collecting"; EVIDENCE_READY="evidence_ready"; ANALYZING="analyzing"; AWAITING_REVIEW="awaiting_review"; ACTIONING="actioning"; READY_TO_CLOSE="ready_to_close"; CLOSED="closed"
class AuthorityTier(StrEnum):
    GOVERNMENT_OFFICIAL="government_official"; CENTRAL_MAINSTREAM_MEDIA="central_mainstream_media"; PROVINCIAL_OFFICIAL_MEDIA="provincial_official_media"
class ClaimRole(StrEnum): PRIMARY="primary"; SUPPORTING="supporting"
class ActionState(StrEnum): PENDING="pending"; COMPLETED="completed"; WAIVED="waived"
class CaseCreate(BaseModel): event_id: str; title: str
class AuthoritySourceCreate(BaseModel): name: str; url: str
class AuthorityReview(BaseModel): decision: str; tier: AuthorityTier | None = None
class AuthoritySourceAccountCreate(BaseModel): platform: str; author_id: str; display_name_snapshot: str; verification_snapshot: dict[str, Any] = Field(default_factory=dict)
class ClaimCreate(BaseModel):
    authority_source_id: str
    exact_quote: str
    quote_start: int
    quote_end: int
    source_url: str
    account: str
    published_at: datetime | None = None
    role: ClaimRole

    @field_validator("source_url")
    @classmethod
    def source_url_must_not_be_blank(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("source_url")
        return text
class RunRequest(BaseModel): snapshot_or_run_id: str | None = None
class VerdictRequest(BaseModel): verdict: dict[str, Any]; approved: bool = False
class ActionCreate(BaseModel): description: str; required: bool = False
class ActionUpdate(BaseModel): state: ActionState; waiver_reason: str | None = None
class CloseRequest(BaseModel): closure_note: str = Field(min_length=1)
class ProductOut(BaseModel): model_config = ConfigDict(from_attributes=True)
