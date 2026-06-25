#!/usr/bin/env python3
"""
RandomForest baseline for macroscopic cascade size prediction.
Reads FOREST-format cascade files, extracts early-observation features,
trains a RandomForestRegressor, and outputs JSON metrics (MSLE, MAE).

Usage:
    python benchmark/adapters/rf_baseline.py --data_dir FOREST/data/douban --obs_ratio 0.1
"""
import argparse
import json
import os
import numpy as np
from sklearn.ensemble import RandomForestRegressor


def parse_cascade(line):
    """Parse a FOREST-format cascade line: 'user,ts user,ts ...' """
    pairs = line.strip().split()
    if not pairs:
        return []
    result = []
    for p in pairs:
        parts = p.split(",")
        if len(parts) == 2:
            result.append((int(parts[0]), int(parts[1])))
    return result


def extract_features(cascade, obs_ratio=0.1):
    """Extract features from early observation window of a cascade."""
    if len(cascade) < 2:
        return None, None
    obs_count = max(2, int(len(cascade) * obs_ratio))
    obs = cascade[:obs_count]
    timestamps = [ts for _, ts in obs]
    time_span = timestamps[-1] - timestamps[0]
    intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    mean_interval = np.mean(intervals) if intervals else 0
    std_interval = np.std(intervals) if len(intervals) > 1 else 0
    unique_users = len(set(u for u, _ in obs))
    features = [
        obs_count,
        time_span,
        mean_interval,
        std_interval,
        unique_users,
    ]
    target = len(cascade)
    return features, target


def load_cascades(filepath, obs_ratio=0.1):
    """Load cascades from file and extract features."""
    X, y = [], []
    with open(filepath, "r") as f:
        for line in f:
            cascade = parse_cascade(line)
            if len(cascade) < 3:
                continue
            feats, target = extract_features(cascade, obs_ratio)
            if feats is not None:
                X.append(feats)
                y.append(target)
    return np.array(X), np.array(y)


def msle(y_true, y_pred):
    y_pred = y_pred.copy()
    y_pred[y_pred < 1] = 1
    return float(np.mean(np.square(np.log2(y_pred) - np.log2(y_true))))


def mae(y_true, y_pred):
    return float(np.mean(np.abs(y_pred - y_true)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True,
                        help="Path to FOREST-format data dir (contains cascade.txt, cascadetest.txt)")
    parser.add_argument("--obs_ratio", type=float, default=0.1,
                        help="Fraction of cascade to observe for feature extraction")
    parser.add_argument("--n_estimators", type=int, default=200)
    parser.add_argument("--random_state", type=int, default=42)
    args = parser.parse_args()

    train_path = os.path.join(args.data_dir, "cascade.txt")
    test_path = os.path.join(args.data_dir, "cascadetest.txt")

    if not os.path.exists(train_path):
        print(f"[RF] ERROR: {train_path} not found")
        return
    if not os.path.exists(test_path):
        print(f"[RF] ERROR: {test_path} not found")
        return

    print(f"[RF] Loading train data from {train_path}")
    X_train, y_train = load_cascades(train_path, args.obs_ratio)
    print(f"[RF] Loading test data from {test_path}")
    X_test, y_test = load_cascades(test_path, args.obs_ratio)

    print(f"[RF] Train samples: {len(X_train)}, Test samples: {len(X_test)}")

    model = RandomForestRegressor(
        n_estimators=args.n_estimators,
        random_state=args.random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    result = {
        "model": "RF_Baseline",
        "dataset": os.path.basename(args.data_dir),
        "obs_ratio": args.obs_ratio,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "msle": msle(y_test, y_pred),
        "mae": mae(y_test, y_pred),
        "hits@10": None,
        "hits@50": None,
        "hits@100": None,
        "map@10": None,
        "map@50": None,
        "map@100": None,
    }

    print(f"[RF] MSLE={result['msle']:.4f}, MAE={result['mae']:.4f}")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
