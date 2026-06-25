#!/usr/bin/env python3
"""
Temporal extrapolation baseline for macroscopic cascade size prediction.

This baseline observes each cascade for a fixed amount of time after the first
activation, estimates a train-set median growth multiplier, and predicts final
cascade size from the observed prefix. It is intentionally simple and exists to
separate "early-time extrapolation" from feature-rich RandomForest regression.
"""
import argparse
import json
import os
from statistics import median
from typing import List, Tuple

import numpy as np


def parse_cascade(line: str) -> List[Tuple[int, int]]:
    cascade: List[Tuple[int, int]] = []
    for raw in line.strip().split():
        parts = raw.split(",")
        if len(parts) != 2:
            continue
        try:
            cascade.append((int(parts[0]), int(parts[1])))
        except ValueError:
            continue
    return sorted(cascade, key=lambda item: item[1])


def load_cascades(path: str) -> List[List[Tuple[int, int]]]:
    cascades: List[List[Tuple[int, int]]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            cascade = parse_cascade(line)
            if len(cascade) >= 3:
                cascades.append(cascade)
    return cascades


def observed_count(cascade: List[Tuple[int, int]], obs_window_seconds: int) -> int:
    start = cascade[0][1]
    cutoff = start + obs_window_seconds
    return sum(1 for _, ts in cascade if ts <= cutoff)


def fit_multiplier(cascades: List[List[Tuple[int, int]]], obs_window_seconds: int) -> float:
    multipliers = []
    for cascade in cascades:
        obs = observed_count(cascade, obs_window_seconds)
        if obs <= 0:
            continue
        multipliers.append(len(cascade) / obs)
    return float(median(multipliers)) if multipliers else 1.0


def msle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    pred = y_pred.copy()
    pred[pred < 1] = 1
    return float(np.mean(np.square(np.log2(pred) - np.log2(y_true))))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_pred - y_true)))


def direction_accuracy(y_true: np.ndarray, y_pred: np.ndarray, observed: np.ndarray, threshold: float) -> float:
    true_growth = y_true >= observed * (1.0 + threshold)
    pred_growth = y_pred >= observed * (1.0 + threshold)
    return float(np.mean(true_growth == pred_growth))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--obs_window_seconds", type=int, default=7 * 24 * 3600)
    parser.add_argument("--direction_threshold", type=float, default=0.1)
    args = parser.parse_args()

    train_path = os.path.join(args.data_dir, "cascade.txt")
    test_path = os.path.join(args.data_dir, "cascadetest.txt")
    train_cascades = load_cascades(train_path)
    test_cascades = load_cascades(test_path)

    multiplier = fit_multiplier(train_cascades, args.obs_window_seconds)
    observed = np.asarray([observed_count(c, args.obs_window_seconds) for c in test_cascades], dtype=float)
    y_true = np.asarray([len(c) for c in test_cascades], dtype=float)
    y_pred = np.maximum(observed * multiplier, observed)

    result = {
        "model": "TemporalSizeBaseline",
        "dataset": os.path.basename(args.data_dir),
        "mode": "fixed_time_window_multiplier",
        "obs_window_seconds": args.obs_window_seconds,
        "train_multiplier_median": multiplier,
        "n_train": len(train_cascades),
        "n_test": len(test_cascades),
        "mean_observed_count": float(np.mean(observed)) if len(observed) else 0.0,
        "msle": msle(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "direction_accuracy": direction_accuracy(y_true, y_pred, observed, args.direction_threshold),
        "hits@10": None,
        "hits@50": None,
        "hits@100": None,
        "map@10": None,
        "map@50": None,
        "map@100": None,
        "note": "Fixed-time early observation baseline; no test future nodes or final-size ratio are used as input.",
    }
    print(
        "[TemporalSizeBaseline] "
        f"MSLE={result['msle']:.4f} MAE={result['mae']:.4f} "
        f"DirAcc={result['direction_accuracy']:.4f}"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
