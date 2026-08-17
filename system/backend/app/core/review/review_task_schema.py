"""Torch-free shared labels and claim context helpers for Review boundaries."""

from __future__ import annotations

from typing import Any


ATTACK_AXIS = "attack_hate_offense"
MISINFO_AXIS = "misinfo_claim_risk"
TEACHER_SILVER_SCHEMA = "review-teacher-silver-v1"


def claim_context_text(case: dict[str, Any]) -> str:
    context = case.get("claim_context") or {}
    parts = [
        str(context.get("claim_text", "")).strip(),
        str(context.get("evidence_text", "")).strip(),
    ]
    for link in context.get("evidence_links") or []:
        if isinstance(link, dict):
            parts.extend(
                [
                    str(link.get("position", "")).strip(),
                    str(link.get("mediatype", "")).strip(),
                    str(link.get("link", "")).strip(),
                ]
            )
    return " ".join(part for part in parts if part).strip()


__all__ = ["ATTACK_AXIS", "MISINFO_AXIS", "TEACHER_SILVER_SCHEMA", "claim_context_text"]
