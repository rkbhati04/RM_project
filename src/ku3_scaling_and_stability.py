"""KU3 — WP10 Scaling Curves & WP11 Pilot-vs-T0 Time Stability Analysis.

WP10: Scaling curves of fingerprinting accuracy vs:
  1. Number of domains (N in [10, 25, 50, 75, 100])
  2. Number of repeats per domain (k in [2, 4, 6, 8, 10])
  Evaluated on headline Airtel data (repeats 8-19) with 95% Wilson intervals and chance baselines.

WP11: Temporal stability across time gap:
  Evaluates 4 regimes on the matched 50 common domains:
    - Pilot -> Pilot (Within-pilot CV, repeats 0-7)
    - T0 -> T0 (Within-T0 CV, repeats 8-19)
    - Pilot -> T0 (Train on Pilot past, test on T0 future)
    - T0 -> Pilot (Train on T0, test backwards on Pilot)
  Quantifies temporal decay and HTTP/2 vs HTTP/3 resilience over time.

Usage:
    PYTHONPATH=src python src/ku3_scaling_and_stability.py           # full run
    PYTHONPATH=src python src/ku3_scaling_and_stability.py --quick   # fast run
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

from encdns.analysis.fingerprinting import available_features, select_headline_repeats
from encdns.analysis.stats import empirical_p_value, wilson_interval

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "dataset_v2.csv"
PILOT_PATH = ROOT / "data" / "processed" / "dataset_pilot_v1.csv"
OUT_WP10 = ROOT / "results" / "wp10_scaling_curves"
OUT_WP11 = ROOT / "results" / "wp11_time_stability"

SEEDS = [7, 42, 99]


# =============================================================================
# Helper: Core leave-k-repeats-out evaluator
# =============================================================================

def eval_cv(
    frame: pd.DataFrame,
    features: list[str],
    seeds: list[int],
    permutations: int,
    estimators: int = 100,
    null_estimators: int = 50,
    held_per_fold: int = 2,
    workers: int = 8,
) -> dict:
    """Evaluates cross-validation accuracy on a frame with repeated folds."""
    clean = frame.dropna(subset=features + ["domain", "repeat"]).copy()
    n_domains = clean["domain"].nunique()
    if n_domains < 2 or clean["repeat"].nunique() < 2:
        return {"accuracy": float("nan"), "n": len(clean), "domains": n_domains}

    repeats = sorted(clean["repeat"].unique())
    # If fewer repeats than held_per_fold, hold 1 out
    fold_size = min(held_per_fold, max(1, len(repeats) // 2))
    folds = [repeats[i:i + fold_size] for i in range(0, len(repeats), fold_size)]
    if len(folds) < 2:
        folds = [[r] for r in repeats]

    def _single_fit(seed: int, permute: bool) -> dict | None:
        actual, predicted = [], []
        rng = np.random.default_rng(seed)
        n_trees = null_estimators if permute else estimators
        for held_out in folds:
            train = clean[~clean["repeat"].isin(held_out)]
            test = clean[clean["repeat"].isin(held_out)]
            labels = train["domain"].to_numpy()
            if permute:
                labels = rng.permutation(labels)
            known = test["domain"].isin(set(labels))
            if not known.any():
                continue
            clf = RandomForestClassifier(
                n_estimators=n_trees, class_weight="balanced_subsample",
                n_jobs=1, random_state=seed + int(held_out[0])
            )
            clf.fit(train[features].to_numpy(float), labels)
            test_x = test.loc[known, features].to_numpy(float)
            test_y = test.loc[known, "domain"].to_numpy()
            preds = clf.predict(test_x)
            actual.extend(test_y)
            predicted.extend(preds)
        if not actual:
            return None
        return {
            "acc": accuracy_score(actual, predicted),
            "macro_f1": f1_score(actual, predicted, average="macro"),
            "n_test": len(actual),
            "correct": sum(a == b for a, b in zip(actual, predicted)),
        }

    # Observed runs across seeds
    obs = Parallel(n_jobs=workers)(delayed(_single_fit)(s, False) for s in seeds)
    obs = [r for r in obs if r is not None]
    if not obs:
        return {"accuracy": float("nan"), "n": len(clean), "domains": n_domains}

    mean_acc = float(np.mean([r["acc"] for r in obs]))
    mean_f1 = float(np.mean([r["macro_f1"] for r in obs]))
    total_test = obs[0]["n_test"]
    total_corr = obs[0]["correct"]
    ci_lo, ci_hi = wilson_interval(total_corr, total_test)

    # Permutation test
    null_scores = []
    if permutations > 0:
        nulls = Parallel(n_jobs=workers)(
            delayed(_single_fit)(seeds[0] + 1000 + i, True) for i in range(permutations)
        )
        null_scores = [r["acc"] for r in nulls if r is not None]

    p_val = empirical_p_value(mean_acc, null_scores) if null_scores else float("nan")

    return {
        "accuracy": round(mean_acc, 6),
        "ci_low": round(ci_lo, 6),
        "ci_high": round(ci_hi, 6),
        "macro_f1": round(mean_f1, 6),
        "chance": round(1.0 / n_domains, 6),
        "p_value": round(p_val, 6),
        "n": len(clean),
        "domains": n_domains,
    }


# =============================================================================
# Helper: Direct Train-Test evaluator (for Cross-Time Transfer)
# =============================================================================

def eval_train_test(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    features: list[str],
    seeds: list[int],
    permutations: int,
    estimators: int = 100,
    null_estimators: int = 50,
    workers: int = 8,
) -> dict:
    """Trains on train_df and tests directly on test_df."""
    train_clean = train_df.dropna(subset=features + ["domain"]).copy()
    test_clean = test_df.dropna(subset=features + ["domain"]).copy()

    # Domain intersection
    shared_domains = sorted(set(train_clean["domain"]).intersection(set(test_clean["domain"])))
    train_clean = train_clean[train_clean["domain"].isin(shared_domains)]
    test_clean = test_clean[test_clean["domain"].isin(shared_domains)]

    n_domains = len(shared_domains)
    if n_domains < 2:
        return {"accuracy": float("nan"), "domains": n_domains}

    test_x = test_clean[features].to_numpy(float)
    test_y = test_clean["domain"].to_numpy()

    def _fit(seed: int, permute: bool) -> dict:
        rng = np.random.default_rng(seed)
        labels = train_clean["domain"].to_numpy()
        if permute:
            labels = rng.permutation(labels)
        clf = RandomForestClassifier(
            n_estimators=null_estimators if permute else estimators,
            class_weight="balanced_subsample",
            n_jobs=1,
            random_state=seed,
        )
        clf.fit(train_clean[features].to_numpy(float), labels)
        preds = clf.predict(test_x)
        return {
            "acc": accuracy_score(test_y, preds),
            "macro_f1": f1_score(test_y, preds, average="macro"),
            "correct": sum(a == b for a, b in zip(test_y, preds)),
        }

    obs = Parallel(n_jobs=workers)(delayed(_fit)(s, False) for s in seeds)
    mean_acc = float(np.mean([r["acc"] for r in obs]))
    mean_f1 = float(np.mean([r["macro_f1"] for r in obs]))
    ci_lo, ci_hi = wilson_interval(obs[0]["correct"], len(test_y))

    null_scores = []
    if permutations > 0:
        nulls = Parallel(n_jobs=workers)(
            delayed(_fit)(seeds[0] + 2000 + i, True) for i in range(permutations)
        )
        null_scores = [r["acc"] for r in nulls]

    p_val = empirical_p_value(mean_acc, null_scores) if null_scores else float("nan")

    return {
        "accuracy": round(mean_acc, 6),
        "ci_low": round(ci_lo, 6),
        "ci_high": round(ci_hi, 6),
        "macro_f1": round(mean_f1, 6),
        "chance": round(1.0 / n_domains, 6),
        "p_value": round(p_val, 6),
        "n_train": len(train_clean),
        "n_test": len(test_clean),
        "domains": n_domains,
    }


# =============================================================================
# WP10: Scaling with Domain Count (N)
# =============================================================================

def run_wp10_domains(
    df: pd.DataFrame,
    features: list[str],
    seeds: list[int],
    permutations: int,
    workers: int,
) -> pd.DataFrame:
    print("\n--- Running WP10: Accuracy vs Number of Domains (N) ---")
    domain_steps = [10, 25, 50, 75, 100]
    records = []

    # Filter to headline repeats 8-19
    df_headline = df[df["repeat"].between(8, 19)].copy()

    # Evaluate across resolvers & protocols
    for (resolver, protocol, workload), group in df_headline.groupby(["resolver", "protocol", "workload"]):
        # Retain domains that have at least 10 repeats
        sampled_group, _ = select_headline_repeats(group, 8, 19, target_k=10)
        available_domains = sorted(sampled_group["domain"].unique())
        if len(available_domains) < 10:
            continue

        for n_dom in domain_steps:
            if n_dom > len(available_domains):
                continue
            # Sample subset of domains fixed with seed 42
            rng = np.random.default_rng(42 + n_dom)
            chosen_domains = rng.choice(available_domains, size=n_dom, replace=False)
            sub_df = sampled_group[sampled_group["domain"].isin(chosen_domains)]

            res = eval_cv(sub_df, features, seeds, permutations, workers=workers)
            records.append({
                "resolver": resolver,
                "protocol": protocol,
                "workload": workload,
                "domain_count": n_dom,
                "actual_domains": res["domains"],
                "accuracy": res["accuracy"],
                "ci_low": res["ci_low"],
                "ci_high": res["ci_high"],
                "macro_f1": res["macro_f1"],
                "chance": res["chance"],
                "p_value": res["p_value"],
                "n_samples": res["n"],
            })
            print(f"  {resolver:10s} {protocol:5s} {workload:6s} | N={n_dom:3d} -> Acc={res['accuracy']:.4f} (chance={res['chance']:.4f})")

    return pd.DataFrame(records)


# =============================================================================
# WP10: Scaling with Repeats per Domain (k)
# =============================================================================

def run_wp10_repeats(
    df: pd.DataFrame,
    features: list[str],
    seeds: list[int],
    permutations: int,
    workers: int,
) -> pd.DataFrame:
    print("\n--- Running WP10: Accuracy vs Repeats per Domain (k) ---")
    k_steps = [2, 4, 6, 8, 10]
    records = []

    df_headline = df[df["repeat"].between(8, 19)].copy()

    for (resolver, protocol, workload), group in df_headline.groupby(["resolver", "protocol", "workload"]):
        # Base pool of domains meeting at least 10 repeats
        pool, _ = select_headline_repeats(group, 8, 19, target_k=10)
        if pool.empty or pool["domain"].nunique() < 25:
            continue

        for k in k_steps:
            # Subsample exactly k repeats per domain (robust across pandas versions)
            idx_list = [
                idx
                for _, g in pool.groupby("domain")
                for idx in g.sample(n=min(k, len(g)), random_state=17).index
            ]
            sampled = pool.loc[idx_list].copy()

            res = eval_cv(sampled, features, seeds, permutations, held_per_fold=1 if k <= 3 else 2, workers=workers)
            records.append({
                "resolver": resolver,
                "protocol": protocol,
                "workload": workload,
                "repeats_k": k,
                "domains": res["domains"],
                "accuracy": res["accuracy"],
                "ci_low": res["ci_low"],
                "ci_high": res["ci_high"],
                "macro_f1": res["macro_f1"],
                "chance": res["chance"],
                "p_value": res["p_value"],
                "n_samples": res["n"],
            })
            print(f"  {resolver:10s} {protocol:5s} {workload:6s} | k={k:2d} -> Acc={res['accuracy']:.4f}")

    return pd.DataFrame(records)


# =============================================================================
# WP11: Temporal Stability Analysis (Pilot vs T0)
# =============================================================================

def run_wp11_time_stability(
    df_v2: pd.DataFrame,
    df_pilot: pd.DataFrame,
    features: list[str],
    seeds: list[int],
    permutations: int,
    workers: int,
) -> pd.DataFrame:
    print("\n--- Running WP11: Time Stability Analysis (Pilot vs T0) ---")

    # Common domains strictly present in both
    common_domains = sorted(set(df_pilot["domain"]).intersection(set(df_v2["domain"])))
    print(f"  Identified {len(common_domains)} common domains between Pilot and T0")

    # Pilot dataset: repeats 0-7
    pilot_matched = df_pilot[df_pilot["domain"].isin(common_domains)].copy()

    # T0 dataset: repeats 8-19, sampled to matched 50 domains with k=8 repeats (matching pilot volume)
    t0_matched = df_v2[
        (df_v2["repeat"].between(8, 19)) & (df_v2["domain"].isin(common_domains))
    ].copy()

    records = []

    slices = [
        (res, proto)
        for res in sorted(pilot_matched["resolver"].unique())
        for proto in sorted(pilot_matched["protocol"].unique())
    ]

    for resolver, protocol in slices:
        p_slice = pilot_matched[(pilot_matched["resolver"] == resolver) & (pilot_matched["protocol"] == protocol)]
        t_slice = t0_matched[(t0_matched["resolver"] == resolver) & (t0_matched["protocol"] == protocol)]

        if p_slice.empty or t_slice.empty:
            continue

        # 1. Pilot within-period CV
        res_p_within = eval_cv(p_slice, features, seeds, permutations, workers=workers)

        # 2. T0 within-period CV (sample k=8 per domain for fair sample size)
        t_slice_k8, _ = select_headline_repeats(t_slice, 8, 19, target_k=8)
        if t_slice_k8.empty:
            t_slice_k8 = t_slice
        res_t_within = eval_cv(t_slice_k8, features, seeds, permutations, workers=workers)

        # 3. Cross-time: Train Pilot -> Test T0
        res_p_to_t = eval_train_test(p_slice, t_slice, features, seeds, permutations, workers=workers)

        # 4. Cross-time: Train T0 -> Test Pilot
        res_t_to_p = eval_train_test(t_slice, p_slice, features, seeds, permutations, workers=workers)

        # Compute temporal degradation
        acc_p_within = res_p_within["accuracy"]
        acc_p_to_t = res_p_to_t["accuracy"]
        decay_p_to_t = acc_p_within - acc_p_to_t

        acc_t_within = res_t_within["accuracy"]
        acc_t_to_p = res_t_to_p["accuracy"]
        decay_t_to_p = acc_t_within - acc_t_to_p

        record = {
            "resolver": resolver,
            "protocol": protocol,
            "common_domains": len(common_domains),
            # Within
            "acc_pilot_within": acc_p_within,
            "ci_pilot_within_lo": res_p_within["ci_low"],
            "ci_pilot_within_hi": res_p_within["ci_high"],
            "acc_t0_within": acc_t_within,
            "ci_t0_within_lo": res_t_within["ci_low"],
            "ci_t0_within_hi": res_t_within["ci_high"],
            # Cross
            "acc_pilot_to_t0": acc_p_to_t,
            "ci_p_to_t_lo": res_p_to_t["ci_low"],
            "ci_p_to_t_hi": res_p_to_t["ci_high"],
            "p_val_p_to_t": res_p_to_t["p_value"],
            "acc_t0_to_pilot": acc_t_to_p,
            "ci_t_to_p_lo": res_t_to_p["ci_low"],
            "ci_t_to_p_hi": res_t_to_p["ci_high"],
            "p_val_t_to_p": res_t_to_p["p_value"],
            # Decay
            "temporal_decay_forward": round(decay_p_to_t, 4),
            "temporal_decay_backward": round(decay_t_to_p, 4),
            "chance": round(1.0 / len(common_domains), 4),
        }
        records.append(record)
        print(f"  {resolver:10s} {protocol:5s} | Pilot Within: {acc_p_within:.3f} -> Pilot->T0: {acc_p_to_t:.3f} (Decay: {decay_p_to_t:+.3f})")

    return pd.DataFrame(records)


# =============================================================================
# Plotting helpers
# =============================================================================

def plot_wp10_domains(df_domains: pd.DataFrame, out_path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    workloads = ["global", "india"]
    resolvers = sorted(df_domains["resolver"].unique())
    colors = {"adguard": "#1f77b4", "cloudflare": "#ff7f0e", "google": "#2ca02c", "quad9": "#d62728"}

    for idx, wl in enumerate(workloads):
        ax = axes[idx]
        sub = df_domains[df_domains["workload"] == wl]
        for res in resolvers:
            for proto, ls in [("doh", "-"), ("doh3", "--")]:
                curve = sub[(sub["resolver"] == res) & (sub["protocol"] == proto)].sort_values("domain_count")
                if curve.empty:
                    continue
                ax.plot(
                    curve["domain_count"], curve["accuracy"],
                    linestyle=ls, marker="o", color=colors.get(res, "gray"),
                    label=f"{res} ({proto})"
                )
                ax.fill_between(
                    curve["domain_count"], curve["ci_low"], curve["ci_high"],
                    color=colors.get(res, "gray"), alpha=0.1
                )
        # Plot chance level 1/N
        n_vals = np.array([10, 25, 50, 75, 100])
        ax.plot(n_vals, 1.0 / n_vals, "k:", label="Chance (1/N)", alpha=0.7)
        ax.set_title(f"Scaling vs Domain Count — {wl.capitalize()} Workload", fontsize=12, fontweight="bold")
        ax.set_xlabel("Number of Domains (Closed World)", fontsize=11)
        ax.set_ylabel("Fingerprinting Accuracy" if idx == 0 else "", fontsize=11)
        ax.grid(True, linestyle="--", alpha=0.5)

    axes[0].legend(loc="upper right", fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure: {out_path}")


def plot_wp10_repeats(df_repeats: pd.DataFrame, out_path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    workloads = ["global", "india"]
    resolvers = sorted(df_repeats["resolver"].unique())
    colors = {"adguard": "#1f77b4", "cloudflare": "#ff7f0e", "google": "#2ca02c", "quad9": "#d62728"}

    for idx, wl in enumerate(workloads):
        ax = axes[idx]
        sub = df_repeats[df_repeats["workload"] == wl]
        for res in resolvers:
            for proto, ls in [("doh", "-"), ("doh3", "--")]:
                curve = sub[(sub["resolver"] == res) & (sub["protocol"] == proto)].sort_values("repeats_k")
                if curve.empty:
                    continue
                ax.plot(
                    curve["repeats_k"], curve["accuracy"],
                    linestyle=ls, marker="s", color=colors.get(res, "gray"),
                    label=f"{res} ({proto})"
                )
                ax.fill_between(
                    curve["repeats_k"], curve["ci_low"], curve["ci_high"],
                    color=colors.get(res, "gray"), alpha=0.1
                )
        ax.set_title(f"Scaling vs Repeats per Domain — {wl.capitalize()} Workload", fontsize=12, fontweight="bold")
        ax.set_xlabel("Repeats per Domain (k)", fontsize=11)
        ax.set_ylabel("Fingerprinting Accuracy" if idx == 0 else "", fontsize=11)
        ax.grid(True, linestyle="--", alpha=0.5)

    axes[0].legend(loc="upper left", fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure: {out_path}")


def plot_wp11_stability(df_stab: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(df_stab))
    width = 0.22

    labels = [f"{r['resolver']}\n{r['protocol'].upper()}" for _, r in df_stab.iterrows()]

    rects1 = ax.bar(x - 1.5 * width, df_stab["acc_pilot_within"], width, label="Within-Pilot (CV)", color="#4a7bb7")
    rects2 = ax.bar(x - 0.5 * width, df_stab["acc_t0_within"], width, label="Within-T0 (CV)", color="#6acc65")
    rects3 = ax.bar(x + 0.5 * width, df_stab["acc_pilot_to_t0"], width, label="Cross-Time (Pilot -> T0)", color="#e58338")
    rects4 = ax.bar(x + 1.5 * width, df_stab["acc_t0_to_pilot"], width, label="Cross-Time (T0 -> Pilot)", color="#b054a8")

    ax.axhline(0.02, color="red", linestyle=":", label="Chance (1/50 = 2.0%)")

    ax.set_ylabel("Accuracy", fontsize=11)
    ax.set_title("WP11: Temporal Stability Across Time Gap (50 Matched Domains)", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure: {out_path}")


# =============================================================================
# Main entrypoint
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Quick smoke test mode")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers for joblib")
    parser.add_argument("--force", action="store_true", help="Re-run all steps even if output CSV exists")
    args = parser.parse_args()

    OUT_WP10.mkdir(parents=True, exist_ok=True)
    OUT_WP11.mkdir(parents=True, exist_ok=True)

    seeds = SEEDS[:2] if args.quick else SEEDS
    permutations = 20 if args.quick else 100

    print("Loading datasets...")
    df_v2 = pd.read_csv(DATA_PATH)
    df_pilot = pd.read_csv(PILOT_PATH)
    features = available_features(df_v2)
    print(f"Using {len(features)} transport-agnostic metadata features.")

    # 1. WP10: Domains
    dom_csv = OUT_WP10 / "scaling_domains.csv"
    if dom_csv.exists() and not args.force:
        print(f"\n--- Loading existing WP10 domain scaling results from {dom_csv} ---")
        df_dom = pd.read_csv(dom_csv)
    else:
        df_dom = run_wp10_domains(df_v2, features, seeds, permutations, args.workers)
        df_dom.to_csv(dom_csv, index=False)
        plot_wp10_domains(df_dom, OUT_WP10 / "scaling_domains.png")

    # 2. WP10: Repeats
    rep_csv = OUT_WP10 / "scaling_repeats.csv"
    if rep_csv.exists() and not args.force:
        print(f"\n--- Loading existing WP10 repeat scaling results from {rep_csv} ---")
        df_rep = pd.read_csv(rep_csv)
    else:
        df_rep = run_wp10_repeats(df_v2, features, seeds, permutations, args.workers)
        df_rep.to_csv(rep_csv, index=False)
        plot_wp10_repeats(df_rep, OUT_WP10 / "scaling_repeats.png")

    # 3. WP11: Time Stability
    df_stab = run_wp11_time_stability(df_v2, df_pilot, features, seeds, permutations, args.workers)
    df_stab.to_csv(OUT_WP11 / "time_stability.csv", index=False)
    plot_wp11_stability(df_stab, OUT_WP11 / "time_stability.png")

    print("\n✅ WP10 & WP11 Analysis Complete!")


if __name__ == "__main__":
    main()
