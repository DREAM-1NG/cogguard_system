import math

from benchmark.adapters.fair_protocol import (
    FIRST_REAL_USER_ID,
    PAD_USER_ID,
    EOS_USER_ID,
    UNK_USER_ID,
    build_fair_protocol_audit,
    build_prefix_windows,
    build_training_user_vocabulary,
    compute_macro_metrics,
    compute_micro_metrics,
    gate_fair_protocol,
    load_original_cascade_splits,
    observation_count,
    parse_forest_cascade,
)
from benchmark.adapters.fair_learned_adapters import run_fair_learned_adapter


def test_parse_and_load_original_split_files(tmp_path):
    (tmp_path / "cascade.txt").write_text("10,0 11,1.5 12,3\n", encoding="utf-8")
    (tmp_path / "cascadevalid.txt").write_text("20,0 21,2\n", encoding="utf-8")
    (tmp_path / "cascadetest.txt").write_text("30,0 31,2 bad_token 32,3\n", encoding="utf-8")

    assert parse_forest_cascade("2,2 1,1") == [(1, 1000), (2, 2000)]
    splits = load_original_cascade_splits(tmp_path, min_length=2)

    assert [len(splits[name]) for name in ("train", "valid", "test")] == [1, 1, 1]
    assert splits["train"][0] == [(10, 0), (11, 1500), (12, 3000)]


def test_train_only_vocabulary_reserves_ids_and_maps_eval_oov_to_unk():
    train = [[(10, 0), (11, 1), (10, 2)], [(12, 0), (11, 1)]]
    valid = [[(10, 0), (99, 1)]]
    vocab = build_training_user_vocabulary(train)

    assert (PAD_USER_ID, EOS_USER_ID, UNK_USER_ID, FIRST_REAL_USER_ID) == (0, 1, 2, 3)
    assert vocab.encode(10) >= FIRST_REAL_USER_ID
    assert vocab.encode(99) == UNK_USER_ID
    assert 99 not in vocab.user_to_id
    assert vocab.decode(vocab.encode(10)) == 10

    capped = build_training_user_vocabulary(train + valid, max_train_users=2)
    assert capped.train_user_count == 2
    assert capped.overflow_user_count == 2


def test_prefix_windows_use_observed_prefix_and_same_cascade_future_labels():
    train = [[(10, 0), (11, 1), (12, 2), (13, 3), (14, 4)]]
    vocab = build_training_user_vocabulary(train)
    windows = build_prefix_windows(
        train,
        split="train",
        obs_ratios=[0.1, 0.5],
        vocabulary=vocab,
        trend_steps=3,
    )

    assert len(windows) == 2
    assert observation_count(5, 0.1) == 1
    assert observation_count(5, 0.5) == 3
    assert windows[0].observed_user_ids == (10,)
    assert windows[0].target_user_id == 11
    assert 11 not in windows[0].observed_user_ids
    assert windows[0].final_size == 5
    assert windows[0].trend_counts == (3.0, 4.0, 5.0)
    assert windows[1].observed_user_ids == (10, 11, 12)
    assert windows[1].target_user_id == 13
    assert windows[1].trend_counts == (4.0, 5.0, 5.0)


def test_macro_and_micro_metric_schema():
    macro = compute_macro_metrics(
        observed_sizes=[2, 4],
        final_sizes=[4, 6],
        predicted_sizes=[5, 6],
        trend_true=[[3, 4], [5, 6]],
        trend_pred=[[3, 5], [5, 6]],
    )

    assert set(macro) == {
        "msle",
        "mae",
        "rmse",
        "mape_percent",
        "smape_percent",
        "direction_accuracy",
        "trend_mae",
        "trend_rmse",
    }
    assert macro["mae"] == 0.5
    assert macro["direction_accuracy"] == 1.0

    scores = [
        {3: 0.2, 4: 0.9, 5: 0.1},
        {3: 0.8, 4: 0.3, 5: 0.1},
        {3: 0.8, 4: 0.3, 5: 0.1},
    ]
    micro = compute_micro_metrics(scores, [4, 3, UNK_USER_ID], candidate_ids=[3, 4, 5], k_list=[1, 2])

    assert micro["candidate_recall_full"] == 2 / 3
    assert micro["target_oov_count"] == 1
    assert micro["hits@1"] == 1.0
    assert micro["map@1"] == 1.0
    assert micro["ndcg@2"] == 1.0
    assert math.isclose(micro["mrr"], 1.0)


