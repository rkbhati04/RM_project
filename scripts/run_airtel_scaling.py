#!/usr/bin/env python3
"""Generate Airtel-only scaling curves for domain count and repeat count."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURES = [
    "n_pkts", "n_up", "n_down", "bytes_up", "bytes_down", "bytes_total",
    "ratio_bytes_down_up", "duration", "up_mean", "up_std", "up_max",
    "down_mean", "down_std", "down_max", "iat_mean", "iat_std",
    "iat_median", "iat_max", "t_first_down", "n_bursts",
    "burst_len_mean", "burst_len_max", "burst_bytes_mean", "burst_bytes_max",
    *[f"pkt_{index:02d}" for index in range(20)],
]
SEEDS = (17, 42, 101)


def evaluate(frame: pd.DataFrame, domains: list[str], repeats: list[int], seed: int) -> float:
    subset = frame[frame["domain"].isin(domains) & frame["repeat"].isin(repeats)].copy()
    train_repeats, test_repeats = repeats[:-2], repeats[-2:]
    train = subset[subset["repeat"].isin(train_repeats)]
    test = subset[subset["repeat"].isin(test_repeats)]
    if train.empty or test.empty or train["domain"].nunique() < 2:
        return float("nan")
    model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced_subsample",
        random_state=seed,
        n_jobs=1,
    )
    model.fit(train[FEATURES], train["domain"])
    return float((model.predict(test[FEATURES]) == test["domain"]).mean())


def choose_domains(frame: pd.DataFrame, count: int, repeats: list[int], seed: int) -> list[str]:
    eligible = (
        frame[frame["repeat"].isin(repeats)]
        .groupby("domain")["repeat"]
        .nunique()
    )
    domains = sorted(eligible[eligible >= len(repeats)].index)
    if len(domains) < count:
        return []
    rng = np.random.default_rng(seed)
    return sorted(rng.choice(domains, size=count, replace=False).tolist())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/dataset_v2.csv"))
    parser.add_argument("--out", type=Path, default=Path("results/airtel_scaling_20261113"))
    args = parser.parse_args()

    frame = pd.read_csv(args.dataset).dropna(subset=FEATURES + ["domain", "repeat"])
    frame["repeat"] = pd.to_numeric(frame["repeat"], errors="coerce")
    frame = frame[frame["network"].eq("airtel") & frame["repeat"].between(8, 19)]
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for (workload, resolver, protocol), group in frame.groupby(
        ["workload", "resolver", "protocol"]
    ):
        for repeat_count in (4, 6, 8, 10):
            repeats = list(range(8, 8 + repeat_count))
            for domain_count in (10, 25, 50, 75, 100):
                domains = choose_domains(group, domain_count, repeats, 17)
                if not domains:
                    continue
                scores = [evaluate(group, domains, repeats, seed) for seed in SEEDS]
                rows.append({
                    "workload": workload,
                    "resolver": resolver,
                    "protocol": protocol,
                    "domain_count": domain_count,
                    "repeat_count": repeat_count,
                    "accuracy": float(np.nanmean(scores)),
                    "accuracy_seed_sd": float(np.nanstd(scores)),
                })

    result = pd.DataFrame(rows)
    result.to_csv(args.out / "scaling_curves.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    for (workload, resolver, protocol), group in result.groupby(
        ["workload", "resolver", "protocol"]
    ):
        label = f"{workload}/{resolver}/{protocol}"
        axes[0].plot(group.groupby("domain_count")["accuracy"].mean(), marker="o", label=label)
        axes[1].plot(group.groupby("repeat_count")["accuracy"].mean(), marker="o", label=label)
    axes[0].set(xlabel="domains", ylabel="accuracy", title="Accuracy vs. domain count")
    axes[1].set(xlabel="successful repeats per domain", ylabel="accuracy",
                title="Accuracy vs. repeat count")
    axes[0].legend(fontsize=6, ncol=2)
    axes[1].legend(fontsize=6, ncol=2)
    fig.savefig(args.out / "scaling_curves.png", dpi=160)
    print(f"Wrote {len(result)} rows to {args.out / 'scaling_curves.csv'}")
    print(f"Wrote {args.out / 'scaling_curves.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
