from __future__ import annotations

from benchmark.adapters.propagation_protocol import (
    UNK_USER_ID,
    build_observation_prefix,
    build_training_user_vocabulary,
    encode_prefix,
    fair_protocol_audit,
    gate_fair_protocol,
)


def test_observation_prefix_never_leaks_future_nodes_into_model_input() -> None:
    cascade = [(10, 0), (11, 1), (99, 2), (100, 3)]
    vocabulary = build_training_user_vocabulary([[(10, 0), (11, 1), (12, 2)]], max_user_ids=32)

    prefix = build_observation_prefix(cascade, 0.5)
    encoded = encode_prefix(prefix["observed"], vocabulary)

    assert [user for user, _timestamp in prefix["observed"]] == [10, 11]
    assert [user for user, _timestamp in encoded] == [vocabulary.encode(10), vocabulary.encode(11)]
    assert 99 not in [user for user, _timestamp in prefix["observed"]]
    assert 100 not in [user for user, _timestamp in prefix["observed"]]
    assert prefix["next_event"] == (99, 2)


def test_training_only_vocabulary_maps_unseen_evaluation_user_to_unk() -> None:
    vocabulary = build_training_user_vocabulary([[(10, 0), (11, 1), (12, 2)]], max_user_ids=32)

    assert vocabulary.encode(10) > UNK_USER_ID
    assert vocabulary.encode(999) == UNK_USER_ID


def test_fair_protocol_gate_requires_train_and_an_evaluation_split() -> None:
    train = [[(10, 0), (11, 1), (12, 2), (13, 3)]]
    vocabulary = build_training_user_vocabulary(train, max_user_ids=32)

    passed = fair_protocol_audit(
        vocabulary=vocabulary,
        train_cascades=train,
        valid_cascades=[],
        test_cascades=[[(10, 0), (99, 1), (100, 2), (101, 3)]],
    )
    blocked = fair_protocol_audit(
        vocabulary=vocabulary,
        train_cascades=train,
        valid_cascades=[],
        test_cascades=[],
    )

    assert passed["test_oov"]["oov_unique_users"] == 3
    assert passed["fair_protocol_passed"] is True
    assert gate_fair_protocol(passed) is True
    assert blocked["fair_protocol_passed"] is False
    assert gate_fair_protocol(blocked) is False