def test_audit_blocks_hash_bucket_proxy_and_future_candidate_paths():
    train = [[(10, 0), (11, 1), (12, 2)]]
    valid = [[(10, 0), (99, 1)]]
    test = [[(12, 0), (98, 1)]]
    vocab = build_training_user_vocabulary(train)

    ok = build_fair_protocol_audit(
        train_cascades=train,
        valid_cascades=valid,
        test_cascades=test,
        vocabulary=vocab,
        uses_original_splits=True,
        uses_train_only_vocabulary=True,
        uses_hash_buckets=False,
        uses_proxy_ranking=False,
        candidate_generation_reads_future_tail=False,
        future_nodes_injected=False,
        model_score_source="learned_logits",
        social_graph_status="no_social_edges",
    )
    assert ok["fair_protocol_passed"] is True
    assert gate_fair_protocol(ok) is True
    assert ok["test_oov"]["oov_events"] == 1

    blocked = dict(ok)
    blocked["uses_proxy_ranking"] = True
    blocked["leakage_check_passed"] = False
    blocked["fair_protocol_passed"] = False
    assert gate_fair_protocol(blocked) is False

    blocked_hash = build_fair_protocol_audit(
        train_cascades=train,
        valid_cascades=valid,
        test_cascades=test,
        vocabulary=vocab,
        uses_original_splits=True,
        uses_train_only_vocabulary=True,
        uses_hash_buckets=True,
        uses_proxy_ranking=False,
        candidate_generation_reads_future_tail=False,
        future_nodes_injected=False,
        model_score_source="learned_logits",
        social_graph_status="edges_txt",
    )
    assert blocked_hash["fair_protocol_passed"] is False


def test_same_protocol_learned_adapters_smoke_all_formal_methods(tmp_path):
    rows = [
        "10,0 11,1 12,2 13,3 14,4\n",
        "10,0 12,1 15,2 16,3 17,4\n",
        "18,0 11,1 12,2 19,3 20,4\n",
        "21,0 22,1 23,2 24,3 25,4\n",
        "10,0 11,1 23,2 24,3 25,4\n",
        "18,0 22,1 12,2 13,3 14,4\n",
    ]
    (tmp_path / "cascade.txt").write_text("".join(rows), encoding="utf-8")
    (tmp_path / "cascadevalid.txt").write_text("".join(rows[:2]), encoding="utf-8")
    (tmp_path / "cascadetest.txt").write_text("".join(rows[2:4]), encoding="utf-8")

    for model_name in ("Ours", "MINDS", "FOREST", "CasFT"):
        row = run_fair_learned_adapter(
            tmp_path,
            model_name=model_name,
            dataset="synthetic",
            obs_ratios=[0.3],
            epochs=1,
            batch_size=2,
            hidden_dim=8,
            max_sequence_len=8,
            trend_steps=2,
            max_train_users=0,
            seed=42,
            device="cpu",
            k_list=[1, 5],
        )

        assert row["status"] == "ok"
        assert row["fair_protocol_passed"] is True
        assert row["candidate_protocol_audit"]["uses_hash_buckets"] is False
        assert row["candidate_protocol_audit"]["uses_proxy_ranking"] is False
        assert row["candidate_protocol_audit"]["future_nodes_injected"] is False
        if model_name == "FOREST":
            assert row["macro_supported"] is False
            assert row["msle"] is None
            assert row["hits@5"] is not None
        elif model_name == "CasFT":
            assert row["macro_supported"] is True
            assert row["micro_supported"] is False
            assert row["hits@5"] is None
            assert row["trend_mae"] is not None
        else:
            assert row["macro_supported"] is True
            assert row["micro_supported"] is True
            assert row["msle"] is not None
            assert row["hits@5"] is not None
