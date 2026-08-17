from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.config import settings
from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.analysis.executor import AnalysisEnginePorts, AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import AnalysisRegistry
from app.services.analysis_governance_service import evaluate_quality_gates
from app.core.analysis.coordination_runtime import (
    CrossPlatformResolver,
    CoordinationDetectionRuntime,
    CoordinationGroupDiscovery,
)


def _dt(day: int, hour: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, 0, second, tzinfo=timezone.utc)


def _snapshot() -> Any:
    return build_event_snapshot(
        event_id="coordination-event",
        posts=[
            {
                "event_id": "coordination-event",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "author-1",
                "author_name": "Shared Alias",
                "profile_url": "https://social.example.com/user/alice?utm_source=share#bio",
                "avatar_hash": "avatar-hash-a",
                "timestamp": _dt(12, 0),
                "content": "shared claim template alpha beta gamma delta epsilon zeta eta theta",
                "url": "https://example.com/story?a=1&utm_source=feed#section",
                "hashtags": ["#TrumpVisit", "#SharedNarrative"],
                "entities": ["White House"],
                "raw_data": {
                    "shared_url": "https://example.com/story?a=1&utm_medium=social",
                    "profile": {
                        "url": "https://social.example.com/user/alice?utm_source=share#bio",
                        "avatar": "avatar-hash-a",
                    },
                },
            },
            {
                "event_id": "coordination-event",
                "platform": "xhs",
                "post_id": "p2",
                "author_id": "author-1",
                "author_name": "Shared Alias",
                "profile_url": "https://social.example.com/user/alice?utm_source=share#bio",
                "avatar_hash": "avatar-hash-a",
                "timestamp": _dt(12, 0, 20),
                "content": "shared claim template alpha beta gamma delta epsilon zeta eta theta second",
                "url": "https://example.com/story?a=1&utm_campaign=ad#fragment",
                "hashtags": ["#TrumpVisit", "#SharedNarrative"],
                "entities": ["White House"],
                "raw_data": {
                    "shared_url": "https://example.com/story?a=1&utm_campaign=ad#fragment",
                    "profile": {
                        "url": "https://social.example.com/user/alice?utm_source=share#bio",
                        "avatar": "avatar-hash-a",
                    },
                },
            },
            {
                "event_id": "coordination-event",
                "platform": "douyin",
                "post_id": "p3",
                "author_id": "author-2",
                "author_name": "Shared Alias",
                "timestamp": _dt(12, 0, 40),
                "content": "shared claim template alpha beta gamma delta epsilon zeta eta theta third",
                "url": "https://example.com/story?a=1&utm_term=ignored",
                "hashtags": ["#TrumpVisit"],
                "entities": ["White House"],
            },
        ],
        comments=[],
        core_window=TimeWindow(start=_dt(11), end=_dt(13)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def _write_coordination_detection_artifact(root: Path) -> dict[str, Any]:
    from app.core.analysis.coordination_runtime import _load_detection_runtime_modules

    detection = _load_detection_runtime_modules().contracts
    schema = detection.DetectionFeatureSchema(
        version="coordination-detection/v1",
        names=(
            "cluster_size",
            "tsgs_density",
            "mhcr_coherence",
            "temporal_sync_delta_seconds",
            "unsupervised_coordination_ranking",
            "evidence_coverage",
            "relation_diversity",
        ),
    )
    artifact = detection.DetectionModelArtifact(
        feature_schema=schema,
        scaler_mean=(1.0, 0.5, 0.5, 10.0, 0.5, 0.5, 0.5),
        scaler_scale=(1.0, 1.0, 1.0, 10.0, 1.0, 1.0, 1.0),
        coefficients=(0.6, 1.1, 1.0, -0.8, 1.0, 0.7, 0.5),
        intercept=-0.25,
        calibrator_slope=1.0,
        calibrator_intercept=0.0,
        lower_decision_threshold=0.5,
        upper_decision_threshold=0.5,
        validation_ood_min=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        validation_ood_max=(10.0, 1.0, 1.0, 30.0, 1.0, 1.0, 1.0),
        optimizer_config={"algorithm": "unit_test"},
        calibrator_config={"algorithm": "unit_test"},
        threshold_objective="forced_binary_probability_at_0_5",
        train_fit_case_ids_fingerprint="train-fingerprint",
        validation_calibration_case_ids_fingerprint="validation-fingerprint",
        validation_threshold_case_ids_fingerprint="validation-fingerprint",
        validation_ood_case_ids_fingerprint="validation-fingerprint",
    )

    artifact_dir = root / "coordination_detection" / "v1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = artifact_dir / "checkpoint.json"
    artifact.to_json(checkpoint_path)
    checkpoint_hash = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    manifest = {
        "technology": "coordination_detection",
        "checkpoint_path": "checkpoint.json",
        "metrics": {
            "macro_f1": 0.81,
            "auprc": 0.83,
            "roc_auc": 0.86,
            "ece": 0.04,
            "p95_latency_seconds": 1.2,
            "beats_system_baseline": True,
            "beats_strongest_fair_baseline": True,
        },
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return {
        "artifact_dir": artifact_dir,
        "artifact": artifact,
        "active_model": {
            "technology": "coordination_detection",
            "model_version_id": 11,
            "version": "v1",
            "model": "coordination-detection-logistic",
            "artifact_uri": str(artifact_dir),
            "artifact_hash": checkpoint_hash,
            "checkpoint_path": str(checkpoint_path),
            "status": "active",
            "provenance": {"artifact": {"checkpoint_path": "checkpoint.json"}},
        },
    }


def _write_socgfm_detection_artifact(root: Path) -> dict[str, Any]:
    from app.core.analysis.coordination_runtime import _load_detection_runtime_modules

    detection = _load_detection_runtime_modules().socgfm
    artifact = detection.SocGFMCrossAttentionArtifact(
        cluster_coefficients=(0.02, 1.8, 1.0, 0.5, 0.4, 0.7),
        cluster_intercept=-1.0,
        calibrator_slope=1.0,
        calibrator_intercept=0.0,
        decision_threshold=0.5,
        default_account_probability=0.62,
        account_probabilities={
            "cross_platform_account:5a0611ec624c": 0.91,
            "douyin:author-2": 0.33,
        },
        threshold_source="validation_macro_f1_official_iohunter",
        checkpoint_reference="iohunter_full_test_20260816-123616",
        provenance={
            "source": "unit_test_socgfm_fixture",
            "shadow_classifier": "recorded_not_primary",
        },
        source_run_hashes={
            "unit_test_predictions.csv": "sha256:" + ("b" * 64),
        },
    )
    artifact_dir = root / "coordination_detection" / "socgfm-v1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = artifact_dir / "checkpoint.json"
    artifact.to_json(checkpoint_path)
    checkpoint_hash = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    manifest = {
        "technology": "coordination_detection",
        "backend": "socgfm_cross_attention",
        "model": "socgfm_cross_attention",
        "checkpoint_path": "checkpoint.json",
        "inference_mode": "precomputed_member_probability_cluster_aggregation",
        "claim_scope": "account_level_io_membership_to_cluster_proxy",
        "online_neural_forward": False,
        "unsupported_claims": ["group_level_harmful_coordination_f1"],
        "metrics": {
            "system_primary_model": "socgfm_cross_attention",
            "macro_f1": 0.86,
            "auprc": 0.88,
            "roc_auc": 0.9,
            "ece": 0.1,
            "p95_latency_seconds": 3.0,
            "official_validation_protocol": True,
            "shadow_classifier_recorded": True,
            "no_feature_leakage": True,
            "claimable_superiority_over_shadow_classifier": False,
        },
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return {
        "artifact_dir": artifact_dir,
        "artifact": artifact,
        "active_model": {
            "technology": "coordination_detection",
            "model_version_id": 12,
            "version": "socgfm-v1",
            "model": "socgfm_cross_attention",
            "artifact_uri": str(artifact_dir),
            "artifact_hash": checkpoint_hash,
            "checkpoint_path": str(checkpoint_path),
            "status": "active",
            "provenance": {"artifact": {"checkpoint_path": "checkpoint.json"}},
        },
    }


def test_cross_platform_resolver_is_conservative_about_identity_merges():
    resolver = CrossPlatformResolver()
    view = resolver.resolve(_snapshot())
    resolved_posts = {row["post_id"]: row for row in view.snapshot.posts}

    assert resolved_posts["p1"]["author_id"].startswith("cross_platform_account:")
    assert resolved_posts["p1"]["author_id"] == resolved_posts["p2"]["author_id"]
    assert resolved_posts["p3"]["author_id"] == "douyin:author-2"
    assert resolved_posts["p1"]["normalized_urls"] == ["https://example.com/story?a=1"]
    assert resolved_posts["p1"]["normalized_domains"] == ["example.com"]
    assert resolved_posts["p1"]["resolved_account_id"] == resolved_posts["p2"]["resolved_account_id"]
    assert resolved_posts["p1"]["resolved_account_id"] != resolved_posts["p3"]["resolved_account_id"]
    assert view.resolution_report["blocked_same_name_merge_count"] == 2
    assert view.resolution_report["cross_platform_merge_count"] == 1


def test_coordination_group_discovery_reuses_the_existing_discovery_contract():
    resolver = CrossPlatformResolver()
    discovery = CoordinationGroupDiscovery()
    view = resolver.resolve(_snapshot())

    result = discovery.analyze(
        view,
        options={
            "time_window": 60,
            "min_participation": 1,
            "edge_weight": 0.5,
            "window_hours": [1, 6, 24],
            "overlap_ratio": 0.5,
        },
    )

    assert result.batch.schema_version == "cogguard.discovered-cluster-batch/v1"
    assert result.batch.candidate_clusters
    assert "platform_missing" not in result.batch.quality_flags
    assert result.network["edge_count"] >= 1
    assert result.batch.provenance.source_event == "coordination-event"
    assert result.batch.candidate_clusters[0].coordination_metrics.evidence_coverage >= 0.0


def test_coordination_detection_runtime_fails_closed_without_an_active_artifact():
    resolver = CrossPlatformResolver()
    discovery = CoordinationGroupDiscovery()
    detection = CoordinationDetectionRuntime()
    view = resolver.resolve(_snapshot())
    batch = discovery.discover(
        view,
        options={
            "time_window": 60,
            "min_participation": 1,
            "edge_weight": 0.5,
        },
    )

    result = detection.predict(batch, feature_rows={}, active_model=None)

    assert result["technology"] == "coordination_detection"
    assert result["status"] == "model_unavailable"
    assert result["fallback"] is False


def test_coordination_detection_runtime_rejects_legacy_learned_artifact_as_primary():
    resolver = CrossPlatformResolver()
    discovery = CoordinationGroupDiscovery()
    detection = CoordinationDetectionRuntime()
    view = resolver.resolve(_snapshot())
    batch = discovery.discover(
        view,
        options={
            "time_window": 60,
            "min_participation": 1,
            "edge_weight": 0.5,
        },
    )

    with tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT / "output")) as tmpdir:
        previous_root = settings.MODEL_ARTIFACT_ROOT
        settings.MODEL_ARTIFACT_ROOT = tmpdir
        try:
            payload = _write_coordination_detection_artifact(Path(tmpdir))
            result = detection.predict(batch, feature_rows={}, active_model=payload["active_model"])
        finally:
            settings.MODEL_ARTIFACT_ROOT = previous_root

    assert result["technology"] == "coordination_detection"
    assert result["status"] == "model_unavailable"
    assert result["fallback"] is False
    assert result["model_role"] == "primary_socgfm_cross_attention"
    assert result["blocking_reason"] == "coordination_detection_active_model_not_socgfm:unsupported_non_socgfm"


def test_coordination_detection_runtime_dispatches_socgfm_cross_attention_artifact():
    resolver = CrossPlatformResolver()
    discovery = CoordinationGroupDiscovery()
    detection = CoordinationDetectionRuntime()
    view = resolver.resolve(_snapshot())
    batch = discovery.discover(
        view,
        options={
            "time_window": 60,
            "min_participation": 1,
            "edge_weight": 0.5,
        },
    )

    with tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT / "output")) as tmpdir:
        previous_root = settings.MODEL_ARTIFACT_ROOT
        settings.MODEL_ARTIFACT_ROOT = tmpdir
        try:
            payload = _write_socgfm_detection_artifact(Path(tmpdir))
            result = detection.predict(batch, feature_rows={}, active_model=payload["active_model"])
        finally:
            settings.MODEL_ARTIFACT_ROOT = previous_root

    assert result.schema_version == "cogguard.cluster-detection-batch/v1"
    assert result.model_role == "primary_socgfm_cross_attention"
    assert len(result.verdicts) == len(batch.candidate_clusters)
    assert {verdict.model_role for verdict in result.verdicts} == {"primary_socgfm_cross_attention"}
    assert {verdict.decision for verdict in result.verdicts} <= {
        "benign_coordination",
        "harmful_coordination",
    }
    assert {verdict.inference_mode for verdict in result.verdicts} == {
        "precomputed_member_probability_cluster_aggregation"
    }
    assert {verdict.claim_scope for verdict in result.verdicts} == {
        "account_level_io_membership_to_cluster_proxy"
    }
    assert {verdict.online_neural_forward for verdict in result.verdicts} == {False}
    assert all(0.0 <= float(verdict.member_probability_coverage) <= 1.0 for verdict in result.verdicts)


