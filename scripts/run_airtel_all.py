#!/usr/bin/env python3
"""
run_airtel_all.py — Master runner for all 6 Airtel work-package tasks.

Work packages covered
─────────────────────
  WP7   Richer packet-size n-grams and post-handshake n-grams vs baseline
  WP8   CNN / GRU sequence models  (requires torch; skipped if unavailable)
  WP9   Open-world monitored-vs-unmonitored evaluation
  WP10  Accuracy-vs-domain-count and accuracy-vs-repeat scaling curves
  WP11  Time-stability: pilot repeats (0-7) → T0 repeats (8-19) transfer
  WP13  Padding and delay defence simulations (clearly labelled as simulated)

Usage
─────
  python3 scripts/run_airtel_all.py               # full run, all WPs
  python3 scripts/run_airtel_all.py --quick       # smoke-test (fast)
  python3 scripts/run_airtel_all.py --skip wp8    # skip one or more WPs
  python3 scripts/run_airtel_all.py --only wp10 wp11

Outputs
───────
  results/airtel_all_<DATE>/
    wp7_feature_comparison.csv
    wp7_notes.txt
    wp8_sequence_models.csv        (or wp8_skipped.txt if torch absent)
    wp9_open_world.csv
    wp10_scaling_curves.csv
    wp10_scaling_curves.png
    wp11_time_stability.csv
    wp13_defence_simulations.csv
    wp13_notes.txt
    SUMMARY.md
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

warnings.filterwarnings("ignore")

# ── constants ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]

BASE_FEATURES = [
    "n_pkts", "n_up", "n_down", "bytes_up", "bytes_down", "bytes_total",
    "ratio_bytes_down_up", "duration", "up_mean", "up_std", "up_max",
    "down_mean", "down_std", "down_max", "iat_mean", "iat_std",
    "iat_median", "iat_max", "t_first_down", "n_bursts",
    "burst_len_mean", "burst_len_max", "burst_bytes_mean", "burst_bytes_max",
    *[f"pkt_{i:02d}" for i in range(20)],
]
SEEDS = (17, 42, 101)


# ── shared helpers ────────────────────────────────────────────────────────────
def _rf(seed: int, n_estimators: int = 100) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=n_estimators,
        class_weight="balanced_subsample",
        random_state=seed,
        n_jobs=1,
    )


def _split_train_test(group: pd.DataFrame, repeats: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_reps, test_reps = repeats[:-2], repeats[-2:]
    return group[group["repeat"].isin(train_reps)], group[group["repeat"].isin(test_reps)]


def _score(model, train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> float:
    if train.empty or test.empty or train["domain"].nunique() < 2:
        return float("nan")
    model.fit(train[features], train["domain"])
    return float(accuracy_score(test["domain"], model.predict(test[features])))


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def _load_dataset(path: Path, repeat_range: tuple[int, int]) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["repeat"] = pd.to_numeric(df["repeat"], errors="coerce")
    df = df.dropna(subset=BASE_FEATURES + ["domain", "repeat", "network"])
    df = df[df["network"].eq("airtel") & df["repeat"].between(*repeat_range)]
    return df


def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_no data_\n"
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = "\n".join(
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in df.itertuples(index=False)
    )
    return "\n".join([header, sep, rows]) + "\n"


# ── WP7: richer features ──────────────────────────────────────────────────────
def _bucket(value: float) -> str:
    mag = abs(value)
    for threshold, label in ((64, "64"), (128, "128"), (256, "256"),
                             (512, "512"), (1024, "1k"), (1500, "1500")):
        if mag <= threshold:
            return ("u" if value >= 0 else "d") + label
    return ("u" if value >= 0 else "d") + "1501+"


def _add_ngram_features(df: pd.DataFrame, start: int) -> pd.DataFrame:
    cols = [f"pkt_{i:02d}" for i in range(start, 20)]
    tokens = df[cols].fillna(0).map(_bucket)
    out = df.copy()
    for width in (2, 3):
        out[f"seq_{start}_gram_{width}"] = [
            " ".join("|".join(row[i: i + width]) for i in range(len(row) - width + 1))
            for row in tokens.to_numpy()
        ]
    return out


def _encode_ngrams(df: pd.DataFrame, columns: list[str]) -> np.ndarray:
    vocab = sorted({
        tok
        for col in columns
        for val in df[col]
        for tok in str(val).split()
    })
    idx = {t: i for i, t in enumerate(vocab)}
    mat = np.zeros((len(df), len(vocab)), dtype=np.float32)
    for ri, row in enumerate(df[columns].itertuples(index=False, name=None)):
        for val in row:
            for tok in str(val).split():
                mat[ri, idx[tok]] += 1
    return mat


def _wp7_score(group: pd.DataFrame, features, seed: int, repeats: list[int]) -> float:
    train_reps, test_reps = repeats[:-2], repeats[-2:]
    train_mask = group["repeat"].isin(train_reps)
    test_mask = group["repeat"].isin(test_reps)
    if isinstance(features, np.ndarray):
        X_train, X_test = features[train_mask.to_numpy()], features[test_mask.to_numpy()]
        y_train = group.loc[train_mask, "domain"].to_numpy()
        y_test = group.loc[test_mask, "domain"].to_numpy()
    else:
        train_df = group[train_mask]
        test_df = group[test_mask]
        X_train = train_df[features].to_numpy(float)
        X_test = test_df[features].to_numpy(float)
        y_train = train_df["domain"].to_numpy()
        y_test = test_df["domain"].to_numpy()
    if len(y_train) == 0 or len(y_test) == 0:
        return float("nan")
    model = _rf(seed)
    model.fit(X_train, y_train)
    return float(accuracy_score(y_test, model.predict(X_test)))


def run_wp7(df: pd.DataFrame, out: Path, quick: bool) -> pd.DataFrame:
    print("  [WP7] packet-size n-grams and post-handshake n-grams vs baseline")
    repeats = list(range(8, 8 + (4 if quick else 10)))
    rows = []
    for (workload, resolver, protocol), group in df.groupby(["workload", "resolver", "protocol"]):
        group = group[group["repeat"].isin(repeats)].copy()
        counts = group.groupby("domain")["repeat"].nunique()
        domains = sorted(counts[counts >= len(repeats)].index)
        if len(domains) < 5:
            continue
        group = group[group["domain"].isin(domains)].reset_index(drop=True)
        group = _add_ngram_features(group, 0)
        group = _add_ngram_features(group, 5)
        for name, feat_arg in (
            ("base", BASE_FEATURES),
            ("packet_size_ngrams", None),
            ("post_handshake_ngrams", None),
        ):
            if name == "base":
                encoded = BASE_FEATURES
            elif name == "packet_size_ngrams":
                encoded = _encode_ngrams(group, ["seq_0_gram_2", "seq_0_gram_3"])
            else:
                encoded = _encode_ngrams(group, ["seq_5_gram_2", "seq_5_gram_3"])
            scores = [_wp7_score(group, encoded, seed, repeats) for seed in SEEDS]
            rows.append({
                "workload": workload, "resolver": resolver, "protocol": protocol,
                "feature_set": name,
                "accuracy": round(float(np.nanmean(scores)), 4),
                "accuracy_seed_sd": round(float(np.nanstd(scores)), 4),
                "domains": len(domains),
                "repeats_per_domain": len(repeats),
            })
    result = pd.DataFrame(rows)
    result.to_csv(out / "wp7_feature_comparison.csv", index=False)
    (out / "wp7_notes.txt").write_text(
        "WP7: Packet-size and post-handshake n-grams computed from signed "
        "packet-size sequences (pkt_00..pkt_19).\n"
        "Burst n-grams are NOT reported because the processed feature table "
        "stores burst aggregates rather than the original burst sequences. "
        "Extracting burst n-grams would require re-processing raw PCAPs.\n",
        encoding="utf-8",
    )
    print(f"     → {len(result)} rows written to {out / 'wp7_feature_comparison.csv'}")
    return result


# ── WP8: CNN / GRU sequence models ───────────────────────────────────────────
def run_wp8(df: pd.DataFrame, out: Path, quick: bool) -> pd.DataFrame:
    print("  [WP8] CNN / GRU sequence models")
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
        HAVE_TORCH = True
    except ImportError:
        HAVE_TORCH = False

    if not HAVE_TORCH:
        msg = (
            "PyTorch is not installed. Install it with:\n"
            "  pip3 install torch --index-url https://download.pytorch.org/whl/cpu\n"
            "Then re-run this script to generate WP8 results.\n"
        )
        (out / "wp8_skipped.txt").write_text(msg, encoding="utf-8")
        print("     ⚠  torch not found — WP8 skipped. See wp8_skipped.txt.")
        return pd.DataFrame()

    # ── sequence features: pkt_00..pkt_19 (signed byte sizes) ────────────────
    SEQ_COLS = [f"pkt_{i:02d}" for i in range(20)]
    EPOCHS = 5 if quick else 20
    BATCH = 64

    class CNNModel(nn.Module):
        def __init__(self, n_classes: int):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, 32, kernel_size=3, padding=1), nn.ReLU(),
                nn.Conv1d(32, 64, kernel_size=3, padding=1), nn.ReLU(),
                nn.AdaptiveMaxPool1d(1),
            )
            self.fc = nn.Linear(64, n_classes)

        def forward(self, x):  # x: (B, 20)
            x = x.unsqueeze(1)           # (B, 1, 20)
            x = self.conv(x).squeeze(-1) # (B, 64)
            return self.fc(x)

    class GRUModel(nn.Module):
        def __init__(self, n_classes: int):
            super().__init__()
            self.gru = nn.GRU(1, 64, batch_first=True, num_layers=2)
            self.fc = nn.Linear(64, n_classes)

        def forward(self, x):
            x = x.unsqueeze(-1)              # (B, 20, 1)
            _, h = self.gru(x)               # h: (2, B, 64)
            return self.fc(h[-1])

    def train_eval(X_tr, y_tr, X_te, y_te, ModelClass, n_classes, device):
        X_tr_t = torch.tensor(X_tr, dtype=torch.float32).to(device)
        y_tr_t = torch.tensor(y_tr, dtype=torch.long).to(device)
        X_te_t = torch.tensor(X_te, dtype=torch.float32).to(device)
        ds = TensorDataset(X_tr_t, y_tr_t)
        dl = DataLoader(ds, batch_size=BATCH, shuffle=True)
        model = ModelClass(n_classes).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        criterion = nn.CrossEntropyLoss()
        model.train()
        for _ in range(EPOCHS):
            for xb, yb in dl:
                opt.zero_grad()
                criterion(model(xb), yb).backward()
                opt.step()
        model.eval()
        with torch.no_grad():
            preds = model(X_te_t).argmax(dim=1).cpu().numpy()
        return float((preds == y_te).mean())

    device = torch.device("cpu")
    repeats = list(range(8, 8 + (4 if quick else 10)))
    rows = []

    for (workload, resolver, protocol), group in df.groupby(["workload", "resolver", "protocol"]):
        group = group[group["repeat"].isin(repeats)].copy()
        counts = group.groupby("domain")["repeat"].nunique()
        domains = sorted(counts[counts >= len(repeats)].index)
        if len(domains) < 5:
            continue
        group = group[group["domain"].isin(domains)].reset_index(drop=True)
        label_map = {d: i for i, d in enumerate(domains)}
        y_all = group["domain"].map(label_map).to_numpy()
        X_all = group[SEQ_COLS].fillna(0).to_numpy(float)
        # normalise per-sequence
        X_all = (X_all - X_all.mean(axis=1, keepdims=True)) / (X_all.std(axis=1, keepdims=True) + 1e-6)

        train_mask = group["repeat"].isin(repeats[:-2]).to_numpy()
        test_mask  = group["repeat"].isin(repeats[-2:]).to_numpy()
        if train_mask.sum() < 2 or test_mask.sum() < 2:
            continue
        n_classes = len(domains)

        for model_name, ModelClass in (("cnn", CNNModel), ("gru", GRUModel)):
            seed_scores = []
            for seed in SEEDS:
                torch.manual_seed(seed)
                acc = train_eval(
                    X_all[train_mask], y_all[train_mask],
                    X_all[test_mask],  y_all[test_mask],
                    ModelClass, n_classes, device,
                )
                seed_scores.append(acc)
            rows.append({
                "workload": workload, "resolver": resolver, "protocol": protocol,
                "model": model_name,
                "accuracy": round(float(np.nanmean(seed_scores)), 4),
                "accuracy_seed_sd": round(float(np.nanstd(seed_scores)), 4),
                "domains": n_classes,
                "epochs": EPOCHS,
                "note": "CPU-only; sequence = pkt_00..pkt_19 normalised per-sample",
            })

    result = pd.DataFrame(rows)
    result.to_csv(out / "wp8_sequence_models.csv", index=False)
    print(f"     → {len(result)} rows written to {out / 'wp8_sequence_models.csv'}")
    return result


# ── WP9: open-world evaluation ────────────────────────────────────────────────
def run_wp9(df: pd.DataFrame, out: Path, quick: bool) -> pd.DataFrame:
    """
    Open-world: treat top-N domains as *monitored*, rest as *unmonitored*.
    Classifier trained on monitored domains; unmonitored samples must be
    rejected (predicted as "unknown").  Metric: TPR @ FPR = 5 %.
    """
    print("  [WP9] open-world monitored-vs-unmonitored evaluation")
    repeats = list(range(8, 8 + (4 if quick else 10)))
    monitored_counts = [10, 25, 50] if quick else [10, 25, 50, 75, 100]
    rows = []

    for (workload, resolver, protocol), group in df.groupby(["workload", "resolver", "protocol"]):
        group = group[group["repeat"].isin(repeats)].copy()
        counts = group.groupby("domain")["repeat"].nunique()
        eligible = sorted(counts[counts >= len(repeats)].index)
        if len(eligible) < 10:
            continue

        rng = np.random.default_rng(42)
        all_domains = np.array(eligible)

        for n_mon in monitored_counts:
            if n_mon > len(all_domains):
                continue
            # deterministic split
            monitored = set(rng.choice(all_domains, size=n_mon, replace=False).tolist())
            unmonitored = set(all_domains) - monitored

            mon_df  = group[group["domain"].isin(monitored)]
            unmon_df = group[group["domain"].isin(unmonitored)]

            if mon_df.empty or unmon_df.empty:
                continue

            train_mon = mon_df[mon_df["repeat"].isin(repeats[:-2])]
            test_mon  = mon_df[mon_df["repeat"].isin(repeats[-2:])]

            if train_mon["domain"].nunique() < 2:
                continue

            for seed in SEEDS:
                model = _rf(seed)
                model.fit(train_mon[BASE_FEATURES], train_mon["domain"])

                # probabilities for monitored test set
                proba_mon  = model.predict_proba(test_mon[BASE_FEATURES].to_numpy(float))
                conf_mon   = proba_mon.max(axis=1)   # confidence = max class prob

                # probabilities for unmonitored set (all repeats → more samples)
                proba_unmon = model.predict_proba(unmon_df[BASE_FEATURES].to_numpy(float))
                conf_unmon  = proba_unmon.max(axis=1)

                # TPR @ FPR ≤ 5 %: threshold set so ≤5% of unmonitored pass
                threshold = float(np.percentile(conf_unmon, 95))
                tpr = float((conf_mon >= threshold).mean())
                fpr = float((conf_unmon >= threshold).mean())

                # closed-world accuracy on monitored set (above threshold only)
                above = test_mon[BASE_FEATURES].to_numpy(float)[conf_mon >= threshold]
                y_above = test_mon["domain"].to_numpy()[conf_mon >= threshold]
                closed_acc = float(np.nan)
                if len(above) > 0:
                    preds_above = model.predict(above)
                    closed_acc = float(accuracy_score(y_above, preds_above))

                rows.append({
                    "workload": workload, "resolver": resolver, "protocol": protocol,
                    "n_monitored": n_mon,
                    "n_unmonitored": len(unmonitored),
                    "seed": seed,
                    "threshold": round(threshold, 4),
                    "tpr_at_fpr5": round(tpr, 4),
                    "actual_fpr": round(fpr, 4),
                    "closed_world_acc": round(closed_acc, 4),
                })

    result = pd.DataFrame(rows)
    if not result.empty:
        # aggregate over seeds
        agg = (
            result.groupby(["workload", "resolver", "protocol", "n_monitored"])
            .agg(
                n_unmonitored=("n_unmonitored", "first"),
                tpr_at_fpr5_mean=("tpr_at_fpr5", "mean"),
                tpr_at_fpr5_sd=("tpr_at_fpr5", "std"),
                actual_fpr_mean=("actual_fpr", "mean"),
                closed_world_acc_mean=("closed_world_acc", "mean"),
            )
            .round(4)
            .reset_index()
        )
        agg.to_csv(out / "wp9_open_world.csv", index=False)
        print(f"     → {len(agg)} rows written to {out / 'wp9_open_world.csv'}")
    else:
        (out / "wp9_open_world.csv").write_text("workload,resolver,protocol,n_monitored,note\n")
        print("     ⚠  no eligible slices for WP9")
    return result


# ── WP10: scaling curves ──────────────────────────────────────────────────────
def run_wp10(df: pd.DataFrame, out: Path, quick: bool) -> pd.DataFrame:
    print("  [WP10] accuracy-vs-domain-count and accuracy-vs-repeat scaling")
    repeat_counts = [4, 6] if quick else [4, 6, 8, 10]
    domain_counts = [10, 25] if quick else [10, 25, 50, 75, 100]
    rows = []

    for (workload, resolver, protocol), group in df.groupby(["workload", "resolver", "protocol"]):
        for repeat_count in repeat_counts:
            repeats = list(range(8, 8 + repeat_count))
            for domain_count in domain_counts:
                # choose domains reproducibly
                rng = np.random.default_rng(17)
                counts = (
                    group[group["repeat"].isin(repeats)]
                    .groupby("domain")["repeat"].nunique()
                )
                eligible = sorted(counts[counts >= repeat_count].index)
                if len(eligible) < domain_count:
                    continue
                domains = sorted(rng.choice(eligible, size=domain_count, replace=False).tolist())
                sub = group[group["domain"].isin(domains) & group["repeat"].isin(repeats)]
                train, test = _split_train_test(sub, repeats)
                if train.empty or test.empty:
                    continue
                scores = [_score(_rf(s), train, test, BASE_FEATURES) for s in SEEDS]
                rows.append({
                    "workload": workload, "resolver": resolver, "protocol": protocol,
                    "domain_count": domain_count,
                    "repeat_count": repeat_count,
                    "accuracy": round(float(np.nanmean(scores)), 4),
                    "accuracy_seed_sd": round(float(np.nanstd(scores)), 4),
                })

    result = pd.DataFrame(rows)
    result.to_csv(out / "wp10_scaling_curves.csv", index=False)

    # ── plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    if not result.empty:
        for (wl, res, proto), grp in result.groupby(["workload", "resolver", "protocol"]):
            label = f"{wl}/{res}/{proto}"
            by_dom = grp.groupby("domain_count")["accuracy"].mean()
            by_rep = grp.groupby("repeat_count")["accuracy"].mean()
            axes[0].plot(by_dom.index, by_dom.values, marker="o", label=label)
            axes[1].plot(by_rep.index, by_rep.values, marker="o", label=label)
    for ax, xlabel, title in (
        (axes[0], "Number of monitored domains", "Accuracy vs. domain count"),
        (axes[1], "Successful repeats per domain", "Accuracy vs. repeat count"),
    ):
        ax.set(xlabel=xlabel, ylabel="Accuracy", title=title, ylim=(0, 1))
        ax.legend(fontsize=5, ncol=2)
        ax.grid(True, alpha=0.3)
    fig.savefig(out / "wp10_scaling_curves.png", dpi=160)
    plt.close(fig)
    print(f"     → {len(result)} rows + plot written to {out / 'wp10_scaling_curves.csv'}")
    return result


# ── WP11: time stability ──────────────────────────────────────────────────────
def run_wp11(pilot: pd.DataFrame, t0: pd.DataFrame, out: Path) -> pd.DataFrame:
    print("  [WP11] time-stability: pilot (repeats 0-7) → T0 (repeats 8-19)")
    rows = []
    for (workload, resolver, protocol), test in t0.groupby(["workload", "resolver", "protocol"]):
        train = pilot[
            (pilot["workload"] == workload)
            & (pilot["resolver"] == resolver)
            & (pilot["protocol"] == protocol)
        ]
        common = set(train["domain"]) & set(test["domain"])
        train_c = train[train["domain"].isin(common)]
        test_c  = test[test["domain"].isin(common)]
        if len(common) < 5 or train_c.empty or test_c.empty:
            continue
        scores = []
        for seed in SEEDS:
            model = _rf(seed)
            model.fit(train_c[BASE_FEATURES], train_c["domain"])
            pred = model.predict(test_c[BASE_FEATURES])
            scores.append(float(accuracy_score(test_c["domain"], pred)))
        mean_acc = float(np.mean(scores))
        ci_lo, ci_hi = _wilson(int(round(mean_acc * len(test_c))), len(test_c))
        rows.append({
            "workload": workload, "resolver": resolver, "protocol": protocol,
            "train_repeats": "0-7 (pilot)",
            "test_repeats": "8-19 (T0)",
            "domains": len(common),
            "n_train": len(train_c),
            "n_test": len(test_c),
            "accuracy": round(mean_acc, 4),
            "accuracy_seed_sd": round(float(np.std(scores)), 4),
            "ci_lo": round(ci_lo, 4),
            "ci_hi": round(ci_hi, 4),
        })
    result = pd.DataFrame(rows)
    result.to_csv(out / "wp11_time_stability.csv", index=False)
    print(f"     → {len(result)} rows written to {out / 'wp11_time_stability.csv'}")
    return result


# ── WP13: defence simulations ─────────────────────────────────────────────────
def run_wp13(df: pd.DataFrame, out: Path, quick: bool) -> pd.DataFrame:
    """
    Simulated defences applied to the feature vectors (not PCAPs).
    All results are clearly labelled SIMULATED.

    Defences implemented:
      P1  Constant-rate padding:  round every packet size to the next multiple
          of `block` bytes.  Applied to pkt_00..pkt_19 and size stats.
      P2  Random padding:        add uniform noise U[0, max_add] to each packet.
      D1  Packet delay jitter:   add U[0, max_jitter] to iat_mean / iat_std.
      D2  Constant-rate cover traffic: inject a fixed number of dummy packets
          (adds to n_pkts, bytes_total).
    """
    print("  [WP13] defence simulations (SIMULATED — not measured on network)")
    repeats = list(range(8, 8 + (4 if quick else 10)))
    rows = []

    def _apply_padding_constant(sub: pd.DataFrame, block: int) -> pd.DataFrame:
        d = sub.copy()
        for col in [f"pkt_{i:02d}" for i in range(20)]:
            d[col] = np.sign(d[col]) * (np.ceil(np.abs(d[col]) / block) * block)
        for col in ["up_mean", "up_max", "down_mean", "down_max"]:
            if col in d.columns:
                d[col] = np.ceil(np.abs(d[col]) / block) * block * np.sign(d[col] if col.startswith("up") else -1)
        return d

    def _apply_padding_random(sub: pd.DataFrame, max_add: int, rng) -> pd.DataFrame:
        d = sub.copy()
        noise = rng.integers(0, max_add + 1, size=(len(d), 20))
        for i, col in enumerate(f"pkt_{j:02d}" for j in range(20)):
            d[col] = d[col] + np.sign(d[col].fillna(0)) * noise[:, i]
        return d

    def _apply_delay_jitter(sub: pd.DataFrame, max_jitter: float, rng) -> pd.DataFrame:
        d = sub.copy()
        n = len(d)
        d["iat_mean"] = d["iat_mean"] + rng.uniform(0, max_jitter, n)
        d["iat_std"]  = d["iat_std"]  + rng.uniform(0, max_jitter / 2, n)
        d["iat_max"]  = d["iat_max"]  + rng.uniform(0, max_jitter * 2, n)
        d["duration"] = d["duration"] + rng.uniform(0, max_jitter, n)
        return d

    def _apply_cover_traffic(sub: pd.DataFrame, dummy_pkts: int, dummy_bytes_each: int) -> pd.DataFrame:
        d = sub.copy()
        d["n_pkts"]      = d["n_pkts"]      + dummy_pkts
        d["n_up"]        = d["n_up"]        + dummy_pkts // 2
        d["n_down"]      = d["n_down"]      + dummy_pkts // 2
        d["bytes_total"] = d["bytes_total"] + dummy_pkts * dummy_bytes_each
        d["bytes_up"]    = d["bytes_up"]    + (dummy_pkts // 2) * dummy_bytes_each
        d["bytes_down"]  = d["bytes_down"]  + (dummy_pkts // 2) * dummy_bytes_each
        return d

    defences = [
        ("no_defence",        lambda d, rng: d),
        ("pad_constant_64",   lambda d, rng: _apply_padding_constant(d, 64)),
        ("pad_constant_128",  lambda d, rng: _apply_padding_constant(d, 128)),
        ("pad_random_128",    lambda d, rng: _apply_padding_random(d, 128, rng)),
        ("jitter_50ms",       lambda d, rng: _apply_delay_jitter(d, 0.050, rng)),
        ("jitter_200ms",      lambda d, rng: _apply_delay_jitter(d, 0.200, rng)),
        ("cover_10pkts",      lambda d, rng: _apply_cover_traffic(d, 10, 500)),
        ("cover_50pkts",      lambda d, rng: _apply_cover_traffic(d, 50, 500)),
    ]

    for (workload, resolver, protocol), group in df.groupby(["workload", "resolver", "protocol"]):
        group = group[group["repeat"].isin(repeats)].copy()
        counts = group.groupby("domain")["repeat"].nunique()
        domains = sorted(counts[counts >= len(repeats)].index)
        if len(domains) < 5:
            continue
        group = group[group["domain"].isin(domains)].reset_index(drop=True)

        train_base, test_base = _split_train_test(group, repeats)
        if train_base.empty or test_base.empty:
            continue

        for defence_name, transform in defences:
            seed_scores = []
            for seed in SEEDS:
                rng = np.random.default_rng(seed)
                train_d = transform(train_base, rng)
                test_d  = transform(test_base,  rng)
                acc = _score(_rf(seed), train_d, test_d, BASE_FEATURES)
                seed_scores.append(acc)
            rows.append({
                "workload": workload, "resolver": resolver, "protocol": protocol,
                "defence": defence_name,
                "accuracy": round(float(np.nanmean(seed_scores)), 4),
                "accuracy_seed_sd": round(float(np.nanstd(seed_scores)), 4),
                "domains": len(domains),
                "note": "SIMULATED — feature-vector perturbation, not measured traffic",
            })

    result = pd.DataFrame(rows)
    result.to_csv(out / "wp13_defence_simulations.csv", index=False)
    (out / "wp13_notes.txt").write_text(
        "WP13: Defence simulations.\n\n"
        "All results in wp13_defence_simulations.csv are SIMULATED.\n"
        "Defences are applied by perturbing the already-extracted feature vectors\n"
        "(pkt_* sizes, timing, counts) — not by replaying or modifying PCAPs.\n\n"
        "Defences:\n"
        "  no_defence       : baseline (unmodified)\n"
        "  pad_constant_64  : round each pkt to next multiple of 64 bytes\n"
        "  pad_constant_128 : round each pkt to next multiple of 128 bytes\n"
        "  pad_random_128   : add uniform random noise U[0,128] per packet\n"
        "  jitter_50ms      : add U[0,50ms] jitter to IAT features\n"
        "  jitter_200ms     : add U[0,200ms] jitter to IAT features\n"
        "  cover_10pkts     : inject 10 dummy 500-byte packets per flow\n"
        "  cover_50pkts     : inject 50 dummy 500-byte packets per flow\n",
        encoding="utf-8",
    )
    print(f"     → {len(result)} rows written to {out / 'wp13_defence_simulations.csv'}")
    return result


# ── summary report ────────────────────────────────────────────────────────────
def write_summary(
    out: Path,
    wp7: pd.DataFrame, wp8: pd.DataFrame, wp9: pd.DataFrame,
    wp10: pd.DataFrame, wp11: pd.DataFrame, wp13: pd.DataFrame,
    elapsed: float, skipped: list[str],
) -> None:
    def _head(df, n=6):
        return _md_table(df.head(n)) if not df.empty else "_no data_\n"

    sections = [
        f"# Airtel Analysis — All Work Packages\n\nGenerated: {date.today()}  \n"
        f"Elapsed: {elapsed:.0f}s  \n"
        f"Skipped WPs: {', '.join(skipped) if skipped else 'none'}\n",

        "## WP7 — Feature Comparison (packet-size & post-handshake n-grams)\n\n"
        + _head(wp7)
        + "\n> **Note:** Burst n-grams are not reported (burst sequences not in feature table).\n",

        "## WP8 — CNN/GRU Sequence Models\n\n" + _head(wp8),

        "## WP9 — Open-World Evaluation (monitored vs unmonitored)\n\n"
        + _head(wp9)
        + "\n> TPR @ FPR ≤ 5%. Threshold set on unmonitored confidence scores.\n",

        "## WP10 — Scaling Curves\n\n"
        + _head(wp10)
        + "\n> See wp10_scaling_curves.png for the full plot.\n",

        "## WP11 — Time Stability (pilot → T0)\n\n" + _head(wp11),

        "## WP13 — Defence Simulations (**SIMULATED**)\n\n"
        + _head(wp13)
        + "\n> **All results are simulated** (feature-vector perturbation, not measured traffic).\n",
    ]
    (out / "SUMMARY.md").write_text("\n".join(sections), encoding="utf-8")
    print(f"\n  → Summary written to {out / 'SUMMARY.md'}")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ALL_WPS = ["wp7", "wp8", "wp9", "wp10", "wp11", "wp13"]

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path,
                    default=ROOT / "data" / "processed" / "dataset_v2.csv")
    ap.add_argument("--pilot", type=Path,
                    default=ROOT / "data" / "processed" / "dataset_pilot_v1.csv")
    ap.add_argument("--out", type=Path,
                    default=ROOT / f"results/airtel_all_{date.today().strftime('%Y%m%d')}")
    ap.add_argument("--quick", action="store_true",
                    help="Smoke-test mode: fewer repeats, domains, epochs")
    ap.add_argument("--skip", nargs="+", metavar="WP",
                    choices=ALL_WPS, default=[],
                    help="Work packages to skip, e.g. --skip wp8 wp9")
    ap.add_argument("--only", nargs="+", metavar="WP",
                    choices=ALL_WPS,
                    help="Run only these work packages")
    args = ap.parse_args()

    to_run = set(args.only) if args.only else set(ALL_WPS) - set(args.skip)

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  Airtel All-WP runner  {'[QUICK MODE]' if args.quick else ''}")
    print(f"  Dataset : {args.dataset}")
    print(f"  Output  : {args.out}")
    print(f"  Running : {', '.join(sorted(to_run))}")
    print(f"{'='*60}\n")

    if not args.dataset.exists():
        sys.exit(f"ERROR: dataset not found: {args.dataset}")

    t_start = time.time()

    # load T0 (repeats 8-19)
    t0 = _load_dataset(args.dataset, (8, 19))
    print(f"  T0 dataset: {len(t0):,} rows, "
          f"{t0['domain'].nunique()} domains, "
          f"{t0['network'].value_counts().to_dict()}")

    # load pilot (repeats 0-7) — needed for WP11
    pilot = pd.DataFrame()
    if "wp11" in to_run:
        if not args.pilot.exists():
            print(f"  ⚠  pilot dataset not found ({args.pilot}); skipping WP11")
            to_run.discard("wp11")
        else:
            pilot = _load_dataset(args.pilot, (0, 7))
            print(f"  Pilot dataset: {len(pilot):,} rows, {pilot['domain'].nunique()} domains")

    print()

    skipped_wps: list[str] = [wp for wp in ALL_WPS if wp not in to_run]
    empty = pd.DataFrame()

    wp7  = run_wp7(t0, args.out, args.quick)  if "wp7"  in to_run else empty
    wp8  = run_wp8(t0, args.out, args.quick)  if "wp8"  in to_run else empty
    wp9  = run_wp9(t0, args.out, args.quick)  if "wp9"  in to_run else empty
    wp10 = run_wp10(t0, args.out, args.quick) if "wp10" in to_run else empty
    wp11 = run_wp11(pilot, t0, args.out)      if "wp11" in to_run else empty
    wp13 = run_wp13(t0, args.out, args.quick) if "wp13" in to_run else empty

    elapsed = time.time() - t_start
    write_summary(args.out, wp7, wp8, wp9, wp10, wp11, wp13, elapsed, skipped_wps)

    print(f"\n{'='*60}")
    print(f"  All done in {elapsed:.0f}s")
    print(f"  Results → {args.out}")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
