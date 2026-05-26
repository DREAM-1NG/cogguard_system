import pandas as pd

from app.services import coordination_service


def _weighted_pair_rows() -> pd.DataFrame:
    rows: list[dict] = []

    def add_pair(account_id: str, account_id_y: str, weight: int, prefix: str) -> None:
        for index in range(weight):
            rows.append(
                {
                    "object_id": f"{prefix}-obj-{index}",
                    "account_id": account_id,
                    "account_id_y": account_id_y,
                    "content_id": f"{account_id}-{prefix}-c{index}",
                    "content_id_y": f"{account_id_y}-{prefix}-c{index}",
                    "time_delta": 5,
                }
            )

    add_pair("u1", "u2", 5, "a12")
    add_pair("u2", "u3", 5, "a23")
    add_pair("u1", "u3", 4, "a13")
    add_pair("u4", "u5", 5, "b45")
    add_pair("u5", "u6", 5, "b56")
    add_pair("u4", "u6", 4, "b46")
    add_pair("u3", "u4", 1, "bridge")

    return pd.DataFrame(rows)


def test_graph_to_dict_reports_core_bridge_and_early_nodes():
    graph = coordination_service.generate_coordinated_network(_weighted_pair_rows(), edge_weight=0.5)
    first_seen = {
        "u1": (100.0, "2026-05-21T00:00:00+00:00"),
        "u2": (110.0, "2026-05-21T00:00:10+00:00"),
        "u3": (120.0, "2026-05-21T00:00:20+00:00"),
        "u4": (130.0, "2026-05-21T00:00:30+00:00"),
        "u5": (140.0, "2026-05-21T00:00:40+00:00"),
        "u6": (150.0, "2026-05-21T00:00:50+00:00"),
    }
    for node, (first_seen_ts, first_seen_at) in first_seen.items():
        graph.nodes[node]["first_seen_ts"] = first_seen_ts
        graph.nodes[node]["first_seen_at"] = first_seen_at
        graph.nodes[node]["coordinated_object_count"] = 3
        graph.nodes[node]["coordinated_content_count"] = 3
        graph.nodes[node]["account_label"] = f"账户-{node}"
        graph.nodes[node]["shared_objects_preview"] = [f"obj-{node}"]
        graph.nodes[node]["shared_object_entries"] = [
            {
                "object_id": f"obj-{node}",
                "object_type": "链接",
                "count": 2,
                "preview": f"obj-{node}",
            }
        ]

    network = coordination_service.graph_to_dict(graph)
    clusters = {
        frozenset(cluster["members"]): cluster
        for cluster in network["clusters"]
    }
    left = clusters[frozenset({"u1", "u2", "u3"})]
    right = clusters[frozenset({"u4", "u5", "u6"})]
    node_map = {node["id"]: node for node in network["nodes"]}

    assert left["bridge_nodes"][0]["account_id"] == "u3"
    assert right["bridge_nodes"][0]["account_id"] == "u4"
    assert left["early_nodes"][0]["account_id"] == "u1"
    assert right["early_nodes"][0]["account_id"] == "u4"
    assert left["core_nodes"]
    assert right["core_nodes"]
    assert left["core_nodes"][0]["account_label"].startswith("账户-")
    assert left["shared_objects_preview"]
    assert node_map["u3"]["cross_cluster_edge_count"] == 1
    assert node_map["u3"]["cross_cluster_weight"] == 1
    assert node_map["u3"]["bridge_score"] > 0