def test_socgfm_artifact_rejects_legacy_payload_without_claim_boundary_fields():
    from app.core.analysis.coordination_runtime import _load_detection_runtime_modules

    detection = _load_detection_runtime_modules().socgfm
    artifact = detection.SocGFMCrossAttentionArtifact(
        account_probabilities={"iohunter:1": 0.9},
        source_run_hashes={"predictions.csv": "sha256:" + ("a" * 64)},
    )
    payload = artifact.to_dict()
    for key in (
        "inference_mode",
        "claim_scope",
        "online_neural_forward",
        "unsupported_claims",
        "source_run_hashes",
    ):
        payload.pop(key)

    try:
        detection.SocGFMCrossAttentionArtifact.from_dict(payload)
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("legacy SocGFM artifact payload without claim-boundary fields was accepted")


def test_coordination_detection_quality_gates_reject_non_socgfm_primary_without_abstain():
    gates = evaluate_quality_gates(
        "coordination_detection",
        {
            "macro_f1": 0.82,
            "auprc": 0.81,
            "roc_auc": 0.85,
            "ece": 0.05,
            "p95_latency_seconds": 1.5,
            "shadow_classifier_recorded": True,
        },
    )

    assert gates["activation_allowed"] is False
    assert "abstain" not in gates["checks"]
    assert "coverage" not in gates["checks"]
    assert gates["checks"]["primary_model_is_socgfm_cross_attention"] is False


