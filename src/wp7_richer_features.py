"""WP7 — Richer Features: packet-size n-grams, burst n-grams, post-handshake features.

Compares three feature sets against the baseline (original 39 features):
  - BASE:        Original 39 features (volume, size stats, timing, bursts, first-20 packets)
  - NGRAM:       BASE + packet-size bigrams and trigrams (consecutive signed-size pairs/triples)
  - POST_HS:     Features computed only from packets AFTER the first downstream packet (post-handshake)
  - NGRAM+POST:  All of the above combined

Evaluation follows METHODOLOGY.md exactly:
  - 5 grouped folds, 2 repeats held out per fold (leave-2-repeats-out within each fold)
  - Random Forest, 100 trees, multiple seeds, Wilson CI, 200-permutation empirical p-value
  - Runs first on dataset_pilot_v1.csv then dataset_v2.csv
  - Results written to results/wp7_richer_features/

Usage:
    python src/wp7_richer_features.py           # full run on both datasets
    python src/wp7_richer_features.py --quick   # smoke test (50 permutations, 2 seeds)
"""

from __future__ import annotations

import argparse
import json
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUT  = ROOT / "results" / "wp7_richer_features"

SEEDS  = [7, 42, 99]
FOLDS  = 5
HELD   = 2          # repeats held out per fold as test
N_REAL = 100        # trees for real model
N_NULL = 50         # trees for null/permutation model
N_PERM = 200        # permutation iterations

# ── Existing base feature groups (from extract_features.py / analysis_v2.py) ─
GROUPS_BASE = {
    "volume":     ["n_pkts", "n_up", "n_down", "bytes_up", "bytes_down",
                   "bytes_total", "ratio_bytes_down_up"],
    "size_stats": ["up_mean", "up_std", "up_max", "down_mean", "down_std", "down_max"],
    "timing":     ["duration", "iat_mean", "iat_std", "iat_median", "iat_max", "t_first_down"],
    "bursts":     ["n_bursts", "burst_len_mean", "burst_len_max",
                   "burst_bytes_mean", "burst_bytes_max"],
    "first20":    [f"pkt_{i:02d}" for i in range(20)],
}
FEATS_BASE = [c for cols in GROUPS_BASE.values() for c in cols]


# ─────────────────────────────────────────────────────────────────────────────
# Feature engineering
# ─────────────────────────────────────────────────────────────────────────────

def add_ngram_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add packet-size bigrams and trigrams from the first-20 signed packet sizes."""
    pkt_cols = [f"pkt_{i:02d}" for i in range(20)]
    new_cols = {}

    # Bigrams: (pkt_i, pkt_{i+1}) -> absolute product sign as a combined feature
    for i in range(len(pkt_cols) - 1):
        col = f"ng2_{i:02d}_{i+1:02d}"
        new_cols[col] = df[pkt_cols[i]] * df[pkt_cols[i + 1]]

    # Trigrams: sum of three consecutive packet sizes (direction-aware)
    for i in range(len(pkt_cols) - 2):
        col = f"ng3_{i:02d}_{i+2:02d}"
        new_cols[col] = df[pkt_cols[i]] + df[pkt_cols[i + 1]] + df[pkt_cols[i + 2]]

    # Burst n-grams: direction transitions (number of sign changes in first-20)
    signs = df[pkt_cols].apply(np.sign)
    new_cols["n_dir_changes"] = (signs.diff(axis=1).abs() > 0).sum(axis=1)

    # Ratio of post-handshake packets (pkt_05 onwards) vs first 5
    early  = df[[f"pkt_{i:02d}" for i in range(5)]].abs().sum(axis=1)
    late   = df[[f"pkt_{i:02d}" for i in range(5, 20)]].abs().sum(axis=1)
    new_cols["early_late_ratio"] = (late / (early + 1)).round(4)

    return pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)


def add_post_handshake_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Post-handshake features: derived from packets after the first downstream packet.
    'First downstream' is the first pkt_xx with a negative value (server→client).
    Features: post-hs packet count, mean/std/max of post-hs sizes, up/down byte ratio post-hs.
    """
    pkt_cols = [f"pkt_{i:02d}" for i in range(20)]
    new_cols = {}

    pkt_arr = df[pkt_cols].values  # shape (N, 20)

    # Find index of first downstream packet per row
    def first_down_idx(row):
        for i, v in enumerate(row):
            if v < 0:
                return i
        return 20  # no downstream in first 20 → all handshake

    hs_end = np.array([first_down_idx(row) for row in pkt_arr])

    post_sizes = []
    post_up    = []
    post_down  = []
    for i, row in enumerate(pkt_arr):
        idx = hs_end[i]
        post = row[idx:]
        post = post[post != 0]      # strip zero-padding
        post_sizes.append(post)
        post_up.append(post[post > 0])
        post_down.append(post[post < 0])

    new_cols["post_hs_n_pkts"]   = [len(p) for p in post_sizes]
    new_cols["post_hs_mean_size"] = [np.abs(p).mean() if len(p) else 0.0 for p in post_sizes]
    new_cols["post_hs_std_size"]  = [np.abs(p).std()  if len(p) > 1 else 0.0 for p in post_sizes]
    new_cols["post_hs_max_size"]  = [np.abs(p).max()  if len(p) else 0.0 for p in post_sizes]
    new_cols["post_hs_bytes_up"]  = [p.sum() for p in post_up]
    new_cols["post_hs_bytes_down"]= [abs(p.sum()) for p in post_down]
    new_cols["post_hs_down_up_ratio"] = [
        round(abs(d.sum()) / (u.sum() + 1), 4)
        for u, d in zip(post_up, post_down)
    ]
    new_cols["hs_length"] = hs_end.tolist()   # how many packets before first response

    return pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)


