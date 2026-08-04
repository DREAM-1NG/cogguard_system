"""Domain language for Chinese account detection labels and cases."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "AccountBehaviorLabel",
    "AccountDetectionCase",
    "NormalizedAccountBehaviorLabel",
    "build_account_detection_cases",
    "normalize_account_behavior_label",
]


class AccountBehaviorLabel(str, Enum):
    """Observable behavior labels allowed in the account-detection loop."""

    HUMAN = "human"
    BOT = "bot"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class NormalizedAccountBehaviorLabel:
    """Normalized label plus its supervised-training target."""

    behavior_label: str
    training_target: str
    review_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AccountDetectionCase:
    """One platform-scoped account case for analyst labeling."""

    case_id: str
    account_id: str
    platform: str
    event_id: str
    author_name: str
    text: str
    post_ids: list[str]
    evidence_post_ids: list[str]
    post_count: int
    first_seen_at: str
    last_seen_at: str
    case_fingerprint: str
    provenance: dict[str, Any] = field(default_factory=dict)
    label_source_policy: str = "analyst_observed_behavior_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TRAINING_TARGETS = {
    AccountBehaviorLabel.HUMAN.value: "non_bot",
    AccountBehaviorLabel.BOT.value: "bot",
    AccountBehaviorLabel.INSUFFICIENT_EVIDENCE.value: "abstain",
}


def normalize_account_behavior_label(label: str | AccountBehaviorLabel) -> NormalizedAccountBehaviorLabel:
    """Validate a label and map it to a training target."""

    value = label.value if isinstance(label, AccountBehaviorLabel) else str(label)
    if value not in _TRAINING_TARGETS:
        raise ValueError(
            "Account labels must be human, bot, or insufficient_evidence. Use reason_tags for "
            "evidence such as coordination, spam behavior, or organization/media context; "
            "identity, intent, ideology, nationality, and attribution labels are not allowed."
        )
    review_policy = "training_eligible" if _TRAINING_TARGETS[value] != "abstain" else "needs_evidence"
    return NormalizedAccountBehaviorLabel(
        behavior_label=value,
        training_target=_TRAINING_TARGETS[value],
        review_policy=review_policy,
    )


def build_account_detection_cases(
    posts: list[dict[str, Any]],
    *,
    event_id: str | None = None,
    platform: str | None = None,
    max_posts_per_case: int = 64,
) -> list[AccountDetectionCase]:
    """Build stable account-level cases from normalized social-media posts."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        account_id = str(post.get("author_id") or post.get("user_id") or "").strip()
        post_platform = str(post.get("platform") or platform or "").strip()
        post_event = str(post.get("event_id") or event_id or "").strip()
        if not account_id or not post_platform:
            continue
        if event_id and post_event != event_id:
            continue
        if platform and post_platform != platform:
            continue
        grouped[(post_platform, account_id)].append(post)

    cases = [
        _build_case(
            account_id=account_id,
            platform=case_platform,
            event_id=event_id or _first_non_empty(row.get("event_id") for row in rows),
            rows=rows,
            max_posts_per_case=max_posts_per_case,
        )
        for (case_platform, account_id), rows in grouped.items()
    ]
    return sorted(cases, key=lambda case: (case.platform, case.account_id, case.case_id))


def _build_case(
    *,
    account_id: str,
    platform: str,
    event_id: str,
    rows: list[dict[str, Any]],
    max_posts_per_case: int,
) -> AccountDetectionCase:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("timestamp") or ""),
            str(row.get("post_id") or row.get("id") or ""),
        ),
    )
    sampled = ordered[:max_posts_per_case]
    post_ids = [str(row.get("post_id") or row.get("id") or "") for row in sampled if row.get("post_id") or row.get("id")]
    contents = [str(row.get("content") or row.get("text") or "").strip() for row in sampled]
    fingerprint = _case_fingerprint(account_id, platform, event_id, sampled)
    author_name = _first_non_empty(row.get("author_name") or row.get("nickname") for row in sampled) or account_id
    timestamps = [str(row.get("timestamp") or "") for row in sampled if row.get("timestamp")]
    return AccountDetectionCase(
        case_id=f"account-detection-case-{fingerprint[:16]}",
        account_id=account_id,
        platform=platform,
        event_id=event_id,
        author_name=author_name,
        text="\n".join(content for content in contents if content),
        post_ids=post_ids,
        evidence_post_ids=post_ids[:10],
        post_count=len(rows),
        first_seen_at=min(timestamps) if timestamps else "",
        last_seen_at=max(timestamps) if timestamps else "",
        case_fingerprint=fingerprint,
        provenance={
            "source": "mongo.raw_posts",
            "input_post_count": len(rows),
            "max_posts_per_case": max_posts_per_case,
        },
    )


def _case_fingerprint(account_id: str, platform: str, event_id: str, rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for value in ("account_detection_case.v1", account_id, platform, event_id):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    for row in rows:
        for key in ("post_id", "id", "timestamp", "content", "text"):
            digest.update(str(row.get(key) or "").encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def _first_non_empty(values) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
