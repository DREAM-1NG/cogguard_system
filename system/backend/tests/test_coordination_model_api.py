import json
import time

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_coordination_datasets_api_lists_system_archives(setup_database, client: AsyncClient):
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
async def test_coordination_latest_result_api_returns_snapshot(setup_database, client: AsyncClient):
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
async def test_coordination_graph_and_community_apis_return_visualization_payload(setup_database, client: AsyncClient):
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
async def test_coordination_runs_api_creates_pending_run_record(setup_database, client: AsyncClient):
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
