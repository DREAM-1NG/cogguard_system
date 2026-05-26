"""协同行为配对检测（对应 CooRTweet detect_groups / flag_speed_share）。

核心思路：在同一 object_id（共享内容）下，找出所有在 time_window 秒
内发布的内容对，过滤自环和低活跃账户，输出协调配对表。
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def detect_groups(
    df: pd.DataFrame,
    time_window: int = 10,
    min_participation: int = 2,
    remove_loops: bool = True,
) -> pd.DataFrame:
    """检测时间窗口内的协调分享行为。

    Parameters
    ----------
    df : DataFrame
        必须包含列: object_id, account_id, content_id, timestamp_share (Unix 秒)
    time_window : int
        协调时间窗口（秒），默认 10
    min_participation : int
        账户最低参与次数，低于此值的账户被排除
    remove_loops : bool
        是否移除自环（同一账户分享同一对象）

    Returns
    -------
    DataFrame
        列: object_id, account_id, account_id_y, content_id, content_id_y, time_delta
        account_id / content_id 为较早的一方
    """
    required = {"object_id", "account_id", "content_id", "timestamp_share"}
    if not required.issubset(df.columns):
        raise ValueError(f"输入数据缺少必要列: {required - set(df.columns)}")

    data = df[list(required)].copy()
    data["timestamp_share"] = pd.to_numeric(data["timestamp_share"], errors="coerce")
    data = data.dropna(subset=["timestamp_share"])

    if min_participation >= 1:
        active_accounts = _active_accounts_by_unique_content(data, min_participation)
        data = data[data["account_id"].isin(active_accounts)].copy()

    if data.empty:
        return _empty_result()

    results = []
    for _, group in data.groupby("object_id"):
        pairs = _calc_group_combinations(group, time_window)
        if not pairs.empty:
            results.append(pairs)

    if not results:
        return _empty_result()

    result = pd.concat(results, ignore_index=True)

    if remove_loops:
        result = _remove_loops(result)

    if min_participation >= 1:
        result = _filter_min_participation(data, result, min_participation)

    if result.empty:
        return _empty_result()

    # 归一化方向：content_id 始终是较早的（time_delta >= 0 时交换）
    swap = result["time_delta"] > 0
    result.loc[swap, ["content_id", "content_id_y"]] = (
        result.loc[swap, ["content_id_y", "content_id"]].values
    )
    result.loc[swap, ["account_id", "account_id_y"]] = (
        result.loc[swap, ["account_id_y", "account_id"]].values
    )
    result["time_delta"] = result["time_delta"].abs()

    return result.reset_index(drop=True)


def flag_speed_share(
    original_df: pd.DataFrame,
    result: pd.DataFrame,
    min_participation: int,
    time_window: int,
) -> pd.DataFrame:
    """在更窄时间窗上为已有结果打标。

    返回 result 增加一列 ``time_window_{time_window}``，匹配行为 1，否则 0。
    """
    narrowed = result[result["time_delta"] <= time_window].copy()
    narrowed = _filter_min_participation(original_df, narrowed, min_participation)

    col = f"time_window_{time_window}"
    result = result.copy()
    key_pairs = set(zip(narrowed["content_id"], narrowed["content_id_y"]))
    result[col] = [
        1 if (cid, cidy) in key_pairs else 0
        for cid, cidy in zip(result["content_id"], result["content_id_y"])
    ]
    return result


# ---------------------------------------------------------------------------
# 内部函数
# ---------------------------------------------------------------------------

def _calc_group_combinations(group: pd.DataFrame, time_window: int) -> pd.DataFrame:
    """同一 object_id 内，生成所有内容对并筛选时间窗。"""
    n = len(group)
    if n < 2:
        return pd.DataFrame()

    arr = group.reset_index(drop=True)
    obj_id = arr["object_id"].iloc[0]

    indices = np.arange(n)
    i_idx, j_idx = np.meshgrid(indices, indices, indexing="ij")
    mask = i_idx < j_idx
    i_flat = i_idx[mask]
    j_flat = j_idx[mask]

    ts = arr["timestamp_share"].values
    time_deltas = ts[i_flat] - ts[j_flat]
    within = np.abs(time_deltas) <= time_window

    if not within.any():
        return pd.DataFrame()

    i_sel = i_flat[within]
    j_sel = j_flat[within]

    return pd.DataFrame({
        "object_id": obj_id,
        "content_id": arr["content_id"].values[i_sel],
        "content_id_y": arr["content_id"].values[j_sel],
        "account_id": arr["account_id"].values[i_sel],
        "account_id_y": arr["account_id"].values[j_sel],
        "time_delta": time_deltas[within],
    })


def _remove_loops(result: pd.DataFrame) -> pd.DataFrame:
    """移除自环：同账户配对、或 object_id 等于 content_id 的情况。"""
    r = result
    if "object_id" in r.columns:
        r = r[r["object_id"] != r["content_id"]]
        r = r[r["object_id"] != r["content_id_y"]]
    r = r[r["content_id"] != r["content_id_y"]]
    r = r[r["account_id"] != r["account_id_y"]]
    return r


def _filter_min_participation(
    original: pd.DataFrame, result: pd.DataFrame, min_participation: int
) -> pd.DataFrame:
    """根据参与次数再次过滤结果。"""
    if result.empty:
        return result
    content_ids = set(result["content_id"]).union(result["content_id_y"])
    filtered = original[original["content_id"].isin(content_ids)]
    active_accounts = _active_accounts_by_unique_content(filtered, min_participation)
    return result[
        result["account_id"].isin(active_accounts) & result["account_id_y"].isin(active_accounts)
    ]


def _active_accounts_by_unique_content(data: pd.DataFrame, min_participation: int) -> set[str]:
    if data.empty:
        return set()
    counts = data.groupby("account_id")["content_id"].nunique()
    return set(counts[counts >= min_participation].index.astype(str))


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "object_id", "account_id", "account_id_y",
        "content_id", "content_id_y", "time_delta",
    ])
