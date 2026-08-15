"""Read-only Claim Response Landscape projection for Propagation Analysis."""

from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analysis.registry import (
    AnalysisRegistry,
    SEMANTIC_ARTIFACT_KEY,
    SqlAlchemyAnalysisStore,
)
from app.db.mongodb import get_mongo_db
from app.db.mysql import async_session_factory
from app.models.case_workbench import AuthoritySource, AuthoritySourceAccount, CaseClaim, CaseRecord
from app.services import propagation_observation_service
from app.services.event_data import (
    analysis_scope_metadata,
    load_event_comments,
    load_event_posts,
)


LANDSCAPE_CAPABILITY = {
    "name": "claim_response_landscape",
    "type": "system_projection",
    "boundary": "read_only_observed_evidence",
    "mutates_analysis_conclusions": False,
    "official_identity_policy": "allowlisted_authority_source_exact_platform_author_binding",
}


async def build_claim_response_landscape(
    event_id: str,
    platform: str | None = None,
    *,
    db: AsyncSession | None = None,
    mongo_db: Any | None = None,
    semantic_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an event-scoped observed landscape around the primary case claim."""

    event_id = _required_text(event_id, "event_id")
    platform = _optional_text(platform)
    if db is None:
        async with async_session_factory() as session:
            return await build_claim_response_landscape(
                event_id,
                platform=platform,
                db=session,
                mongo_db=mongo_db,
                semantic_projection=semantic_projection,
            )

    if mongo_db is None:
        mongo_db = get_mongo_db()
    case = await _load_case(db, event_id)
    if case is None:
        return _base_projection(
            event_id=event_id,
            platform=platform,
            status="not_found",
            blocking_reason="event_review_case_not_found",
            coverage={
                "case": {"status": "not_found", "reason": "event_review_case_not_found"},
                "primary_claim": {"status": "unavailable", "reason": "event_review_case_not_found"},
                "official_account_binding": {"status": "unavailable", "reason": "event_review_case_not_found"},
                "observed_paths": {"status": "unavailable", "reason": "event_review_case_not_found", "path_count": 0},
                "semantic": {"status": "unavailable", "reason": "event_review_case_not_found"},
            },
        )

    claim = await _load_primary_claim(db, case.case_id)
    if claim is None:
        return _blocked_projection(
            event_id=event_id,
            platform=platform,
            case=case,
            reason="primary_claim_unavailable",
        )

    case_claims = await _load_case_claims(db, case.case_id)
    source = await _load_authority_source(db, claim.authority_source_id)
    if source is None:
        return _blocked_projection(
            event_id=event_id,
            platform=platform,
            case=case,
            claim=claim,
            reason="authority_source_unavailable",
        )
    if source.review_status != "allowlisted":
        return _blocked_projection(
            event_id=event_id,
            platform=platform,
            case=case,
            claim=claim,
            source=source,
            reason="authority_source_not_allowlisted",
        )

    claim_sources = await _load_claim_authority_sources(db, case.case_id)
    allowlisted_source_ids = [
        row.source_id
        for row in claim_sources
        if row.review_status == "allowlisted"
    ]
    bindings = await _load_authority_accounts_for_sources(db, allowlisted_source_ids, platform=platform)
    posts = await load_event_posts(mongo_db, event_id=event_id, platform=platform)
    comments = await load_event_comments(mongo_db, event_id=event_id, platform=platform)
    observed = await _load_observed_paths(event_id=event_id, platform=platform)
    if semantic_projection is None:
        semantic_projection = await _load_latest_semantic_projection(event_id, db=db, mongo_db=mongo_db)

    evidence_index = _build_evidence_index(posts, comments)
    engagement_percentiles = _platform_engagement_percentiles(posts, comments)
    semantic_by_ref = _semantic_evidence_by_ref(semantic_projection)
    official_keys = {(row.platform, row.author_id) for row in bindings}
    official_publications = _official_publications(
        posts,
        bindings,
        engagement_percentiles=engagement_percentiles,
        semantic_by_ref=semantic_by_ref,
    )
    official_publication_refs = {
        ref
        for publication in official_publications
        for ref in publication.get("evidence_refs") or []
    }
    claim_id_by_source_id = _claim_id_by_source_id(case_claims)
    claim_id_by_official_ref = _claim_id_by_official_ref(official_publications, claim_id_by_source_id)
    observed_paths = _verified_paths_for_platform(
        observed,
        platform=platform,
        primary_claim_id=claim.claim_id,
        official_publication_refs=official_publication_refs,
    )
    if not observed_paths and official_publication_refs:
        observed_paths = _official_response_paths_from_graph(
            observed,
            evidence_index=evidence_index,
            official_keys=official_keys,
            official_publication_refs=official_publication_refs,
            claim_id_by_official_ref=claim_id_by_official_ref,
            platform=platform,
            primary_claim_id=claim.claim_id,
        )
    influential_responses = _influential_responses(
        observed,
        observed_paths,
        evidence_index=evidence_index,
        official_keys=official_keys,
        platform=platform,
        engagement_percentiles=engagement_percentiles,
        semantic_by_ref=semantic_by_ref,
    )
    coverage = _coverage(
        case=case,
        claim=claim,
        source=source,
        bindings=bindings,
        posts=posts,
        comments=comments,
        observed_paths=observed_paths,
        semantic_projection=semantic_projection,
        official_publications=official_publications,
        influential_responses=influential_responses,
    )

    return {
        **_base_projection(
            event_id=event_id,
            platform=platform,
            status="ready",
            coverage=coverage,
        ),
        "claim_anchor": _claim_anchor(case, claim),
        "official_publications": official_publications,
        "influential_responses": influential_responses,
        "timeline": _timeline(official_publications, influential_responses),
        "data_scope": analysis_scope_metadata(
            event_id=event_id,
            platform=platform,
            posts_count=len(posts),
            comments_count=len(comments),
        ),
    }


async def _load_case(db: AsyncSession, event_id: str) -> CaseRecord | None:
    result = await db.execute(select(CaseRecord).where(CaseRecord.event_id == event_id))
    return result.scalars().first()


async def _load_primary_claim(db: AsyncSession, case_id: str) -> CaseClaim | None:
    result = await db.execute(
        select(CaseClaim)
        .where(CaseClaim.case_id == case_id, CaseClaim.role == "primary")
        .order_by(CaseClaim.id.asc())
    )
    return result.scalars().first()


async def _load_case_claims(db: AsyncSession, case_id: str) -> list[CaseClaim]:
    result = await db.execute(
        select(CaseClaim)
        .where(CaseClaim.case_id == case_id)
        .order_by(CaseClaim.role.desc(), CaseClaim.id.asc())
    )
    return list(result.scalars().all())


async def _load_authority_source(db: AsyncSession, source_id: str) -> AuthoritySource | None:
    result = await db.execute(select(AuthoritySource).where(AuthoritySource.source_id == source_id))
    return result.scalars().first()


async def _load_claim_authority_sources(db: AsyncSession, case_id: str) -> list[AuthoritySource]:
    result = await db.execute(
        select(AuthoritySource)
        .join(CaseClaim, CaseClaim.authority_source_id == AuthoritySource.source_id)
        .where(CaseClaim.case_id == case_id)
        .order_by(CaseClaim.role.desc(), CaseClaim.id.asc())
    )
    seen: set[str] = set()
    sources: list[AuthoritySource] = []
    for source in result.scalars().all():
        if source.source_id in seen:
            continue
        seen.add(source.source_id)
        sources.append(source)
    return sources


async def _load_authority_accounts(
    db: AsyncSession,
    source_id: str,
    *,
    platform: str | None,
) -> list[AuthoritySourceAccount]:
    statement = select(AuthoritySourceAccount).where(AuthoritySourceAccount.source_id == source_id)
    if platform:
        statement = statement.where(AuthoritySourceAccount.platform == platform)
    result = await db.execute(statement.order_by(AuthoritySourceAccount.platform, AuthoritySourceAccount.author_id))
    return list(result.scalars().all())


async def _load_authority_accounts_for_sources(
    db: AsyncSession,
    source_ids: list[str],
    *,
    platform: str | None,
) -> list[AuthoritySourceAccount]:
    if not source_ids:
        return []
    statement = select(AuthoritySourceAccount).where(AuthoritySourceAccount.source_id.in_(source_ids))
    if platform:
        statement = statement.where(AuthoritySourceAccount.platform == platform)
    result = await db.execute(statement.order_by(
        AuthoritySourceAccount.source_id,
        AuthoritySourceAccount.platform,
        AuthoritySourceAccount.author_id,
    ))
    return list(result.scalars().all())


async def _load_observed_paths(*, event_id: str, platform: str | None) -> dict[str, Any]:
    try:
        return await propagation_observation_service.analyze_observed_propagation(
            event_id=event_id,
            platform=platform,
            node_limit=300,
        )
    except Exception as exc:
        return {
            "status": "blocked",
            "blocking_reason": f"observed_propagation_unavailable: {type(exc).__name__}",
            "graph": {"nodes": [], "edges": []},
            "path_analysis": {"key_paths": []},
        }


async def _load_latest_semantic_projection(
    event_id: str,
    *,
    db: AsyncSession,
    mongo_db: Any,
) -> dict[str, Any]:
    registry = AnalysisRegistry(mongo_db=mongo_db, store=SqlAlchemyAnalysisStore(db))
    try:
        candidates = await registry.list_semantic_artifact_candidates(event_id)
    except Exception:
        return {"status": "blocked", "blocking_reason": "semantic_artifact_lookup_failed", "artifact": None}
    if not candidates:
        return {"status": "not_found", "blocking_reason": "semantic_artifact_not_found", "artifact": None}

    first_failure: dict[str, Any] | None = None
    for run in candidates:
        run_id = str(run.get("run_id") or "")
        try:
            artifact = await registry.load_run_artifact(run_id, SEMANTIC_ARTIFACT_KEY)
        except KeyError:
            reason = "semantic_artifact_not_found"
        except ValueError:
            reason = "semantic_artifact_integrity_failed"
        except Exception:
            reason = "semantic_artifact_load_failed"
        else:
            if _is_ready_semantic_artifact(artifact):
                return {
                    "status": "ready",
                    "run_id": run_id,
                    "snapshot_id": _optional_text(run.get("snapshot_id")),
                    "artifact": artifact,
                }
            reason = _optional_text(artifact.get("blocking_reason")) if isinstance(artifact, dict) else None
            reason = reason or "semantic_artifact_not_ready"
        if first_failure is None:
            first_failure = {"status": "blocked", "blocking_reason": reason, "artifact": None}

    return first_failure or {"status": "not_found", "blocking_reason": "semantic_artifact_not_found", "artifact": None}


def _base_projection(
    *,
    event_id: str,
    platform: str | None,
    status: str,
    coverage: dict[str, Any],
    blocking_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "event_id": event_id,
        "platform": platform,
        "blocking_reason": blocking_reason,
        "claim_anchor": None,
        "official_publications": [],
        "influential_responses": [],
        "timeline": [],
        "coverage": coverage,
        "capability": dict(LANDSCAPE_CAPABILITY),
        "data_scope": analysis_scope_metadata(
            event_id=event_id,
            platform=platform,
            posts_count=0,
            comments_count=0,
        ),
    }


def _blocked_projection(
    *,
    event_id: str,
    platform: str | None,
    case: CaseRecord,
    reason: str,
    claim: CaseClaim | None = None,
    source: AuthoritySource | None = None,
) -> dict[str, Any]:
    return {
        **_base_projection(
            event_id=event_id,
            platform=platform,
            status="blocked",
            blocking_reason=reason,
            coverage={
                "case": {"status": "available", "case_id": case.case_id},
                "primary_claim": (
                    {"status": "available", "claim_id": claim.claim_id}
                    if claim is not None
                    else {"status": "unavailable", "reason": reason}
                ),
                "official_account_binding": {"status": "unavailable", "reason": reason},
                "observed_paths": {"status": "unavailable", "reason": reason, "path_count": 0},
                "semantic": {"status": "unavailable", "reason": reason},
            },
        ),
        "claim_anchor": _claim_anchor(case, claim) if claim is not None else None,
        "authority_source": _source_anchor(source) if source is not None else None,
    }


def _claim_anchor(case: CaseRecord, claim: CaseClaim) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "claim_id": claim.claim_id,
        "authority_source_id": claim.authority_source_id,
        "text": claim.exact_quote,
        "source_url": claim.source_url,
        "account": claim.account,
        "published_at": _iso(claim.published_at),
        "role": claim.role,
        "source_review_status": claim.source_review_snapshot,
        "source_tier": claim.source_tier_snapshot,
        "evidence_refs": [f"case:{case.case_id}:claim:{claim.claim_id}"],
    }


def _source_anchor(source: AuthoritySource | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "source_id": source.source_id,
        "name": source.name,
        "review_status": source.review_status,
        "tier": source.tier,
        "url": source.url,
    }


def _official_publications(
    posts: list[dict[str, Any]],
    bindings: list[AuthoritySourceAccount],
    *,
    engagement_percentiles: dict[str, float],
    semantic_by_ref: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    binding_by_key = {
        (binding.platform, binding.author_id): binding
        for binding in bindings
    }
    publications: list[dict[str, Any]] = []
    for post in posts:
        post_platform = _required_text(post.get("platform"), "platform")
        author_id = _optional_text(post.get("author_id"))
        binding = binding_by_key.get((post_platform, author_id or ""))
        if binding is None:
            continue
        ref = _post_ref(post)
        if ref is None:
            continue
        publications.append(
            {
                "post_id": str(post.get("post_id") or ""),
                "platform": post_platform,
                "author_id": author_id,
                "author_name": _optional_text(post.get("author_name")) or binding.display_name_snapshot,
                "content": _optional_text(post.get("content")) or "",
                "published_at": _optional_text(post.get("timestamp")),
                "source_url": _optional_text(post.get("url")),
                "authority_binding": {
                    "source_id": binding.source_id,
                    "platform": binding.platform,
                    "author_id": binding.author_id,
                },
                "verification_context": _verification_context(post, binding),
                "engagement_percentile": engagement_percentiles.get(ref, 0.0),
                "evidence_refs": [ref],
                "semantic": semantic_by_ref.get(ref),
            }
        )
    publications.sort(key=lambda row: (row.get("published_at") or "", row.get("post_id") or ""))
    return publications


def _influential_responses(
    observed: dict[str, Any],
    observed_paths: list[dict[str, Any]],
    *,
    evidence_index: dict[str, Any],
    official_keys: set[tuple[str, str]],
    platform: str | None,
    engagement_percentiles: dict[str, float],
    semantic_by_ref: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    adjacency = _adjacency(observed)
    account_platforms = evidence_index["account_platforms"]
    by_author = evidence_index["by_author"]
    rows: dict[tuple[str, str], dict[str, Any]] = {}

    for path in observed_paths:
        path_refs = _path_canonical_refs(path)
        path_id = _optional_text(path.get("path_id") or path.get("id"))
        path_score = _float(path.get("score"), default=1.0)
        for node in [str(value or "").strip() for value in path.get("nodes") or []]:
            if not node:
                continue
            node_refs = [
                ref for ref in path_refs
                if evidence_index["author_by_ref"].get(ref) == node
            ]
            if not node_refs:
                continue
            node_platforms = {
                evidence_index["platform_by_ref"].get(ref)
                for ref in node_refs
                if evidence_index["platform_by_ref"].get(ref)
            }
            scoped_platforms = [platform] if platform else sorted(node_platforms)
            for resolved_platform in scoped_platforms:
                if resolved_platform not in node_platforms or (resolved_platform, node) in official_keys:
                    continue
                platform_refs = [
                    ref for ref in node_refs
                    if evidence_index["platform_by_ref"].get(ref) == resolved_platform
                ]
                if not platform_refs:
                    continue
                key = (resolved_platform, node)
                row = rows.setdefault(
                    key,
                    {
                        "platform": resolved_platform,
                        "author_id": node,
                        "author_name": _author_name(node, by_author),
                        "rank_scope": "platform",
                        "downstream_reach": _downstream_reach(
                            node,
                            adjacency,
                            platform=resolved_platform,
                            account_platforms=account_platforms,
                        ),
                        "path_contribution": 0.0,
                        "path_count": 0,
                        "engagement_percentile": 0.0,
                        "first_seen_at": _first_seen(node, by_author, platform=resolved_platform),
                        "evidence_refs": [],
                        "path_refs": [],
                    },
                )
                row["path_contribution"] += path_score
                row["path_count"] += 1
                row["evidence_refs"] = _dedupe([*row["evidence_refs"], *platform_refs])
                if path_id:
                    path_ref = {"path_id": path_id, "evidence_refs": path_refs}
                    if isinstance(path.get("nodes"), list):
                        path_ref["nodes"] = list(path["nodes"])
                    if path.get("score") is not None:
                        path_ref["score"] = path["score"]
                    row["path_refs"].append(path_ref)
                row["engagement_percentile"] = max(
                    row["engagement_percentile"],
                    max((engagement_percentiles.get(ref, 0.0) for ref in platform_refs), default=0.0),
                )

    ranked_rows: list[dict[str, Any]] = []
    by_platform: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows.values():
        semantic = _aggregate_semantic_evidence(row["evidence_refs"], semantic_by_ref)
        if semantic is not None:
            row["semantic"] = semantic
            row["stance"] = semantic.get("dominant_stance")
        by_platform[str(row["platform"])].append(row)
    for scoped_platform in sorted(by_platform):
        ranked = sorted(
            by_platform[scoped_platform],
            key=lambda row: (
                -int(row["downstream_reach"]),
                -float(row["path_contribution"]),
                str(row["author_id"]),
            ),
        )
        for index, row in enumerate(ranked[:10], start=1):
            row["rank"] = index
            row["path_contribution"] = round(float(row["path_contribution"]), 4)
            row["engagement_percentile"] = round(float(row["engagement_percentile"]), 4)
            ranked_rows.append(row)
    return ranked_rows


def _coverage(
    *,
    case: CaseRecord,
    claim: CaseClaim,
    source: AuthoritySource,
    bindings: list[AuthoritySourceAccount],
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    observed_paths: list[dict[str, Any]],
    semantic_projection: dict[str, Any],
    official_publications: list[dict[str, Any]],
    influential_responses: list[dict[str, Any]],
) -> dict[str, Any]:
    path_count = len(observed_paths)
    return {
        "case": {"status": "available", "case_id": case.case_id},
        "primary_claim": {"status": "available", "claim_id": claim.claim_id},
        "authority_source": {
            "status": "available",
            "source_id": source.source_id,
            "review_status": source.review_status,
        },
        "official_account_binding": (
            {"status": "available", "binding_count": len(bindings)}
            if bindings
            else {"status": "unavailable", "reason": "authority_source_account_binding_unavailable", "binding_count": 0}
        ),
        "observed_paths": (
            {"status": "available", "path_count": path_count}
            if path_count
            else {"status": "unavailable", "reason": "observed_path_evidence_unavailable", "path_count": 0}
        ),
        "semantic": _semantic_coverage(semantic_projection),
        "evidence_refs": {
            "status": "available" if _returned_refs_available(official_publications, influential_responses) else "unavailable",
            "official_publication_count": len(official_publications),
            "response_count": len(influential_responses),
        },
        "data_scope": analysis_scope_metadata(
            event_id=case.event_id,
            platform=None,
            posts_count=len(posts),
            comments_count=len(comments),
        ),
    }


def _semantic_coverage(projection: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(projection, dict):
        return {"status": "unavailable", "reason": "semantic_projection_unavailable"}
    status = str(projection.get("status") or "").strip().lower()
    if status == "ready":
        artifact = projection.get("artifact") if isinstance(projection.get("artifact"), dict) else {}
        overlays = (
            ((artifact.get("cross_analysis") or {}).get("propagation_path_overlays") or [])
            if isinstance(artifact, dict)
            else []
        )
        return {"status": "available", "path_overlay_count": len(overlays)}
    if status == "blocked":
        return {
            "status": "blocked",
            "reason": _optional_text(projection.get("blocking_reason")) or "semantic_projection_blocked",
        }
    return {
        "status": "unavailable",
        "reason": _optional_text(projection.get("blocking_reason")) or "semantic_projection_unavailable",
    }


def _semantic_evidence_by_ref(projection: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index only per-record semantic evidence from a ready real artifact."""

    if not isinstance(projection, dict) or projection.get("status") != "ready":
        return {}
    artifact = projection.get("artifact")
    if not _is_ready_semantic_artifact(artifact):
        return {}
    layers = artifact.get("layers") if isinstance(artifact.get("layers"), dict) else {}
    indexed: dict[str, dict[str, Any]] = {}
    for layer, ref_kind in (("posts", "post"), ("comments", "comment")):
        for item in layers.get(layer) or []:
            if not isinstance(item, dict):
                continue
            platform = _optional_text(item.get("platform"))
            item_id = _optional_text(item.get("id"))
            if not platform or not item_id:
                continue
            evidence: dict[str, Any] = {}
            stance = _semantic_stance_label(item.get("stance"))
            sentiment = _semantic_label(item.get("sentiment"))
            if stance:
                evidence["stance"] = stance
            if sentiment:
                evidence["sentiment"] = sentiment
            if evidence:
                indexed[f"{platform}:{ref_kind}:{item_id}"] = evidence
    return indexed


def _aggregate_semantic_evidence(
    evidence_refs: list[str], semantic_by_ref: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    values = [semantic_by_ref[ref] for ref in evidence_refs if ref in semantic_by_ref]
    if not values:
        return None
    stance_distribution = Counter(value["stance"] for value in values if value.get("stance"))
    sentiment_distribution = Counter(value["sentiment"] for value in values if value.get("sentiment"))
    result: dict[str, Any] = {
        "evidence_item_count": len(values),
        "stance_distribution": dict(sorted(stance_distribution.items())),
        "sentiment_distribution": dict(sorted(sentiment_distribution.items())),
    }
    if stance_distribution:
        result["dominant_stance"] = min(
            stance_distribution,
            key=lambda label: (-stance_distribution[label], label),
        )
    return result


def _semantic_label(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict):
        return None
    return _optional_text(value.get("label"))


def _semantic_stance_label(value: Any) -> str | None:
    """Map the fixed NLI runtime labels to analyst-facing claim stance."""

    label = _semantic_label(value)
    labels = {
        "entailment": "support",
        "contradiction": "oppose",
        "neutral": "neutral",
    }
    return labels.get(str(label or "").lower())


def _verified_paths_for_platform(
    observed: dict[str, Any],
    *,
    platform: str | None,
    primary_claim_id: str | None = None,
    official_publication_refs: set[str] | None = None,
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for path in _candidate_paths(observed):
        refs = _path_canonical_refs(path)
        if not refs:
            continue
        claim_id = _optional_text(path.get("claim_id"))
        if primary_claim_id is not None and claim_id and claim_id != primary_claim_id:
            continue
        if official_publication_refs is not None and not official_publication_refs.intersection(refs):
            continue
        if platform:
            ref_platforms = {_reference_platform(ref) for ref in refs}
            if ref_platforms != {platform}:
                continue
        key = (_optional_text(path.get("path_id") or path.get("id")) or "", tuple(refs))
        if key in seen:
            continue
        seen.add(key)
        enriched = dict(path)
        enriched["evidence_refs"] = refs
        paths.append(enriched)
    return paths


def _official_response_paths_from_graph(
    observed: dict[str, Any],
    *,
    evidence_index: dict[str, Any],
    official_keys: set[tuple[str, str]],
    official_publication_refs: set[str],
    claim_id_by_official_ref: dict[str, str],
    platform: str | None,
    primary_claim_id: str,
) -> list[dict[str, Any]]:
    """Derive observed response chains from graph edges when key_paths are absent.

    The derived chains are deliberately conservative: every node in a returned
    chain must resolve to a real post/comment ref in the event evidence index.
    """

    adjacency = _adjacency(observed)
    if not adjacency:
        return []

    author_by_ref = evidence_index["author_by_ref"]
    official_seed_refs = [
        ref for ref in sorted(official_publication_refs)
        if (not platform or _reference_platform(ref) == platform) and author_by_ref.get(ref)
    ]
    paths: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    max_depth = 3

    for official_ref in official_seed_refs:
        official_author = author_by_ref.get(official_ref)
        if not official_author:
            continue
        path_platform = _reference_platform(official_ref)
        queue: deque[list[str]] = deque([[official_author]])
        while queue and len(paths) < 50:
            node_path = queue.popleft()
            if len(node_path) > max_depth:
                continue
            current = node_path[-1]
            for neighbor in sorted(adjacency.get(current, set())):
                if neighbor in node_path:
                    continue
                next_path = [*node_path, neighbor]
                if len(next_path) <= max_depth:
                    queue.append(next_path)
                if (path_platform, neighbor) in official_keys:
                    continue
                evidence_refs = _path_refs_from_node_evidence(
                    next_path,
                    official_ref=official_ref,
                    path_platform=path_platform,
                    evidence_index=evidence_index,
                )
                if not evidence_refs:
                    continue
                key = tuple(next_path)
                if key in seen:
                    continue
                seen.add(key)
                claim_id = claim_id_by_official_ref.get(official_ref) or primary_claim_id
                path_id = f"observed_graph:{claim_id}:{path_platform}:{len(paths)}"
                paths.append(
                    {
                        "path_id": path_id,
                        "claim_id": claim_id,
                        "nodes": next_path,
                        "score": max(1.0, 4.0 - len(next_path)),
                        "confidence": "medium",
                        "source": "observed_graph_official_bfs",
                        "evidence_refs": evidence_refs,
                    }
                )
    return paths


def _path_refs_from_node_evidence(
    node_path: list[str],
    *,
    official_ref: str,
    path_platform: str,
    evidence_index: dict[str, Any],
) -> list[str]:
    refs = [official_ref]
    for node in node_path[1:]:
        node_refs = _refs_for_author(
            node,
            evidence_index=evidence_index,
            platform=path_platform,
        )
        if not node_refs:
            return []
        refs.append(node_refs[0])
    return _dedupe(refs)


def _refs_for_author(
    author_id: str,
    *,
    evidence_index: dict[str, Any],
    platform: str | None,
) -> list[str]:
    rows = [
        row for row in evidence_index["by_author"].get(author_id, [])
        if not platform or _optional_text(row.get("platform")) == platform
    ]
    refs: list[tuple[str, str]] = []
    for row in rows:
        ref = _post_ref(row) if row.get("kind") == "post" else _comment_ref(row)
        if ref:
            refs.append((_optional_text(row.get("timestamp")) or "", ref))
    return [ref for _timestamp, ref in sorted(refs)]


def _claim_id_by_source_id(claims: list[CaseClaim]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for claim in claims:
        source_id = _optional_text(claim.authority_source_id)
        claim_id = _optional_text(claim.claim_id)
        if source_id and claim_id and source_id not in mapping:
            mapping[source_id] = claim_id
    return mapping


def _claim_id_by_official_ref(
    official_publications: list[dict[str, Any]],
    claim_id_by_source_id: dict[str, str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for publication in official_publications:
        binding = publication.get("authority_binding") if isinstance(publication.get("authority_binding"), dict) else {}
        claim_id = claim_id_by_source_id.get(str(binding.get("source_id") or ""))
        if not claim_id:
            continue
        for ref in publication.get("evidence_refs") or []:
            if isinstance(ref, str):
                mapping[ref] = claim_id
    return mapping


def _candidate_paths(observed: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    path_analysis = observed.get("path_analysis") if isinstance(observed.get("path_analysis"), dict) else {}
    candidates.extend(path_analysis.get("key_paths") or [])
    candidates.extend(observed.get("key_paths") or [])
    for chain in observed.get("evidence_chains") or []:
        if not isinstance(chain, dict):
            continue
        for path in chain.get("key_paths") or []:
            if isinstance(path, dict):
                row = dict(path)
                row.setdefault("claim_id", chain.get("claim_id"))
                candidates.append(row)
    return [dict(path) for path in candidates if isinstance(path, dict)]


def _build_evidence_index(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> dict[str, Any]:
    by_ref: dict[str, dict[str, Any]] = {}
    author_by_ref: dict[str, str] = {}
    platform_by_ref: dict[str, str] = {}
    by_author: dict[str, list[dict[str, Any]]] = defaultdict(list)
    account_platforms: dict[str, set[str]] = defaultdict(set)
    for post in posts:
        ref = _post_ref(post)
        if ref is None:
            continue
        author_id = _optional_text(post.get("author_id"))
        row = {"kind": "post", **post}
        by_ref[ref] = row
        platform_by_ref[ref] = _reference_platform(ref)
        if author_id:
            author_by_ref[ref] = author_id
            by_author[author_id].append(row)
            account_platforms[author_id].add(_reference_platform(ref))
    for comment in comments:
        ref = _comment_ref(comment)
        if ref is None:
            continue
        author_id = _optional_text(comment.get("author_id"))
        row = {"kind": "comment", **comment}
        by_ref[ref] = row
        platform_by_ref[ref] = _reference_platform(ref)
        if author_id:
            author_by_ref[ref] = author_id
            by_author[author_id].append(row)
            account_platforms[author_id].add(_reference_platform(ref))
    return {
        "by_ref": by_ref,
        "author_by_ref": author_by_ref,
        "platform_by_ref": platform_by_ref,
        "by_author": by_author,
        "account_platforms": account_platforms,
    }


def _adjacency(observed: dict[str, Any]) -> dict[str, set[str]]:
    graph = observed.get("graph") if isinstance(observed.get("graph"), dict) else {}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source = _optional_text(edge.get("source"))
        target = _optional_text(edge.get("target"))
        if source and target and source != target:
            adjacency[source].add(target)
    return adjacency


def _downstream_reach(
    author_id: str,
    adjacency: dict[str, set[str]],
    *,
    platform: str,
    account_platforms: dict[str, set[str]],
) -> int:
    seen: set[str] = set()
    queue: deque[str] = deque(adjacency.get(author_id, set()))
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(adjacency.get(node, set()) - seen)
    return sum(1 for node in seen if platform in account_platforms.get(node, {platform}))


def _platform_engagement_percentiles(posts: list[dict[str, Any]], comments: list[dict[str, Any]]) -> dict[str, float]:
    values_by_platform: dict[str, list[float]] = defaultdict(list)
    values_by_ref: dict[str, float] = {}
    for row, ref_builder in [
        *[(post, _post_ref) for post in posts],
        *[(comment, _comment_ref) for comment in comments],
    ]:
        ref = ref_builder(row)
        if ref is None:
            continue
        value = _engagement(row)
        values_by_ref[ref] = value
        values_by_platform[_reference_platform(ref)].append(value)
    percentiles: dict[str, float] = {}
    for ref, value in values_by_ref.items():
        platform_values = sorted(values_by_platform[_reference_platform(ref)])
        if not platform_values:
            percentiles[ref] = 0.0
            continue
        less_or_equal = sum(1 for item in platform_values if item <= value)
        percentiles[ref] = round(less_or_equal / len(platform_values), 4)
    return percentiles


def _engagement(row: dict[str, Any]) -> float:
    total = 0.0
    for key in ("likes", "like_count", "reposts", "repost_count", "shares", "share_count", "comments_count", "comment_count"):
        total += _float(row.get(key), default=0.0)
    return total


def _timeline(
    official_publications: list[dict[str, Any]],
    influential_responses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for publication in official_publications:
        rows.append(
            {
                "type": "official_publication",
                "at": publication.get("published_at"),
                "platform": publication.get("platform"),
                "author_id": publication.get("author_id"),
                "post_id": publication.get("post_id"),
                "evidence_refs": list(publication.get("evidence_refs") or []),
            }
        )
    for response in influential_responses:
        rows.append(
            {
                "type": "influential_response",
                "at": response.get("first_seen_at"),
                "platform": response.get("platform"),
                "author_id": response.get("author_id"),
                "rank": response.get("rank"),
                "evidence_refs": list(response.get("evidence_refs") or []),
                "path_refs": list(response.get("path_refs") or []),
            }
        )
    rows.sort(key=lambda row: (row.get("at") or "", row.get("type") or "", row.get("author_id") or ""))
    return rows


def _returned_refs_available(
    official_publications: list[dict[str, Any]],
    influential_responses: list[dict[str, Any]],
) -> bool:
    rows = [*official_publications, *influential_responses]
    if not rows:
        return False
    return all(row.get("evidence_refs") for row in rows)


def _path_canonical_refs(path: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    refs.extend(_canonical_ref(ref) for ref in path.get("evidence_refs") or [])
    metadata = path.get("metadata") if isinstance(path.get("metadata"), dict) else {}
    refs.extend(_canonical_ref(ref) for ref in metadata.get("evidence_refs") or [])
    for edge in path.get("edges") or []:
        if isinstance(edge, dict):
            refs.extend(_canonical_ref(ref) for ref in edge.get("evidence_refs") or [])
    return _dedupe(ref for ref in refs if ref)


def _canonical_ref(reference: Any) -> str | None:
    if isinstance(reference, str):
        text = reference.strip()
        parts = text.split(":", 2)
        if len(parts) == 3 and parts[0] and parts[1] in {"post", "comment"} and parts[2]:
            return text
        return None
    if not isinstance(reference, dict):
        return None
    platform = _optional_text(reference.get("platform"))
    if not platform:
        return None
    post_id = _optional_text(reference.get("post_id"))
    if post_id:
        return f"{platform}:post:{post_id}"
    comment_id = _optional_text(reference.get("comment_id"))
    if comment_id:
        return f"{platform}:comment:{comment_id}"
    return None


def _post_ref(post: dict[str, Any]) -> str | None:
    platform = _optional_text(post.get("platform"))
    post_id = _optional_text(post.get("post_id"))
    if not platform or not post_id:
        return None
    return f"{platform}:post:{post_id}"


def _comment_ref(comment: dict[str, Any]) -> str | None:
    platform = _optional_text(comment.get("platform"))
    comment_id = _optional_text(comment.get("comment_id"))
    if not platform or not comment_id:
        return None
    return f"{platform}:comment:{comment_id}"


def _reference_platform(ref: str) -> str:
    return ref.split(":", 1)[0]


def _verification_context(post: dict[str, Any], binding: AuthoritySourceAccount) -> dict[str, Any]:
    context: dict[str, Any] = {}
    profile = post.get("author_profile") if isinstance(post.get("author_profile"), dict) else {}
    snapshot = profile.get("verification_snapshot") if isinstance(profile.get("verification_snapshot"), dict) else None
    if snapshot is not None:
        context["platform_verification"] = snapshot
    stored = _json_loads(binding.verification_snapshot, {})
    if stored:
        context["authority_binding_review_snapshot"] = stored
    context["policy"] = "context_only_not_authority"
    return context


def _author_name(author_id: str, by_author: dict[str, list[dict[str, Any]]]) -> str:
    for row in by_author.get(author_id, []):
        name = _optional_text(row.get("author_name"))
        if name:
            return name
    return author_id


def _first_seen(author_id: str, by_author: dict[str, list[dict[str, Any]]], *, platform: str) -> str | None:
    timestamps = [
        _optional_text(row.get("timestamp"))
        for row in by_author.get(author_id, [])
        if _optional_text(row.get("platform")) == platform
    ]
    values = [value for value in timestamps if value]
    return min(values) if values else None


def _is_ready_semantic_artifact(artifact: Any) -> bool:
    return (
        isinstance(artifact, dict)
        and artifact.get("technology") == "semantic_enrichment"
        and artifact.get("status") == "ok"
        and artifact.get("runtime_status") == "ready"
        and not artifact.get("fallback")
    )


def _dedupe(values) -> list:
    return list(dict.fromkeys(value for value in values if value))


def _float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(field)
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


__all__ = ["LANDSCAPE_CAPABILITY", "build_claim_response_landscape"]