def test_coordination_detection_quality_gates_allow_socgfm_primary_without_superiority_claim():
    gates = evaluate_quality_gates(
        "coordination_detection",
        {
            "system_primary_model": "socgfm_cross_attention",
            "macro_f1": 0.86,
            "auprc": 0.88,
            "roc_auc": 0.9,
            "ece": 0.1,
            "p95_latency_seconds": 3.0,
            "official_validation_protocol": True,
            "shadow_classifier_recorded": True,
            "no_feature_leakage": True,
            "claimable_superiority_over_shadow_classifier": False,
        },
    )

    assert gates["activation_allowed"] is True
    assert "beats_system_baseline" not in gates["checks"]
    assert "beats_strongest_fair_baseline" not in gates["checks"]
    assert gates["checks"]["shadow_classifier_recorded"] is True
    assert gates["diagnostics"]["calibration_warning"] is False


def test_coordination_detection_quality_gates_warn_on_socgfm_calibration_without_blocking_activation():
    gates = evaluate_quality_gates(
        "coordination_detection",
        {
            "system_primary_model": "socgfm_cross_attention",
            "macro_f1": 0.81,
            "auprc": 0.91,
            "roc_auc": 0.95,
            "ece": 0.37,
            "p95_latency_seconds": 3.0,
            "official_validation_protocol": True,
            "shadow_classifier_recorded": True,
            "no_feature_leakage": True,
            "claimable_superiority_over_shadow_classifier": False,
        },
    )

    assert gates["activation_allowed"] is True
    assert "ece" not in gates["failed_gates"]
    assert gates["diagnostics"]["calibration_warning"] is True


