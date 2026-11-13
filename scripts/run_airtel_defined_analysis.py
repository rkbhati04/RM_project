#!/usr/bin/env python3
"""Run Airtel-only WP7 richer features and WP11 time-stability analyses."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

BASE_FEATURES = [
    "n_pkts", "n_up", "n_down", "bytes_up", "bytes_down", "bytes_total",
    "ratio_bytes_down_up", "duration", "up_mean", "up_std", "up_max",
    "down_mean", "down_std", "down_max", "iat_mean", "iat_std",
    "iat_median", "iat_max", "t_first_down", "n_bursts",
    "burst_len_mean", "burst_len_max", "burst_bytes_mean", "burst_bytes_max",
    *[f"pkt_{index:02d}" for index in range(20)],
]
SEEDS = (17, 42, 101)


def bucket(value: float) -> str:
    magnitude = abs(value)
    if magnitude <= 64:
        band = "64"
    elif magnitude <= 128:
        band = "128"
    elif magnitude <= 256:
        band = "256"
    elif magnitude <= 512:
        band = "512"
    elif magnitude <= 1024:
        band = "1024"
    elif magnitude <= 1500:
        band = "1500"
    else:
        band = "1501+"
    return ("u" if value >= 0 else "d") + band


def add_sequence_features(frame: pd.DataFrame, start: int = 0) -> pd.DataFrame:
    columns = [f"pkt_{index:02d}" for index in range(start, 20)]
    tokens = frame[columns].fillna(0).applymap(bucket)
    output = frame.copy()
    for width in (2, 3):
        output[f"seq_{start}_gram_{width}"] = [
            " ".join(
                "|".join(row[index:index + width])
                for index in range(len(row) - width + 1)
            )
            for row in tokens.to_numpy()
        ]
    return output


def encode_sequence(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    vocabulary = sorted({
        token
        for column in columns
        for value in frame[column]
        for token in str(value).split()
    })
    index = {token: position for position, token in enumerate(vocabulary)}
    matrix = np.zeros((len(frame), len(vocabulary)), dtype=np.float32)
    for row_index, row in enumerate(frame[columns].itertuples(index=False, name=None)):
        for value in row:
            for token in str(value).split():
                matrix[row_index, index[token]] += 1
    return matrix


def fingerprint_score(frame: pd.DataFrame, features: np.ndarray, seed: int,
                       repeats: list[int]) -> float:
    train = frame["repeat"].isin(repeats[:-2]).to_numpy()
    test = frame["repeat"].isin(repeats[-2:]).to_numpy()
    if train.sum() == 0 or test.sum() == 0:
        return float("nan")
    model = RandomForestClassifier(
        n_estimators=100, class_weight="balanced_subsample",
        random_state=seed, n_jobs=1,
    )
    model.fit(features[train], frame.loc[train, "domain"])
    return float((model.predict(features[test]) == frame.loc[test, "domain"]).mean())


def run_wp7(dataset: pd.DataFrame, output: Path, quick: bool) -> None:
    rows = []
    repeat_values = list(range(8, 8 + (4 if quick else 10)))
    for (workload, resolver, protocol), group in dataset.groupby(
        ["workload", "resolver", "protocol"]
    ):
        group = group[group["repeat"].isin(repeat_values)].copy()
        counts = group.groupby("domain")["repeat"].nunique()
        domains = sorted(counts[counts >= len(repeat_values)].index)
        if len(domains) < 5:
            continue
        group = group[group["domain"].isin(domains)].reset_index(drop=True)
        group = add_sequence_features(group, 0)
        group = add_sequence_features(group, 5)
        for name, columns in (
            ("base", BASE_FEATURES),
            ("packet_size_ngrams", ["seq_0_gram_2", "seq_0_gram_3"]),
            ("post_handshake_ngrams", ["seq_5_gram_2", "seq_5_gram_3"]),
        ):
            encoded = encode_sequence(group, columns) if name != "base" else group[BASE_FEATURES].to_numpy(float)
            scores = [fingerprint_score(group, encoded, seed, repeat_values) for seed in SEEDS]
            rows.append({
                "workload": workload, "resolver": resolver, "protocol": protocol,
                "feature_set": name, "accuracy": float(np.nanmean(scores)),
                "accuracy_seed_sd": float(np.nanstd(scores)), "domains": len(domains),
                "repeats_per_domain": len(repeat_values),
            })
    pd.DataFrame(rows).to_csv(output / "wp7_feature_comparison.csv", index=False)
    (output / "wp7_notes.txt").write_text(
        "Packet-size and post-handshake n-grams are computed from signed packet-size "
        "sequences. Burst n-grams are not reported because the committed feature table "
        "contains burst aggregates, not the original burst sequence.\n",
        encoding="utf-8",
    )


def run_wp11(pilot: pd.DataFrame, t0: pd.DataFrame, output: Path) -> None:
    rows = []
    for (workload, resolver, protocol), test in t0.groupby(
        ["workload", "resolver", "protocol"]
    ):
        train = pilot[
            (pilot["workload"] == workload)
            & (pilot["resolver"] == resolver)
            & (pilot["protocol"] == protocol)
        ]
        common = set(train["domain"]) & set(test["domain"])
        train, test = train[train["domain"].isin(common)], test[test["domain"].isin(common)]
        if len(common) < 5 or train.empty or test.empty:
            continue
        scores = []
        for seed in SEEDS:
            model = RandomForestClassifier(
                n_estimators=100, class_weight="balanced_subsample",
                random_state=seed, n_jobs=1,
            )
            model.fit(train[BASE_FEATURES], train["domain"])
            scores.append(float((model.predict(test[BASE_FEATURES]) == test["domain"]).mean()))
        rows.append({
            "workload": workload, "resolver": resolver, "protocol": protocol,
            "train_repeats": "0-7", "test_repeats": "8-19",
            "domains": len(common), "n_train": len(train), "n_test": len(test),
            "accuracy": float(np.mean(scores)), "accuracy_seed_sd": float(np.std(scores)),
        })
    pd.DataFrame(rows).to_csv(output / "wp11_pilot_t0_stability.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/dataset_v2.csv"))
    parser.add_argument("--pilot", type=Path, default=Path("data/processed/dataset_pilot_v1.csv"))
    parser.add_argument("--out", type=Path, default=Path("results/airtel_defined_20261113"))
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    t0 = pd.read_csv(args.dataset).dropna(subset=BASE_FEATURES + ["domain", "repeat"])
    pilot = pd.read_csv(args.pilot).dropna(subset=BASE_FEATURES + ["domain", "repeat"])
    t0 = t0[t0["network"].eq("airtel") & t0["repeat"].between(8, 19)]
    pilot = pilot[pilot["network"].eq("airtel") & pilot["repeat"].between(0, 7)]
    run_wp7(t0, args.out, args.quick)
    run_wp11(pilot, t0, args.out)
    print(f"Wrote WP7 and WP11 outputs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
