import json
import time
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.api.v1 import coordination as coordination_api
from app.services import coordination_model_service


SYSTEM_ARCHIVE_DATASETS = ("UAE", "cuba", "russia", "venezuela", "iran", "china")


def _archive_discovery_summary() -> dict:
    return {
        "metrics": {"modularity": 0.8, "cluster_count": 2},
        "nodes": [
            {"account_id": "u1", "node_score": 0.9, "cluster_id": 0},
            {"account_id": "u2", "node_score": 0.8, "cluster_id": 0},
            {"account_id": "u3", "node_score": 0.3, "cluster_id": 1},
        ],
        "edges": [
            {
                "source": "u1",
                "target": "u2",
                "weight": 2.0,
                "edge_score": 0.9,
                "relations": {"url_share": 2},
            }
        ],
        "communities": [
            {
                "cluster_id": 0,
                "size": 2,
                "community_score": 0.8,
                "density": 1.0,
                "top_objects": [{"object_id": "url:a", "count": 2}],
            },
            {
                "cluster_id": 1,
                "size": 1,
                "community_score": 0.3,
                "density": 0.0,
                "top_objects": [{"object_id": "url:b", "count": 1}],
            },
        ],
        "evidence_summary": {"top_objects": [{"object_id": "url:a", "count": 2}]},
    }


def _archive_detect_summary() -> dict:
    return {
        "predictions": [
            {"account_id": "u1", "node_score": 0.95, "predicted_label": 1, "cluster_id": 0},
            {"account_id": "u2", "node_score": 0.88, "predicted_label": 1, "cluster_id": 0},
            {"account_id": "u3", "node_score": 0.2, "predicted_label": 0, "cluster_id": 1},
        ],
        "metrics": {"auprc": 0.9},
    }


def _write_archive_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def system_archive(monkeypatch, tmp_path: Path):
    archive_root = tmp_path / "archive"
    experiment_root = tmp_path / "experiments"
    event_root = experiment_root / "events"
    discover_root = experiment_root / "discover"
    detect_root = experiment_root / "detect"
    manifest = {
        "archive_name": "test-system-archive",
        "dataset_scale": [
            {
                "dataset": name,
                "event_rows": 3,
                "account_nodes": 3,
                "object_ids": 2,
                "user_user_edges": 1,
                "relations": ["url_share"],
            }
            for name in SYSTEM_ARCHIVE_DATASETS
        ],
    }
    _write_archive_file(archive_root / "archive_manifest.json", manifest)

    for name in SYSTEM_ARCHIVE_DATASETS:
        event_path = event_root / name / "events.csv"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            "\n".join(
                [
                    "account_id,relation,object_id,timestamp,content_id,content,label",
                    "u1,url_share,url:a,1,c1,alpha beta,1",
                    "u2,url_share,url:a,2,c2,alpha gamma,1",
                    "u3,url_share,url:b,3,c3,gamma delta,0",
                ]
            ),
            encoding="utf-8",
        )
        _write_archive_file(
            discover_root / name / "seed_42" / "magnn" / "discovery_summary.json",
            _archive_discovery_summary(),
        )
        _write_archive_file(
            detect_root
            / f"{name}_batch"
            / name
            / "seed_42"
            / "magnn"
            / "supervised"
            / "fusion_gnn"
            / "sbert"
            / "detection_summary.json",
            _archive_detect_summary(),
        )

    monkeypatch.setattr(coordination_model_service, "ARCHIVE_MANIFEST_PATH", archive_root / "archive_manifest.json")
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_DETECT_METRICS_PATH", archive_root / "missing_metrics.csv")
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_EVENT_ROOT", event_root)
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_DISCOVER_DETAIL_ROOT", discover_root)
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_FUSION_DETAIL_ROOT", detect_root)


@pytest.fixture
def incomplete_system_archive(monkeypatch, tmp_path: Path):
    manifest_path = tmp_path / "archive_manifest.json"
    _write_archive_file(
        manifest_path,
        {
            "archive_name": "incomplete-system-archive",
            "dataset_scale": [
                {
                    "dataset": "partial",
                    "event_rows": 1,
                    "account_nodes": 1,
                    "object_ids": 1,
                    "user_user_edges": 0,
                    "relations": ["url_share"],
                }
            ],
        },
    )
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_DETECT_METRICS_PATH", tmp_path / "missing_metrics.csv")
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_EVENT_ROOT", tmp_path / "missing_events")
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_DISCOVER_DETAIL_ROOT", tmp_path / "missing_discover")
    monkeypatch.setattr(coordination_model_service, "ARCHIVE_FUSION_DETAIL_ROOT", tmp_path / "missing_detect")


@pytest.mark.asyncio
async def test_coordination_datasets_api_lists_system_archives(
    setup_database, client: AsyncClient, system_archive
):
    username = f"coord_ds_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    resp = await client.get(
        "/api/v1/coordination/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    names = {item["display_name"] for item in body["data"]}
    assert {"UAE", "cuba", "russia", "venezuela", "iran", "china"}.issubset(names)