def test_executor_fails_closed_for_non_socgfm_coordination_detection_active_pointer():
    async def scenario():
        snapshot = _snapshot()
        temp_root = Path(tempfile.mkdtemp(dir=str(PROJECT_ROOT / "output")))
        previous_root = settings.MODEL_ARTIFACT_ROOT
        settings.MODEL_ARTIFACT_ROOT = str(temp_root)
        try:
            artifact_payload = _write_coordination_detection_artifact(temp_root)

            class FakeSnapshotCollection:
                def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
                    self.documents = documents

                async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
                    return self.documents.get(str(query["snapshot_id"]))

            class FakeRunStore:
                def __init__(self) -> None:
                    self.runs = {
                        "run-1": {
                            "run_id": "run-1",
                            "event_id": snapshot.event_id,
                            "snapshot_id": snapshot.snapshot_id,
                            "status": "queued",
                            "requested_stages": ["coordination_discover"],
                            "options": {
                                "coordination_discover": {
                                    "time_window": 60,
                                    "min_participation": 1,
                                    "edge_weight": 0.5,
                                }
                            },
                            "finished_at": None,
                        }
                    }
                    self.events: list[dict[str, Any]] = []
                    self.active_models = {
                        "coordination_detection": artifact_payload["active_model"],
                    }

                async def get_snapshot_record(self, snapshot_id: str) -> dict[str, Any] | None:
                    return {
                        "snapshot_id": snapshot.snapshot_id,
                        "mongo_collection": "analysis_event_snapshots",
                        "mongo_key": snapshot.snapshot_id,
                    }

                async def get_run(self, run_id: str) -> dict[str, Any] | None:
                    return dict(self.runs[run_id])

                async def update_run_status(self, *, run_id: str, status, payload: dict[str, Any], finished: bool):
                    run = self.runs[run_id]
                    run["status"] = status.value
                    run["result"] = payload
                    return dict(run)

                async def update_artifact_manifest(self, *, run_id: str, manifest: dict[str, Any]):
                    self.runs[run_id]["artifact_manifest"] = manifest
                    return dict(self.runs[run_id])

                async def append_run_event(self, *, run_id: str, event_type: str, status, payload: dict[str, Any]):
                    event = {"run_id": run_id, "event_type": event_type, "status": status.value, "payload": payload}
                    self.events.append(event)
                    return event

                async def list_run_events(self, *, run_id: str, after_id: int = 0, limit: int = 100):
                    return list(self.events)

                async def get_active_model(self, *, technology: str):
                    return self.active_models.get(technology)

            store = FakeRunStore()
            registry = AnalysisRegistry(
                mongo_db={"analysis_event_snapshots": FakeSnapshotCollection({snapshot.snapshot_id: snapshot.model_dump(mode="json")})},
                store=store,
            )
            analysis_engine = default_analysis_engine_ports()
            executor = AnalysisExecutor(registry=registry, engines=AnalysisEnginePorts(
                coordination=analysis_engine.coordination,
                propagation=analysis_engine.propagation,
                student=analysis_engine.student,
                teacher=analysis_engine.teacher,
                semantic=analysis_engine.semantic,
            ))

            result = await executor.execute_run("run-1")
            coordination_result = result["results"]["coordination_discover"]

            assert coordination_result["status"] == "model_unavailable"
            assert coordination_result["coordination_discovery"]["schema_version"] == "cogguard.discovered-cluster-batch/v1"
            assert coordination_result["coordination_detection"]["technology"] == "coordination_detection"
            assert coordination_result["coordination_detection"]["status"] == "model_unavailable"
            assert coordination_result["coordination_detection"]["model_role"] == "primary_socgfm_cross_attention"
            assert coordination_result["coordination_detection"]["blocking_reason"] == (
                "coordination_detection_active_model_not_socgfm:unsupported_non_socgfm"
            )
            assert result["status"] == "needs_evidence"
        finally:
            settings.MODEL_ARTIFACT_ROOT = previous_root

    asyncio.run(scenario())


