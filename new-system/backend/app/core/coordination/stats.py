"""协同检测统计功能（对应 CooRTweet account_stats / group_stats）。"""

from __future__ import annotations

import pandas as pd
import networkx as nx


def account_stats(G: nx.Graph, result: pd.DataFrame) -> pd.DataFrame:
    """按账户汇总协同指标。

    Returns
    -------
    DataFrame
        列: account_id, degree, avg_weight, avg_time_delta,
            avg_edge_symmetry, coordinated_shares_count
    """
    if G.number_of_edges() == 0:
        return pd.DataFrame(columns=[
            "account_id", "degree", "avg_weight", "avg_time_delta",
            "avg_edge_symmetry", "coordinated_shares_count",
        ])

    rows = []
    for u, v, d in G.edges(data=True):
        w = d.get("weight", 1)
        td = d.get("avg_time_delta", 0)
        sym = d.get("edge_symmetry_score", 0)
        rows.append({"account_id": u, "weight": w, "avg_time_delta": td, "sym": sym})
        rows.append({"account_id": v, "weight": w, "avg_time_delta": td, "sym": sym})

    edge_df = pd.DataFrame(rows)
    stats = edge_df.groupby("account_id").agg(
        degree=("weight", "count"),
        avg_weight=("weight", "mean"),
        avg_time_delta=("avg_time_delta", "mean"),
        avg_edge_symmetry=("sym", "mean"),
    ).reset_index()

    share_counts = pd.concat([
        result[["content_id", "account_id"]].rename(columns={"content_id": "cid"}),
        result[["content_id_y", "account_id_y"]].rename(
            columns={"content_id_y": "cid", "account_id_y": "account_id"}
        ),
    ]).drop_duplicates()
    share_agg = share_counts.groupby("account_id")["cid"].nunique().reset_index()
    share_agg.columns = ["account_id", "coordinated_shares_count"]

    stats = stats.merge(share_agg, on="account_id", how="left")
    stats["coordinated_shares_count"] = stats["coordinated_shares_count"].fillna(0).astype(int)

    for col in ["avg_weight", "avg_time_delta", "avg_edge_symmetry"]:
        stats[col] = stats[col].round(4)

    return stats.sort_values("avg_weight", ascending=False).reset_index(drop=True)


def group_stats(G: nx.Graph, result: pd.DataFrame) -> pd.DataFrame:
    """按 object_id 汇总哪些共享对象涉及最多协调账户。

    Returns
    -------
    DataFrame
        列: object_id, num_accounts, num_pairs
    """
    if result.empty:
        return pd.DataFrame(columns=["object_id", "num_accounts", "num_pairs"])

    coord_accounts = set()
    for n in G.nodes():
        coord_accounts.add(str(n))

    coord_result = result[
        result["account_id"].astype(str).isin(coord_accounts)
        | result["account_id_y"].astype(str).isin(coord_accounts)
    ]

    if coord_result.empty:
        return pd.DataFrame(columns=["object_id", "num_accounts", "num_pairs"])

    groups = []
    for obj_id, grp in coord_result.groupby("object_id"):
        accounts = set(grp["account_id"].astype(str)) | set(grp["account_id_y"].astype(str))
        groups.append({
            "object_id": obj_id,
            "num_accounts": len(accounts),
            "num_pairs": len(grp),
        })

    return pd.DataFrame(groups).sort_values("num_accounts", ascending=False).reset_index(drop=True)
