import numpy as np

from research.social_bot_detection.evaluation import prediction_rows


def test_prediction_rows_preserve_source_label():
    rows = prediction_rows(
        ["a"],
        [1],
        np.asarray([0.7]),
        np.asarray([0.8]),
        np.asarray([True]),
        ["social_spambots_1"],
    )
    assert rows[0]["source_label"] == "social_spambots_1"
