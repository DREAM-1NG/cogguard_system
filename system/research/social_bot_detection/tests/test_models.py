import torch

from research.social_bot_detection.base_detector import BaseDetector
from research.social_bot_detection.correction import ResidualCorrection
from research.social_bot_detection.text_encoder import _sample_chunks


def test_base_and_correction_forward_shapes():
    detector = BaseDetector(input_dim=12, hidden_dim=8, dropout=0.0)
    logits, representation = detector(torch.randn(5, 12))
    assert logits.shape == (5, 2)
    assert representation.shape == (5, 8)
    correction = ResidualCorrection(8, 4, 0.0)
    assert correction(representation, representation).shape == (5, 2)


def test_account_chunk_sampling_is_deterministic_and_covers_boundaries():
    chunks = [[index] for index in range(20)]
    sampled = _sample_chunks(chunks, 4)
    assert sampled == [[0], [6], [13], [19]]