@pytest.mark.asyncio
async def test_coordination_latest_result_api_returns_snapshot(
    setup_database, client: AsyncClient, system_archive
):
    username = f"coord_latest_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    datasets = await client.get(
        "/api/v1/coordination/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    dataset_id = next(item["dataset_id"] for item in datasets.json()["data"] if item["display_name"] == "russia")

    latest = await client.get(
        f"/api/v1/coordination/datasets/{dataset_id}/latest-result",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert latest.status_code == 200
    body = latest.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["dataset_summary"]["display_name"] == "russia"
    assert "network" in data
    assert "communities" in data
    assert "global_key_nodes" in data
    assert "shared_objects" in data


@pytest.mark.asyncio
async def test_coordination_graph_and_community_apis_return_visualization_payload(
    setup_database, client: AsyncClient, system_archive
):
    username = f"coord_graph_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    datasets = await client.get(
        "/api/v1/coordination/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    dataset_id = next(item["dataset_id"] for item in datasets.json()["data"] if item["display_name"] == "russia")

    graph = await client.get(
        f"/api/v1/coordination/datasets/{dataset_id}/graph",
        params={"node_limit": 50, "min_node_score": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert graph.status_code == 200
    graph_data = graph.json()["data"]
    assert graph_data["summary"]["rendered_node_count"] <= 50
    assert graph_data["summary"]["total_nodes"] >= graph_data["summary"]["rendered_node_count"]
    assert graph_data["nodes"]
    rendered_ids = {node["id"] for node in graph_data["nodes"]}
    assert all(link["source"] in rendered_ids and link["target"] in rendered_ids for link in graph_data["links"])

    first_cluster = graph_data["nodes"][0]["cluster_id"]
    community = await client.get(
        f"/api/v1/coordination/datasets/{dataset_id}/communities/{first_cluster}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert community.status_code == 200
    community_data = community.json()["data"]
    assert str(community_data["cluster_id"]) == str(first_cluster)
    assert community_data["members"]
    assert "topwords" in community_data
    assert "top_objects" in community_data


@pytest.mark.asyncio
async def test_coordination_upload_api_registers_dataset(setup_database, client: AsyncClient):
    username = f"coord_upload_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    csv_content = "\n".join(
        [
            "account_id,relation,object_id,timestamp,content_id,content,label",
            "u1,url_share,https://a.example,1,c1,hello,1",
            "u2,url_share,https://a.example,2,c2,world,0",
            "u1,hashtag_share,#x,3,c3,hello again,1",
            "u2,hashtag_share,#x,4,c4,world again,0",
        ]
    ).encode("utf-8")

    resp = await client.post(
        "/api/v1/coordination/datasets/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("demo.csv", csv_content, "text/csv")},
        data={"display_name": "Uploaded Demo Dataset"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["display_name"] == "Uploaded Demo Dataset"
    assert body["data"]["source_type"] == "uploaded"
    assert body["data"]["has_labels"] is True


@pytest.mark.asyncio
async def test_coordination_runs_api_creates_pending_run_record(
    setup_database, client: AsyncClient, system_archive, monkeypatch
):
    scheduled_run_ids: list[int] = []

    async def record_scheduled_run(run_id: int) -> None:
        scheduled_run_ids.append(run_id)

    monkeypatch.setattr(coordination_api, "run_coordination_model_job", record_scheduled_run)
    username = f"coord_run_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    datasets = await client.get(
        "/api/v1/coordination/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    dataset_id = next(item["dataset_id"] for item in datasets.json()["data"] if item["display_name"] == "russia")

    resp = await client.post(
        "/api/v1/coordination/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={"dataset_id": dataset_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["dataset_id"] == dataset_id
    assert body["data"]["status"] in {"pending", "running"}
    assert scheduled_run_ids == [body["data"]["run_id"]]


@pytest.mark.asyncio
async def test_coordination_datasets_api_ignores_incomplete_system_archives(
    setup_database, client: AsyncClient, incomplete_system_archive
):
    username = f"coord_incomplete_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    response = await client.get(
        "/api/v1/coordination/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    names = {item["display_name"] for item in response.json()["data"]}
    assert "partial" not in names


@pytest.mark.asyncio
async def test_coordination_graph_api_returns_empty_payload_for_uploaded_dataset_without_result(setup_database, client: AsyncClient):
    username = f"coord_empty_{int(time.time())}"
    password = "pass123456"
    email = f"{username}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login.json()["data"]["access_token"]

    csv_content = "\n".join(
        [
            "account_id,relation,object_id,timestamp,content_id,content",
            "u1,reply_target,tweet:1,1,c1,hello",
            "u2,reply_target,tweet:1,2,c2,world",
        ]
    ).encode("utf-8")

    upload = await client.post(
        "/api/v1/coordination/datasets/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("unlabeled.csv", csv_content, "text/csv")},
        data={"display_name": "Uploaded No Result Dataset"},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["data"]["dataset_id"]

    graph = await client.get(
        f"/api/v1/coordination/datasets/{dataset_id}/graph",
        params={"node_limit": 50, "min_node_score": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert graph.status_code == 200
    graph_data = graph.json()["data"]
    assert graph_data["nodes"] == []
    assert graph_data["links"] == []
    assert graph_data["summary"]["total_nodes"] == 0
    assert graph_data["run_summary"]["status"] == "no_result"