def build_feature_sets(df: pd.DataFrame) -> dict[str, list[str]]:
    """Return dict of {set_name: [column_names]} after engineering new features."""
    df = add_ngram_features(df)
    df = add_post_handshake_features(df)

    ngram_cols   = [c for c in df.columns if c.startswith(("ng2_", "ng3_", "n_dir", "early_late"))]
    post_hs_cols = [c for c in df.columns if c.startswith("post_hs") or c == "hs_length"]

    return df, {
        "BASE":       FEATS_BASE,
        "NGRAM":      FEATS_BASE + ngram_cols,
        "POST_HS":    FEATS_BASE + post_hs_cols,
        "NGRAM+POST": FEATS_BASE + ngram_cols + post_hs_cols,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation (mirrors analysis_v2.py evaluation protocol)
# ─────────────────────────────────────────────────────────────────────────────

def wilson_ci(acc: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = acc
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    spread = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return max(0.0, centre - spread), min(1.0, centre + spread)


def leave_k_repeats_out_cv(X: np.ndarray, y: np.ndarray, groups: np.ndarray,
                            seed: int, n_trees: int, held: int = HELD,
                            n_folds: int = FOLDS) -> float:
    """
    Grouped k-fold where groups are repeat indices.
    Splits repeats into n_folds groups; each fold holds out `held` repeats as test.
    """
    unique_repeats = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_repeats)

    # Divide repeats into n_folds chunks
    fold_repeats = np.array_split(unique_repeats, n_folds)
    scores = []
    for fold_idx in range(n_folds):
        test_repeats  = set(fold_repeats[fold_idx][:held])
        test_mask     = np.isin(groups, list(test_repeats))
        train_mask    = ~test_mask
        if train_mask.sum() == 0 or test_mask.sum() == 0:
            continue
        clf = RandomForestClassifier(n_estimators=n_trees, random_state=seed, n_jobs=1)
        clf.fit(X[train_mask], y[train_mask])
        scores.append(accuracy_score(y[test_mask], clf.predict(X[test_mask])))
    return float(np.mean(scores)) if scores else 0.0


def permutation_pvalue(X: np.ndarray, y: np.ndarray, groups: np.ndarray,
                       observed: float, n_perm: int, seed: int,
                       n_trees: int = N_NULL) -> float:
    rng = np.random.default_rng(seed + 1000)
    null_scores = []
    for _ in range(n_perm):
        y_perm = rng.permutation(y)
        null_scores.append(
            leave_k_repeats_out_cv(X, y_perm, groups, seed=int(rng.integers(1e6)),
                                   n_trees=n_trees)
        )
    return float((np.array(null_scores) >= observed).mean() + 1 / (n_perm + 1))


def evaluate_slice(df_slice: pd.DataFrame, feat_cols: list[str],
                   label_col: str, repeat_col: str,
                   seeds: list[int], n_perm: int,
                   quick: bool = False) -> dict:
    """Evaluate one (resolver, protocol, workload) slice on a given feature set."""
    # Drop rows with any NaN in feature columns
    df_slice = df_slice.dropna(subset=feat_cols)
    if len(df_slice) < 20:
        return {"n": len(df_slice), "skipped": True}

    le   = LabelEncoder()
    y    = le.fit_transform(df_slice[label_col].values)
    grp  = df_slice[repeat_col].values
    X    = df_slice[feat_cols].values.astype(np.float64)

    seed_accs = [leave_k_repeats_out_cv(X, y, grp, seed=s,
                                         n_trees=N_REAL if not quick else 20)
                 for s in seeds]
    acc    = float(np.mean(seed_accs))
    acc_sd = float(np.std(seed_accs))
    n      = len(df_slice)
    ci_lo, ci_hi = wilson_ci(acc, n)
    chance = 1.0 / len(np.unique(y))
    p_val  = permutation_pvalue(X, y, grp, acc,
                                n_perm=n_perm if not quick else 50,
                                seed=seeds[0],
                                n_trees=N_NULL if not quick else 10)

    return {
        "n": n, "domains": int(df_slice[label_col].nunique()),
        "accuracy": round(acc, 6), "accuracy_seed_sd": round(acc_sd, 6),
        "ci_low": round(ci_lo, 6), "ci_high": round(ci_hi, 6),
        "chance": round(chance, 6), "p_value": round(p_val, 8),
        "skipped": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def run_wp7(df_raw: pd.DataFrame, dataset_label: str, quick: bool = False) -> list[dict]:
    seeds  = SEEDS[:2] if quick else SEEDS
    n_perm = 50 if quick else N_PERM

    df, feat_sets = build_feature_sets(df_raw.copy())

    # Use only headline repeats (8-19) if available; fall back to all
    headline = df[df["repeat"].isin(range(8, 20))]
    if len(headline) < 100:
        headline = df

    results = []
    slices = [
        (resolver, protocol, workload)
        for resolver  in sorted(headline["resolver"].unique())
        for protocol  in sorted(headline["protocol"].unique())
        for workload  in sorted(headline["workload"].unique())
    ]

    total = len(slices) * len(feat_sets)
    done  = 0
    for resolver, protocol, workload in slices:
        mask = (
            (headline["resolver"]  == resolver) &
            (headline["protocol"]  == protocol) &
            (headline["workload"]  == workload)
        )
        df_slice = headline[mask]
        if len(df_slice) < 20:
            continue

        for feat_name, feat_cols in feat_sets.items():
            # Only keep columns that actually exist in this df
            valid_cols = [c for c in feat_cols if c in df.columns]
            done += 1
            print(f"  [{done}/{total}] {dataset_label} | {resolver}/{protocol}/{workload} | {feat_name} "
                  f"({len(valid_cols)} feats)", flush=True)

            res = evaluate_slice(df_slice, valid_cols, "domain", "repeat",
                                 seeds=seeds, n_perm=n_perm, quick=quick)
            results.append({
                "dataset":   dataset_label,
                "resolver":  resolver,
                "protocol":  protocol,
                "workload":  workload,
                "feat_set":  feat_name,
                "n_features": len(valid_cols),
                **res,
            })

    return results


def summarise(results: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(results)
    if df.empty:
        return df
    df = df[~df.get("skipped", False)]
    return df.sort_values(["dataset", "resolver", "protocol", "workload", "feat_set"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true",
                    help="Smoke test: fewer permutations, fewer seeds, fewer trees")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    all_results = []
    for csv_name, label in [
        ("dataset_pilot_v1.csv", "pilot"),
        ("dataset_v2.csv",       "final"),
    ]:
        path = DATA / csv_name
        if not path.exists():
            print(f"  Skipping {csv_name} — file not found")
            continue
        print(f"\n{'='*60}")
        print(f" Dataset: {label}  ({csv_name})")
        print(f"{'='*60}")
        df_raw = pd.read_csv(path)
        all_results.extend(run_wp7(df_raw, label, quick=args.quick))

    df_out = summarise(all_results)
    out_csv = OUT / "wp7_results.csv"
    df_out.to_csv(out_csv, index=False)
    print(f"\nWrote {len(df_out)} rows → {out_csv}")

    # ── Summary table: BASE vs NGRAM+POST per dataset ──────────────────────
    print("\n── WP7 Summary: accuracy by feature set (mean across slices) ──")
    if not df_out.empty:
        pivot = (
            df_out.groupby(["dataset", "feat_set"])["accuracy"]
            .agg(["mean", "std", "count"])
            .round(4)
        )
        print(pivot.to_string())

    # ── Save summary JSON ───────────────────────────────────────────────────
    summary = {}
    if not df_out.empty:
        for (ds, fs), grp in df_out.groupby(["dataset", "feat_set"]):
            summary.setdefault(ds, {})[fs] = {
                "mean_accuracy": round(grp["accuracy"].mean(), 6),
                "std_accuracy":  round(grp["accuracy"].std(), 6),
                "n_slices":      int(len(grp)),
                "sig_slices":    int((grp["p_value"] < 0.05).sum()),
            }
    (OUT / "wp7_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Summary JSON → {OUT / 'wp7_summary.json'}")


if __name__ == "__main__":
    main()
