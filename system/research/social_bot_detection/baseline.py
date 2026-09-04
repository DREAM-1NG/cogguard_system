"""Transparent text-only reference baseline for same-split comparison."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from .contracts import AccountSample

__all__ = ["evaluate_text_baseline"]


def evaluate_text_baseline(
    train_samples: list[AccountSample],
    evaluation_samples: list[AccountSample],
) -> dict[str, Any]:
    """Evaluate a deliberately shallow TF-IDF reference on the same split."""

    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=2, max_features=20000)
    train_matrix = vectorizer.fit_transform([sample.text for sample in train_samples])
    evaluation_matrix = vectorizer.transform([sample.text for sample in evaluation_samples])
    labels = np.asarray([sample.label for sample in train_samples], dtype=np.int64)
    evaluation_labels = np.asarray([sample.label for sample in evaluation_samples], dtype=np.int64)
    model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    model.fit(train_matrix, labels)
    probabilities = model.predict_proba(evaluation_matrix)[:, 1]
    predictions = (probabilities >= 0.5).astype(np.int64)
    return {
        "description": "same-split character TF-IDF + balanced LogisticRegression reference",
        "accuracy": float(accuracy_score(evaluation_labels, predictions)),
        "macro_f1": float(f1_score(evaluation_labels, predictions, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(evaluation_labels, predictions, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(evaluation_labels, predictions, average="macro", zero_division=0)),
        "roc_auc": float(roc_auc_score(evaluation_labels, probabilities)),
        "feature_count": int(train_matrix.shape[1]),
    }
