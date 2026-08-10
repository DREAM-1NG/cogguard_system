"""Build immutable Chinese corpus and frozen-holdout manifests.

This module is the boundary between Mongo's collected social content and the
account-model training pipeline.  It deliberately emits sanitized text and
stable provenance rather than passing raw platform payloads to a trainer.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import resolve_project_path, settings
from app.db.mongodb import get_mongo_db
from app.core.account_labeling import account_scope_key
from app.models.account_labeling import (
    AccountBehaviorLabelRecord,
    AccountCorpusVersion,
    AccountDetectionCaseRecord,
    AccountFrozenHoldoutMembership,
)
from app.services.event_data import load_event_comments, load_event_posts
from app.utils.exceptions import AppException

__all__ = [
    "CorpusDocument",
    "build_corpus_documents",
    "create_account_corpus_version",
    "freeze_account_holdout",
    "list_account_corpus_versions",
    "list_frozen_account_holdout",
]

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """One deduplicated, sanitized document eligible for DAPT."""

    document_id: str
    text: str
    platform: str
    event_id: str
    source_kind: str
    source_id: str
    account_id: str
    observed_at: str
    text_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_corpus_documents(
    posts: Iterable[Mapping[str, Any]],
    comments: Iterable[Mapping[str, Any]] = (),
    *,
    event_id: str | None = None,
    platform: str | None = None,
    require_chinese: bool = True,
) -> list[CorpusDocument]:
    """Normalize and exact-deduplicate Chinese post/comment text.

    Deduplication is content based across both collections.  This prevents a
    post copied into a comment or collected by multiple crawl jobs from
    receiving extra DAPT weight while retaining the first deterministic source
    record as provenance.
    """

    candidates: list[CorpusDocument] = []
    for source_kind, rows in (("post", posts), ("comment", comments)):
        for row in rows:
            row_platform = str(row.get("platform") or platform or "").strip()
            row_event = str(row.get("event_id") or event_id or "").strip()
            text = _normalize_text(row.get("content") or row.get("text") or row.get("comment_content"))
            if not row_platform or not text or (require_chinese and not _CJK_RE.search(text)):
                continue
            if event_id and row_event != event_id:
                continue
            if platform and row_platform != platform:
                continue
            source_id = str(
                row.get("post_id")
                or row.get("comment_id")
                or row.get("id")
                or _digest((source_kind, row_platform, row_event, text))[:24]
            )
            account_id = str(row.get("author_id") or row.get("user_id") or "").strip()
            text_fingerprint = _digest(("account_corpus.text.v1", text))
            candidates.append(
                CorpusDocument(
                    document_id=_digest(("account_corpus.document.v1", source_kind, row_platform, source_id, text)),
                    text=text,
                    platform=row_platform,
                    event_id=row_event,
                    source_kind=source_kind,
                    source_id=source_id,
                    account_id=account_id,
                    observed_at=str(row.get("timestamp") or row.get("created_at") or ""),
                    text_fingerprint=text_fingerprint,
                )
            )

    by_text: dict[str, CorpusDocument] = {}
    for document in sorted(
        candidates,
        key=lambda item: (
            item.text_fingerprint,
            item.platform,
            item.event_id,
            item.source_kind,
            item.source_id,
        ),
    ):
        by_text.setdefault(document.text_fingerprint, document)
    return sorted(
        by_text.values(),
        key=lambda item: (item.platform, item.event_id, item.observed_at, item.document_id),
    )


async def create_account_corpus_version(
    session: AsyncSession,
    *,
    event_id: str | None = None,
    platform: str | None = None,
    corpus_version_id: str | None = None,
    operator_id: int,
    output_dir: str | Path | None = None,
    require_chinese: bool = True,
) -> dict[str, Any]:
    """Snapshot Mongo content into an immutable, hash-addressed corpus."""

    mongo_db = get_mongo_db()
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    documents = build_corpus_documents(
        posts,
        comments,
        event_id=event_id,
        platform=platform,
        require_chinese=require_chinese,
    )
    if not documents:
        raise AppException(code=400, msg="No qualified Chinese post or comment text is available for corpus creation.")

    version_id = corpus_version_id or f"account-corpus-{uuid4().hex[:12]}"
    target_dir = _resolve_corpus_output_dir(output_dir, version_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = target_dir / "corpus.jsonl"
    input_fingerprint = _digest(tuple(document.to_dict() for document in documents))
    with corpus_path.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps(document.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    token_count, token_count_status, token_count_model = _count_tokens(
        [document.text for document in documents],
        model_path=str(settings.ACCOUNT_ACQUISITION_TEXT_MODEL_PATH or "").strip(),
    )
    manifest = {
        "schema": "cogguard.account-corpus.v1",
        "corpus_version_id": version_id,
        "input_fingerprint": input_fingerprint,
        "document_count": len(documents),
        "character_count": sum(len(document.text) for document in documents),
        "token_count": token_count,
        "token_count_status": token_count_status,
        "token_count_model": token_count_model,
        "platforms": sorted({document.platform for document in documents}),
        "event_ids": sorted({document.event_id for document in documents if document.event_id}),
        "time_range": _time_range(documents),
        "deduplication": "exact_normalized_text_sha256_across_posts_and_comments",
        "source_policy": "repo_owned_mongo_raw_posts_and_raw_comments_chinese_text_only",
        "raw_payload_policy": "raw platform payload is not copied into training artifact",
        "corpus_path": str(corpus_path),
    }
    (target_dir / "corpus_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    record = AccountCorpusVersion(
        corpus_version_id=version_id,
        input_fingerprint=input_fingerprint,
        source_label_count=0,
        manifest_json=json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        status="candidate",
        created_by=operator_id,
    )
    session.add(record)
    await session.flush()
    return {
        "corpus_version_id": record.corpus_version_id,
        "input_fingerprint": record.input_fingerprint,
        "manifest": manifest,
        "status": record.status,
    }


async def freeze_account_holdout(
    session: AsyncSession,
    *,
    corpus_version_id: str,
    operator_id: int,
    fraction: float = 0.2,
    seed: int = 17,
) -> dict[str, Any]:
    """Freeze an account/event-stratified label holdout before training export."""

    if not 0.0 < fraction < 1.0:
        raise AppException(code=400, msg="Frozen holdout fraction must be between 0 and 1.")
    corpus = (
        await session.execute(
            select(AccountCorpusVersion).where(AccountCorpusVersion.corpus_version_id == corpus_version_id)
        )
    ).scalar_one_or_none()
    if corpus is None:
        raise AppException(code=404, msg="Account corpus version not found.")
    statement = (
        select(AccountBehaviorLabelRecord, AccountDetectionCaseRecord)
        .join(AccountDetectionCaseRecord, AccountDetectionCaseRecord.case_id == AccountBehaviorLabelRecord.case_id)
        .where(AccountBehaviorLabelRecord.label_status.in_(("approved", "adjudicated")))
        .where(AccountBehaviorLabelRecord.training_target.in_(("bot", "non_bot")))
        .where(AccountBehaviorLabelRecord.case_fingerprint == AccountDetectionCaseRecord.case_fingerprint)
    )
    corpus_manifest = _loads(corpus.manifest_json)
    manifest_platforms = tuple(
        str(value).strip()
        for value in (corpus_manifest.get("platforms") or ())
        if str(value).strip()
    )
    manifest_events = tuple(
        str(value).strip()
        for value in (corpus_manifest.get("event_ids") or ())
        if str(value).strip()
    )
    if manifest_platforms:
        statement = statement.where(AccountDetectionCaseRecord.platform.in_(manifest_platforms))
    if manifest_events:
        statement = statement.where(AccountDetectionCaseRecord.event_id.in_(manifest_events))
    result = await session.execute(statement)
    candidates = list(result.all())
    if not candidates:
        raise AppException(code=400, msg="No approved account labels are available for a frozen holdout.")
    existing_rows = list(
        (
            await session.execute(
                select(AccountFrozenHoldoutMembership).where(
                    AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id
                )
            )
        ).scalars().all()
    )
    existing = {(str(row.case_id), str(row.label_id)) for row in existing_rows}
    existing_accounts = {
        _holdout_account_scope(row)
        for row in existing_rows
        if row.account_id
    }
    eligible = [
        (label, case)
        for label, case in candidates
        if (str(case.case_id), str(label.label_id)) not in existing
        and account_scope_key(case.platform, case.account_id) not in existing_accounts
    ]
    if not eligible:
        return {"corpus_version_id": corpus_version_id, "membership_count": len(existing_rows), "created": 0}

    # Stable randomization is reproducible but independent of database row order.
    rng = random.Random(seed)
    shuffled = sorted(eligible, key=lambda pair: _digest((seed, pair[1].case_id, pair[0].label_id)))
    rng.shuffle(shuffled)
    target_count = max(1, round(len(shuffled) * fraction))
    selected = _stratified_selection(shuffled, target_count)
    for label, case in selected:
        session.add(
            AccountFrozenHoldoutMembership(
                membership_id=f"account-holdout-{uuid4().hex[:16]}",
                corpus_version_id=corpus_version_id,
                account_id=case.account_id,
                platform=case.platform,
                case_id=case.case_id,
                label_id=label.label_id,
                stratum_json=json.dumps(
                    {
                        "account_id": case.account_id,
                        "platform": case.platform,
                        "event_id": case.event_id,
                        "training_target": label.training_target,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                frozen_by=operator_id,
            )
        )
    await session.flush()
    return {
        "corpus_version_id": corpus_version_id,
        "membership_count": len(existing_rows) + len(selected),
        "created": len(selected),
        "fraction": fraction,
        "seed": seed,
        "account_disjoint": True,
    }


async def list_account_corpus_versions(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(AccountCorpusVersion).order_by(AccountCorpusVersion.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "corpus_version_id": row.corpus_version_id,
            "input_fingerprint": row.input_fingerprint,
            "source_label_count": row.source_label_count,
            "manifest": _loads(row.manifest_json),
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


async def list_frozen_account_holdout(
    session: AsyncSession,
    *,
    corpus_version_id: str,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(AccountFrozenHoldoutMembership)
            .where(AccountFrozenHoldoutMembership.corpus_version_id == corpus_version_id)
            .order_by(AccountFrozenHoldoutMembership.created_at.asc())
        )
    ).scalars().all()
    return [
        {
            "membership_id": row.membership_id,
            "corpus_version_id": row.corpus_version_id,
            "account_id": row.account_id,
            "platform": row.platform or _loads(row.stratum_json).get("platform"),
            "case_id": row.case_id,
            "label_id": row.label_id,
            "stratum": _loads(row.stratum_json),
            "frozen_at": row.frozen_at.isoformat() if row.frozen_at else None,
        }
        for row in rows
    ]


def _stratified_selection(rows: list[tuple[Any, Any]], target_count: int) -> list[tuple[Any, Any]]:
    """Select unique accounts while retaining platform/event/class strata."""

    groups: dict[tuple[str, str, str], list[tuple[Any, Any]]] = {}
    for label, case in rows:
        groups.setdefault((str(case.platform), str(case.event_id), str(label.training_target)), []).append((label, case))
    selected: list[tuple[Any, Any]] = []
    selected_accounts: set[str] = set()
    for group_key in sorted(groups):
        group = groups[group_key]
        if len(selected) >= target_count:
            break
        for label, case in group:
            account_scope = account_scope_key(case.platform, case.account_id)
            if account_scope not in selected_accounts:
                selected.append((label, case))
                selected_accounts.add(account_scope)
                break
    if len(selected) < target_count:
        for label, case in rows:
            if len(selected) >= target_count:
                break
            account_scope = account_scope_key(case.platform, case.account_id)
            if account_scope in selected_accounts:
                continue
            selected.append((label, case))
            selected_accounts.add(account_scope)
    return selected[:target_count]


def _normalize_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _loads(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _holdout_account_scope(row: AccountFrozenHoldoutMembership) -> str:
    """Read platform from the column and support pre-migration rows."""

    stratum = _loads(row.stratum_json)
    return account_scope_key(
        str(row.platform or stratum.get("platform") or "unknown"),
        str(row.account_id or ""),
    )


def _digest(values: Any) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _time_range(documents: Iterable[CorpusDocument]) -> dict[str, str]:
    values = sorted(document.observed_at for document in documents if document.observed_at)
    return {"first": values[0], "last": values[-1]} if values else {"first": "", "last": ""}


def _count_tokens(texts: list[str], *, model_path: str) -> tuple[int | None, str, str]:
    """Count with the configured local tokenizer, never with a character proxy."""

    if not model_path:
        return None, "requires_local_tokenizer", ""
    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, use_fast=True)
        encoded = tokenizer(texts, add_special_tokens=True, truncation=False, padding=False)
        input_ids = encoded.get("input_ids")
        if not isinstance(input_ids, list):
            return None, "tokenizer_output_invalid", model_path
        return sum(len(item) for item in input_ids), "counted_with_local_tokenizer", model_path
    except Exception as error:
        return None, f"tokenizer_unavailable:{type(error).__name__}", model_path


def _resolve_corpus_output_dir(output_dir: str | Path | None, version_id: str) -> Path:
    root = resolve_project_path(settings.MODEL_ARTIFACT_ROOT)
    requested = Path(output_dir) if output_dir else Path("account_corpus") / version_id
    if requested.is_absolute() or ".." in requested.parts:
        raise AppException(code=400, msg="Account corpus output_dir must stay inside MODEL_ARTIFACT_ROOT.")
    target = (root / requested).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise AppException(code=400, msg="Account corpus output_dir must stay inside MODEL_ARTIFACT_ROOT.") from exc
    return target
