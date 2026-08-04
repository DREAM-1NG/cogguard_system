from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from app.core.review.selective_student import SelectiveStudentEncoder, predict_selective_student_outputs


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_review_trainable_post.py"
SPEC = importlib.util.spec_from_file_location("review_trainable_post_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_student_checkpoint_reloads_with_matching_predictions(tmp_path):
    features = np.asarray([[0.2, 0.4, 0.1, 0.8], [0.8, 0.1, 0.7, 0.3]], dtype="float32")
    model = SelectiveStudentEncoder(input_dim=4, hidden_dim=3, stance_count=4)
    expected_outputs = predict_selective_student_outputs(model, features, device="cpu")
    checkpoint_path = tmp_path / "student_checkpoint.pt"

    runner.save_student_checkpoint(
        checkpoint_path,
        model,
        model_config={"input_dim": 4, "hidden_dim": 3, "stance_count": 4},
        metadata={"dataset": "unit"},
    )

    restored_model, metadata = runner.reload_student_checkpoint(checkpoint_path)
    restored_outputs = predict_selective_student_outputs(restored_model, features, device="cpu")

    assert metadata["dataset"] == "unit"
    for axis, expected in expected_outputs.items():
        np.testing.assert_allclose(restored_outputs[axis], expected, rtol=1e-6, atol=1e-6)
