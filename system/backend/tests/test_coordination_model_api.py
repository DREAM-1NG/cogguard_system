import asyncio
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import coordination as coordination_api
from app.core.security import get_current_user
from app.db.mysql import get_db
from app.main import app


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


def test_coordination_result_routes_reuse_cached_payload(monkeypatch):
    calls = {"latest": 0, "graph": 0}

    async def fake_latest(_db, dataset_id):
        calls["latest"] += 1
        return {"dataset_summary": {"dataset_id": dataset_id}, "status": "completed"}

    async def fake_graph(_db, dataset_id, *, node_limit, min_node_score):
        calls["graph"] += 1
        return {
            "nodes": [{"id": "u1", "label": "u1"}],
            "links": [],
            "summary": {
                "total_nodes": 1,
                "total_edges": 0,
                "rendered_node_count": 1,
                "rendered_edge_count": 0,
                "filters": {"node_limit": node_limit, "min_node_score": min_node_score},
            },
        }

    async def fake_db():
        yield object()

    async def fake_user():
        return None

    async def exercise_routes():
        coordination_api.clear_coordination_response_cache()
        monkeypatch.setattr(coordination_api, "get_coordination_dataset_latest_result", fake_latest)
        monkeypatch.setattr(coordination_api, "get_coordination_dataset_graph", fake_graph)
        previous_db_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = fake_db
        app.dependency_overrides[get_current_user] = fake_user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                first_latest = await client.get("/api/v1/coordination/datasets/123/latest-result")
                second_latest = await client.get("/api/v1/coordination/datasets/123/latest-result")
                first_graph = await client.get("/api/v1/coordination/datasets/123/graph?node_limit=50&min_node_score=0")
                second_graph = await client.get("/api/v1/coordination/datasets/123/graph?node_limit=50&min_node_score=0")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            if previous_db_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_db_override
            coordination_api.clear_coordination_response_cache()
        return first_latest, second_latest, first_graph, second_graph

    first_latest, second_latest, first_graph, second_graph = asyncio.run(exercise_routes())

    assert first_latest.status_code == 200
    assert second_latest.status_code == 200
    assert first_graph.status_code == 200
    assert second_graph.status_code == 200
    assert calls == {"latest": 1, "graph": 1}


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
