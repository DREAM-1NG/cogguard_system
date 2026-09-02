from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.analysis import AnalysisModelActivationApproval, AnalysisModelVersion
from app.models.user import User
from app.services.analysis_governance_service import (
    activate_model_version,
    approve_model_candidate,
)


@pytest.mark.asyncio
async def test_production_activation_requires_persisted_distinct_approvals(
    db_session: AsyncSession,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "BACKEND_ENV", "production")
    monkeypatch.setattr(settings, "ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE", "auto")

    artifact_root = tmp_path / "artifacts"
    artifact_dir = artifact_root / "coordination_discover" / "candidate-v1"
    artifact_dir.mkdir(parents=True)
    checkpoint = artifact_dir / "checkpoint.pt"
    checkpoint.write_bytes(b"coordination-discover-checkpoint")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "technology": "coordination_discover",
                "checkpoint_path": "checkpoint.pt",
                "metrics": {
                    "strict_leiden": True,
                    "stability_passed": True,
                    "evidence_coverage_passed": True,
                },
            }
        ),
        encoding="utf-8",
    )

    first_admin = User(
        username="governance_admin_one",
        email="governance_admin_one@example.com",
        hashed_password="test-hash-one",
        role="admin",
        is_active=True,
    )
    second_admin = User(
        username="governance_admin_two",
        email="governance_admin_two@example.com",
        hashed_password="test-hash-two",
        role="admin",
        is_active=True,
    )
    db_session.add_all([first_admin, second_admin])
    await db_session.flush()

    candidate = AnalysisModelVersion(
        technology="coordination_discover",
        model="temporal_magnn",
        version="candidate-v1",
        artifact_hash=checkpoint_hash,
        artifact_uri=str(artifact_dir),
        config_json="{}",
        metrics_json="{}",
        status="candidate",
        created_by=first_admin.id,
    )
    db_session.add(candidate)
    await db_session.flush()

    first_approval = await approve_model_candidate(
        model_version_id=candidate.id,
        approved_by=first_admin.id,
        approval_notes="First administrator reviewed the artifact.",
        db=db_session,
        artifact_root=artifact_root,
    )
    assert first_approval["active_approval_count"] == 1
    assert first_approval["ready_for_activation"] is False

    with pytest.raises(ValueError, match="two distinct active administrator"):
        await activate_model_version(
            model_version_id=candidate.id,
            operator_id=first_admin.id,
            reason="Attempt activation with one persisted approval.",
            db=db_session,
            artifact_root=artifact_root,
        )

    second_approval = await approve_model_candidate(
        model_version_id=candidate.id,
        approved_by=second_admin.id,
        approval_notes="Second administrator independently reviewed the artifact.",
        db=db_session,
        artifact_root=artifact_root,
    )
    assert second_approval["active_approval_count"] == 2
    assert second_approval["ready_for_activation"] is True

    activation = await activate_model_version(
        model_version_id=candidate.id,
        operator_id=first_admin.id,
        reason="Activate after the required approvals were persisted.",
        db=db_session,
        artifact_root=artifact_root,
    )
    await db_session.commit()

    approvals = await db_session.execute(
        select(AnalysisModelActivationApproval)
        .where(AnalysisModelActivationApproval.model_version_id == candidate.id)
        .order_by(AnalysisModelActivationApproval.approver_id)
    )
    approval_rows = list(approvals.scalars().all())

    assert len(approval_rows) == 2
    assert {row.approver_id for row in approval_rows} == {first_admin.id, second_admin.id}
    assert activation["decision"]["approved_by"] == [first_admin.id, second_admin.id]
