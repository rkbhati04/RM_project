"""KU5 — WP8 Deep Learning (1D-CNN & GRU), WP9 Open-World, and WP13 Defense Simulations.

This module addresses the three advanced modeling and security evaluation tasks:
  1. WP8: Sequential Deep Learning (1D-CNN and Bidirectional GRU) on raw signed packet sizes,
     benchmarked honestly against Random Forest under the identical 5-fold repeat-held-out protocol.
  2. WP9: Open-World Fingerprinting (Monitored vs Unmonitored domains), computing
     Precision-Recall and ROC curves to evaluate resistance to open-world eavesdropping.
  3. WP13: Countermeasure Defense What-If Simulations (RFC 8467 128-byte & 468-byte padding,
     and random timing jitter), explicitly labelled as simulations per project ethics.

Outputs:
  - results/wp8_deep_learning/wp8_models.csv & wp8_comparison.png
  - results/wp9_open_world/open_world_curves.csv & open_world_pr_curves.png
  - results/wp13_defenses/defense_simulations.csv & defense_ablation.png

Usage:
    PYTHONPATH=src python src/ku5_deep_learning_openworld_defenses.py           # full run
    PYTHONPATH=src python src/ku5_deep_learning_openworld_defenses.py --quick   # fast run
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
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_recall_curve, roc_curve, auc
from sklearn.preprocessing import LabelEncoder

from encdns.analysis.fingerprinting import available_features, select_headline_repeats
from encdns.analysis.stats import wilson_interval

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "dataset_v2.csv"
OUT_WP8 = ROOT / "results" / "wp8_deep_learning"
OUT_WP9 = ROOT / "results" / "wp9_open_world"
OUT_WP13 = ROOT / "results" / "wp13_defenses"

DEVICE = torch.device("cpu")
PKT_COLS = [f"pkt_{i:02d}" for i in range(20)]


# =============================================================================
# WP8: Neural Network Architectures
# =============================================================================

class PacketCNN1D(nn.Module):
    """1D-CNN for sequential packet sizes."""
    def __init__(self, num_classes: int, seq_len: int = 20):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 32, kernel_size=3, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(2)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(64, num_classes)

    def forward(self, x):
        # x: (batch, 1, seq_len)
        x = self.pool1(self.relu1(self.conv1(x)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = x.squeeze(-1)
        x = self.dropout(x)
        return self.fc(x)


class PacketGRU(nn.Module):
    """Bidirectional GRU for sequential packet dynamics."""
    def __init__(self, num_classes: int, seq_len: int = 20, hidden_dim: int = 48):
        super().__init__()
        self.gru = nn.GRU(1, hidden_dim, batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)

    def forward(self, x):
        # x: (batch, seq_len, 1)
        out, _ = self.gru(x)
        # Average pooling across time
        pooled = out.mean(dim=1)
        pooled = self.dropout(pooled)
        return self.fc(pooled)


def train_eval_torch_model(
    model_type: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    num_classes: int,
    epochs: int = 25,
    batch_size: int = 32,
    lr: float = 0.003,
) -> tuple[float, float, list[int], list[int]]:
    """Trains a PyTorch sequence model and returns accuracy and predictions."""
    torch.manual_seed(42)

    # Normalize packet sizes to [-1.0, 1.0]
    train_norm = np.clip(train_x / 1500.0, -1.0, 1.0).astype(np.float32)
    test_norm = np.clip(test_x / 1500.0, -1.0, 1.0).astype(np.float32)

    if model_type == "cnn":
        # Shape: (N, 1, 20)
        train_t = torch.tensor(train_norm).unsqueeze(1)
        test_t = torch.tensor(test_norm).unsqueeze(1)
        model = PacketCNN1D(num_classes)
    else:  # gru
        # Shape: (N, 20, 1)
        train_t = torch.tensor(train_norm).unsqueeze(-1)
        test_t = torch.tensor(test_norm).unsqueeze(-1)
        model = PacketGRU(num_classes)

    labels_t = torch.tensor(train_y, dtype=torch.long)
    dataset = TensorDataset(train_t, labels_t)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for _ in range(epochs):
        for bx, by in loader:
            optimizer.zero_grad()
            out = model(bx)
            loss = criterion(out, by)
            loss.backward()
            optimizer.step()

    model.eval()
    with torch.no_grad():
        logits = model(test_t)
        preds = logits.argmax(dim=1).numpy()

    acc = float(accuracy_score(test_y, preds))
    macro_f1 = float(f1_score(test_y, preds, average="macro"))
    return acc, macro_f1, test_y.tolist(), preds.tolist()


def evaluate_wp8_models(df: pd.DataFrame, quick: bool = False) -> pd.DataFrame:
    print("\n--- Running WP8: 1D-CNN, GRU, and Random Forest on Signed Packet Sequences ---")
    records = []
    epochs = 15 if quick else 30

    # Test key slices: AdGuard, Google, Quad9 on DoH and DoH/3
    slices = [
        ("adguard", "doh", "global"),
        ("adguard", "doh3", "global"),
        ("google", "doh", "global"),
        ("google", "doh3", "global"),
        ("quad9", "doh", "global"),
        ("quad9", "doh3", "global"),
    ]

    for resolver, protocol, workload in slices:
        sub = df[(df["resolver"] == resolver) & (df["protocol"] == protocol) & (df["workload"] == workload)]
        sampled, _ = select_headline_repeats(sub, 8, 19, target_k=10)
        if sampled.empty or sampled["domain"].nunique() < 10:
            continue

        le = LabelEncoder()
        y_all = le.fit_transform(sampled["domain"].values)
        num_classes = len(le.classes_)
        repeats = sorted(sampled["repeat"].unique())
        folds = [repeats[i:i + 2] for i in range(0, len(repeats), 2)]

        # Prepare evaluation across folds
        rf_accs, cnn_accs, gru_accs = [], [], []

        for held_out in folds:
            train_mask = ~sampled["repeat"].isin(held_out)
            test_mask = sampled["repeat"].isin(held_out)

            train_seq = sampled.loc[train_mask, PKT_COLS].to_numpy(float)
            test_seq = sampled.loc[test_mask, PKT_COLS].to_numpy(float)
            y_tr, y_te = y_all[train_mask], y_all[test_mask]

            # 1. Random Forest (on same packet sequence features)
            rf = RandomForestClassifier(n_estimators=50 if quick else 100, random_state=42, n_jobs=1)
            rf.fit(train_seq, y_tr)
            rf_pred = rf.predict(test_seq)
            rf_accs.append(accuracy_score(y_te, rf_pred))

            # 2. 1D-CNN
            cnn_acc, _, _, _ = train_eval_torch_model("cnn", train_seq, y_tr, test_seq, y_te, num_classes, epochs=epochs)
            cnn_accs.append(cnn_acc)

            # 3. GRU
            gru_acc, _, _, _ = train_eval_torch_model("gru", train_seq, y_tr, test_seq, y_te, num_classes, epochs=epochs)
            gru_accs.append(gru_acc)

        rf_mean = float(np.mean(rf_accs))
        cnn_mean = float(np.mean(cnn_accs))
        gru_mean = float(np.mean(gru_accs))

        # Wilson intervals on total test samples
        n_total = len(sampled)
        rf_ci = wilson_interval(int(round(rf_mean * n_total)), n_total)
        cnn_ci = wilson_interval(int(round(cnn_mean * n_total)), n_total)
        gru_ci = wilson_interval(int(round(gru_mean * n_total)), n_total)

        records.append({
            "resolver": resolver, "protocol": protocol, "workload": workload,
            "domains": num_classes, "n_samples": n_total,
            "rf_seq_acc": round(rf_mean, 4), "rf_ci_lo": round(rf_ci[0], 4), "rf_ci_hi": round(rf_ci[1], 4),
            "cnn_acc": round(cnn_mean, 4), "cnn_ci_lo": round(cnn_ci[0], 4), "cnn_ci_hi": round(cnn_ci[1], 4),
            "gru_acc": round(gru_mean, 4), "gru_ci_lo": round(gru_ci[0], 4), "gru_ci_hi": round(gru_ci[1], 4),
            "chance": round(1.0 / num_classes, 4),
        })
        print(f"  {resolver:10s} {protocol:5s} | RF: {rf_mean:.3f} | 1D-CNN: {cnn_mean:.3f} | GRU: {gru_mean:.3f} (chance: {1.0/num_classes:.3f})")

    return pd.DataFrame(records)


def plot_wp8_comparison(df_wp8: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(df_wp8))
    width = 0.25

    labels = [f"{r['resolver']}\n{r['protocol'].upper()}" for _, r in df_wp8.iterrows()]

    ax.bar(x - width, df_wp8["rf_seq_acc"], width, label="Random Forest (Seq Only)", color="#4c72b0")
    ax.bar(x, df_wp8["cnn_acc"], width, label="1D-CNN", color="#55a868")
    ax.bar(x + width, df_wp8["gru_acc"], width, label="Bidirectional GRU", color="#c44e52")

    ax.axhline(0.01, color="black", linestyle=":", label="Chance (1/100 = 1%)")
    ax.set_ylabel("Accuracy on Packet Sequences", fontsize=11)
    ax.set_title("WP8: Sequence Models vs Tree Models on Raw Packet Sizes (pkt_00 to pkt_19)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure: {out_path}")


# =============================================================================
# WP9: Open-World Fingerprinting Evaluation
# =============================================================================

def evaluate_wp9_open_world(df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, dict]:
    print("\n--- Running WP9: Open-World Fingerprinting (Monitored vs Unmonitored) ---")
    curves_records = []
    summary_records = {}

    # Target slices: AdGuard & Quad9 on DoH vs DoH/3
    slices = [
        ("adguard", "doh"),
        ("adguard", "doh3"),
        ("quad9", "doh"),
        ("quad9", "doh3"),
    ]

    for resolver, protocol in slices:
        sub = df[(df["resolver"] == resolver) & (df["protocol"] == protocol) & (df["workload"] == "global")]
        sampled, _ = select_headline_repeats(sub, 8, 19, target_k=10)
        if sampled.empty or sampled["domain"].nunique() < 50:
            continue

        all_domains = sorted(sampled["domain"].unique())
        # First 20 domains are Monitored (positives), remaining are Unmonitored (negatives)
        monitored_domains = set(all_domains[:20])
        unmonitored_domains = set(all_domains[20:])

        sampled["is_monitored"] = sampled["domain"].isin(monitored_domains).astype(int)

        # Train on repeats 8-15, test on repeats 16-19 (open world unseen repeats)
        train_df = sampled[sampled["repeat"].between(8, 15)]
        test_df = sampled[sampled["repeat"].between(16, 19)]

        # Fit multi-class classifier on training set
        rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)
        rf.fit(train_df[features].to_numpy(float), train_df["domain"].to_numpy())

        # Test set probability inference
        test_x = test_df[features].to_numpy(float)
        probs = rf.predict_proba(test_x)
        classes = rf.classes_

        # Probability that the sample is in the monitored set
        monitored_indices = [i for i, c in enumerate(classes) if c in monitored_domains]
        p_monitored = probs[:, monitored_indices].sum(axis=1)

        y_true = test_df["is_monitored"].to_numpy()

        # Compute ROC and PR curves
        fpr, tpr, _ = roc_curve(y_true, p_monitored)
        prec, rec, _ = precision_recall_curve(y_true, p_monitored)
        roc_auc = float(auc(fpr, tpr))
        pr_auc = float(auc(rec, prec))

        summary_records[f"{resolver}_{protocol}"] = {
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "n_monitored": len(monitored_domains),
            "n_unmonitored": len(unmonitored_domains),
        }

        # Subsample points for curves CSV
        sample_indices = np.linspace(0, len(rec) - 1, min(50, len(rec)), dtype=int)
        for idx in sample_indices:
            curves_records.append({
                "resolver": resolver,
                "protocol": protocol,
                "precision": round(float(prec[idx]), 4),
                "recall": round(float(rec[idx]), 4),
                "roc_auc": round(roc_auc, 4),
                "pr_auc": round(pr_auc, 4),
            })

        print(f"  {resolver:10s} {protocol:5s} | Open-World ROC-AUC: {roc_auc:.3f} | PR-AUC: {pr_auc:.3f}")

    return pd.DataFrame(curves_records), summary_records


def plot_wp9_curves(df_curves: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = {
        ("adguard", "doh"): "#1f77b4",
        ("adguard", "doh3"): "#1f77b4",
        ("quad9", "doh"): "#d62728",
        ("quad9", "doh3"): "#d62728",
    }
    linestyles = {"doh": "-", "doh3": "--"}

    for (res, proto), group in df_curves.groupby(["resolver", "protocol"]):
        group = group.sort_values("recall")
        auc_val = group["pr_auc"].iloc[0]
        ax.plot(
            group["recall"], group["precision"],
            linestyle=linestyles[proto],
            color=colors[(res, proto)],
            label=f"{res.capitalize()} {proto.upper()} (PR-AUC={auc_val:.2f})",
            linewidth=2
        )

    # Base rate of monitored domains: 20 / 100 = 0.20
    ax.axhline(0.20, color="gray", linestyle=":", label="Chance Precision (20/100 = 0.20)")
    ax.set_xlabel("Recall (TPR on Monitored)", fontsize=11)
    ax.set_ylabel("Precision", fontsize=11)
    ax.set_title("WP9: Open-World Precision-Recall Curves (20 Monitored vs 80 Unmonitored)", fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure: {out_path}")


# =============================================================================
# WP13: Countermeasure What-If Defense Simulations
# =============================================================================

def simulate_defenses_on_frame(df_slice: pd.DataFrame, features: list[str]) -> dict[str, pd.DataFrame]:
    """Generates simulated countermeasure variants of the feature set."""
    sims = {}
    # 1. Unmitigated baseline
    sims["unmitigated"] = df_slice.copy()

    # 2. 128-byte RFC 8467 fixed padding simulation
    df_p128 = df_slice.copy()
    for col in PKT_COLS:
        if col in df_p128.columns:
            s = df_p128[col].values
            df_p128[col] = np.sign(s) * np.ceil(np.abs(s) / 128.0) * 128.0
    for col in ["bytes_up", "bytes_down", "bytes_total"]:
        if col in df_p128.columns:
            df_p128[col] = np.ceil(df_p128[col] / 128.0) * 128.0
    sims["sim_pad128"] = df_p128

    # 3. 468-byte RFC 8467 padding simulation (standard recommended padding for DoH/DoT)
    df_p468 = df_slice.copy()
    for col in PKT_COLS:
        if col in df_p468.columns:
            s = df_p468[col].values
            df_p468[col] = np.sign(s) * np.ceil(np.abs(s) / 468.0) * 468.0
    for col in ["bytes_up", "bytes_down", "bytes_total"]:
        if col in df_p468.columns:
            df_p468[col] = np.ceil(df_p468[col] / 468.0) * 468.0
    sims["sim_pad468"] = df_p468

    # 4. Timing Jitter simulation (Gaussian noise on duration & IATs, sigma = 20ms)
    rng = np.random.default_rng(42)
    df_jitter = df_slice.copy()
    for col in ["duration", "iat_mean", "iat_median", "iat_max", "t_first_down"]:
        if col in df_jitter.columns:
            noise = rng.normal(0, 0.020, size=len(df_jitter))
            df_jitter[col] = np.clip(df_jitter[col] + noise, 0.001, None)
    sims["sim_jitter20ms"] = df_jitter

    # 5. Combined simulation: 468-byte padding + 20ms timing jitter
    df_comb = df_p468.copy()
    for col in ["duration", "iat_mean", "iat_median", "iat_max", "t_first_down"]:
        if col in df_comb.columns:
            noise = rng.normal(0, 0.020, size=len(df_comb))
            df_comb[col] = np.clip(df_comb[col] + noise, 0.001, None)
    sims["sim_combined"] = df_comb

    return sims


def evaluate_wp13_defenses(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    print("\n--- Running WP13: Countermeasure What-If Defense Simulations ---")
    print("  [NOTE: Per methodology guidelines, all defensive padding and jitter are explicitly simulated]")
    records = []

    slices = [
        ("adguard", "doh"),
        ("adguard", "doh3"),
        ("quad9", "doh"),
        ("quad9", "doh3"),
        ("google", "doh"),
        ("google", "doh3"),
    ]

    for resolver, protocol in slices:
        sub = df[(df["resolver"] == resolver) & (df["protocol"] == protocol) & (df["workload"] == "global")]
        sampled, _ = select_headline_repeats(sub, 8, 19, target_k=10)
        if sampled.empty or sampled["domain"].nunique() < 25:
            continue

        n_domains = sampled["domain"].nunique()
        sim_variants = simulate_defenses_on_frame(sampled, features)

        le = LabelEncoder()
        y = le.fit_transform(sampled["domain"].values)
        repeats = sorted(sampled["repeat"].unique())
        folds = [repeats[i:i + 2] for i in range(0, len(repeats), 2)]

        for sim_name, sim_df in sim_variants.items():
            scores = []
            for held_out in folds:
                train_mask = ~sim_df["repeat"].isin(held_out)
                test_mask = sim_df["repeat"].isin(held_out)
                rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)
                rf.fit(sim_df.loc[train_mask, features].to_numpy(float), y[train_mask])
                preds = rf.predict(sim_df.loc[test_mask, features].to_numpy(float))
                scores.append(accuracy_score(y[test_mask], preds))

            mean_acc = float(np.mean(scores))
            ci_lo, ci_hi = wilson_interval(int(round(mean_acc * len(sampled))), len(sampled))

            records.append({
                "resolver": resolver,
                "protocol": protocol,
                "defense": sim_name,
                "domains": n_domains,
                "accuracy": round(mean_acc, 4),
                "ci_low": round(ci_lo, 4),
                "ci_high": round(ci_hi, 4),
                "chance": round(1.0 / n_domains, 4),
            })
            print(f"  {resolver:10s} {protocol:5s} | Defense: {sim_name:15s} -> Acc: {mean_acc:.3f}")

    return pd.DataFrame(records)


def plot_wp13_defenses(df_def: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(11, 6))

    # Order of defenses
    def_order = ["unmitigated", "sim_pad128", "sim_pad468", "sim_jitter20ms", "sim_combined"]
    def_labels = ["Unmitigated", "Sim. 128B Pad", "Sim. 468B Pad", "Sim. 20ms Jitter", "Sim. Combined"]

    slices = sorted(df_def.groupby(["resolver", "protocol"]).groups.keys())
    x = np.arange(len(slices))
    width = 0.16

    colors = ["#2b5c8f", "#4a8bc2", "#74add1", "#fdae61", "#d73027"]

    for i, (d_name, d_label) in enumerate(zip(def_order, def_labels)):
        accs = [
            df_def[(df_def["resolver"] == r) & (df_def["protocol"] == p) & (df_def["defense"] == d_name)]["accuracy"].values[0]
            for r, p in slices
        ]
        ax.bar(x + (i - 2) * width, accs, width, label=d_label, color=colors[i])

    ax.axhline(0.01, color="black", linestyle=":", label="Chance (1/100 = 1%)")
    ax.set_ylabel("Fingerprinting Accuracy", fontsize=11)
    ax.set_title("WP13: Simulated Defense Effectiveness Across Encrypted DNS Protocols", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r.capitalize()}\n{p.upper()}" for r, p in slices], fontsize=10)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure: {out_path}")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Fast smoke test mode")
    args = parser.parse_args()

    OUT_WP8.mkdir(parents=True, exist_ok=True)
    OUT_WP9.mkdir(parents=True, exist_ok=True)
    OUT_WP13.mkdir(parents=True, exist_ok=True)

    print("Loading dataset...")
    df_v2 = pd.read_csv(DATA_PATH)
    features = available_features(df_v2)

    # 1. WP8: Deep Learning (1D-CNN, GRU, RF)
    df_wp8 = evaluate_wp8_models(df_v2, quick=args.quick)
    df_wp8.to_csv(OUT_WP8 / "wp8_models.csv", index=False)
    plot_wp8_comparison(df_wp8, OUT_WP8 / "wp8_comparison.png")

    # 2. WP9: Open-World Fingerprinting
    df_wp9, summary_wp9 = evaluate_wp9_open_world(df_v2, features)
    df_wp9.to_csv(OUT_WP9 / "open_world_curves.csv", index=False)
    (OUT_WP9 / "open_world_summary.json").write_text(json.dumps(summary_wp9, indent=2))
    plot_wp9_curves(df_wp9, OUT_WP9 / "open_world_pr_curves.png")

    # 3. WP13: Defense Simulations
    df_wp13 = evaluate_wp13_defenses(df_v2, features)
    df_wp13.to_csv(OUT_WP13 / "defense_simulations.csv", index=False)
    plot_wp13_defenses(df_wp13, OUT_WP13 / "defense_ablation.png")

    print("\n✅ WP8, WP9 & WP13 (KU5) Evaluations Complete!")


if __name__ == "__main__":
    main()