def test_executor_uses_socgfm_detection_as_primary_coordination_verdict():
    async def scenario():
        snapshot = _snapshot()
        temp_root = Path(tempfile.mkdtemp(dir=str(PROJECT_ROOT / "output")))
        previous_root = settings.MODEL_ARTIFACT_ROOT
        settings.MODEL_ARTIFACT_ROOT = str(temp_root)
        try:
            artifact_payload = _write_socgfm_detection_artifact(temp_root)

            class FakeSnapshotCollection:
                def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
                    self.documents = documents

                async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
                    return self.documents.get(str(query["snapshot_id"]))

            class FakeRunStore:
                def __init__(self) -> None:
                    self.runs = {
                        "run-socgfm": {
                            "run_id": "run-socgfm",
                            "event_id": snapshot.event_id,
                            "snapshot_id": snapshot.snapshot_id,
                            "status": "queued",
                            "requested_stages": ["coordination_discover"],
                            "options": {
                                "coordination_discover": {
                                    "time_window": 60,
                                    "min_participation": 1,
                                    "edge_weight": 0.5,
                                }
                            },
                            "finished_at": None,
                        }
                    }
                    self.events: list[dict[str, Any]] = []
                    self.active_models = {
                        "coordination_detection": artifact_payload["active_model"],
                    }

                async def get_snapshot_record(self, snapshot_id: str) -> dict[str, Any] | None:
                    return {
                        "snapshot_id": snapshot.snapshot_id,
                        "mongo_collection": "analysis_event_snapshots",
                        "mongo_key": snapshot.snapshot_id,
                    }

                async def get_run(self, run_id: str) -> dict[str, Any] | None:
                    return dict(self.runs[run_id])

                async def update_run_status(self, *, run_id: str, status, payload: dict[str, Any], finished: bool):
                    run = self.runs[run_id]
                    run["status"] = status.value
                    run["result"] = payload
                    return dict(run)

                async def update_artifact_manifest(self, *, run_id: str, manifest: dict[str, Any]):
                    self.runs[run_id]["artifact_manifest"] = manifest
                    return dict(self.runs[run_id])

                async def append_run_event(self, *, run_id: str, event_type: str, status, payload: dict[str, Any]):
                    event = {"run_id": run_id, "event_type": event_type, "status": status.value, "payload": payload}
                    self.events.append(event)
                    return event

                async def list_run_events(self, *, run_id: str, after_id: int = 0, limit: int = 100):
                    return list(self.events)

                async def get_active_model(self, *, technology: str):
                    return self.active_models.get(technology)

            store = FakeRunStore()
            registry = AnalysisRegistry(
                mongo_db={"analysis_event_snapshots": FakeSnapshotCollection({snapshot.snapshot_id: snapshot.model_dump(mode="json")})},
                store=store,
            )
            analysis_engine = default_analysis_engine_ports()
            executor = AnalysisExecutor(registry=registry, engines=AnalysisEnginePorts(
                coordination=analysis_engine.coordination,
                propagation=analysis_engine.propagation,
                student=analysis_engine.student,
                teacher=analysis_engine.teacher,
                semantic=analysis_engine.semantic,
            ))

            result = await executor.execute_run("run-socgfm")
            coordination_result = result["results"]["coordination_discover"]
            detection_payload = coordination_result["coordination_detection"]

            assert coordination_result["status"] == "ok"
            assert detection_payload["model_role"] == "primary_socgfm_cross_attention"
            assert detection_payload["model_version"] == "socgfm_cross_attention/v1"
            assert detection_payload["inference_mode"] == "precomputed_member_probability_cluster_aggregation"
            assert detection_payload["claim_scope"] == "account_level_io_membership_to_cluster_proxy"
            assert detection_payload["online_neural_forward"] is False
            assert detection_payload["runtime_diagnostics"]["online_neural_forward_executed"] is False
            assert detection_payload["verdicts"][0]["inference_mode"] == "precomputed_member_probability_cluster_aggregation"
            assert detection_payload["verdicts"][0]["claim_scope"] == "account_level_io_membership_to_cluster_proxy"
            assert detection_payload["verdicts"][0]["online_neural_forward"] is False
            assert 0.0 <= detection_payload["verdicts"][0]["member_probability_coverage"] <= 1.0
            label_cases = coordination_result["coordination_group_label_cases"]
            assert label_cases
            assert label_cases[0]["review_status"] == "pending"
            assert label_cases[0]["cluster_harm_label"] is None
            assert label_cases[0]["model_output"]["claim_scope"] == "account_level_io_membership_to_cluster_proxy"
            assert label_cases[0]["characterization"]["harmfulness"]["source"] == "coordination_detection"
            assert label_cases[0]["characterization"]["authenticity"]["source"] == "account_profile_bot_detection_join"
            assert label_cases[0]["characterization"]["orchestration"]["source"] == "coordination_discovery_metrics"
            assert label_cases[0]["characterization"]["time_variance"]["source"] == "coordination_discovery_lineage"
            assert "shadow_detection" not in detection_payload
            assert result["status"] == "completed"
        finally:
            settings.MODEL_ARTIFACT_ROOT = previous_root

    asyncio.run(scenario())
