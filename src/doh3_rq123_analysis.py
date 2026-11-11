"""DoH/3 (DNS-over-HTTP/3) Dedicated Privacy Analysis for RQ1, RQ2, and RQ3.

Research Questions (DoH/3 Focused):
  RQ1: Can DNS queries over DoH/3 be distinguished using encrypted traffic metadata?
       (Domain identification / fingerprinting on DoH/3 traffic)
  RQ2: How does the traffic-analysis resistance of DoH/3 compare across resolvers?
       (Comparing DoH/3 implementation privacy on Cloudflare, Google, Quad9, AdGuard)
  RQ3: Which traffic characteristics (packet sizes, timing, burst patterns, directionality)
       contribute most to DoH/3 metadata leakage? (Feature importance, ANOVA F, ablation)

Usage:
    python src\\doh3_rq123_analysis.py             # full run
    python src\\doh3_rq123_analysis.py --quick     # smoke test (~10-20 sec)
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import f_classif
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBClassifier
    HAVE_XGB = True
except Exception:
    HAVE_XGB = False

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
SEED = 42

GROUPS = {
    "volume":     ["n_pkts", "n_up", "n_down", "bytes_up", "bytes_down",
                   "bytes_total", "ratio_bytes_down_up"],
    "size_stats": ["up_mean", "up_std", "up_max", "down_mean", "down_std", "down_max"],
    "timing":     ["duration", "iat_mean", "iat_std", "iat_median", "iat_max", "t_first_down"],
    "bursts":     ["n_bursts", "burst_len_mean", "burst_len_max",
                   "burst_bytes_mean", "burst_bytes_max"],
    "first20":    [f"pkt_{i:02d}" for i in range(20)],
}
FEATS = [c for cols in GROUPS.values() for c in cols]
GROUP_OF = {f: g for g, cols in GROUPS.items() for f in cols}


def select_headline_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    config = yaml.safe_load((ROOT / "config" / "project.yaml").read_text(encoding="utf-8"))
    settings = config["analysis"]
    start, end = settings["headline_repeats"]
    target_k = settings["target_successful_repeats"]
    selected = df[df["repeat"].between(start, end)].copy()
    counts = selected.groupby("domain")["repeat"].nunique()
    dropped = {
        str(domain): f"{int(count)} successful repeats; required {target_k}"
        for domain, count in counts.items() if count < target_k
    }
    return selected[selected["domain"].isin(set(counts[counts >= target_k].index))].copy(), dropped


def make_model(name: str, jobs: int, n_est: int = 100):
    if name == "rf":
        return RandomForestClassifier(
            n_estimators=n_est, class_weight="balanced_subsample",
            n_jobs=jobs, random_state=SEED,
        )
    return XGBClassifier(
        n_estimators=n_est, max_depth=5, learning_rate=0.1, subsample=0.9,
        colsample_bytree=0.9, n_jobs=jobs, random_state=SEED,
        eval_metric="mlogloss", tree_method="hist", verbosity=0,
    )


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def evaluate_split(X_tr, y_tr, X_te, y_te, jobs: int, model_name="xgb", n_est: int = 100):
    """Fast repeat-based split evaluation (returns pred, proba, top5, accuracy, f1)."""
    classes = np.unique(y_tr)
    le = LabelEncoder().fit(classes)
    model = make_model(model_name, jobs, n_est=n_est)
    model.fit(X_tr, le.transform(y_tr))

    # Test filtering
    te_mask = [y in classes for y in y_te]
    X_te_f = X_te[te_mask]
    y_te_f = np.array(y_te)[te_mask]

    proba = model.predict_proba(X_te_f)
    pred_enc = proba.argmax(axis=1)
    pred = le.inverse_transform(pred_enc)

    y_te_enc = le.transform(y_te_f)
    k_top = min(5, proba.shape[1])
    top_idx = np.argsort(-proba, axis=1)[:, :k_top]
    top5_hits = sum(y_te_enc[i] in top_idx[i] for i in range(len(y_te_enc)))

    acc = accuracy_score(y_te_f, pred)
    top5_acc = top5_hits / len(y_te_f) if len(y_te_f) > 0 else 0.0
    macro_f1 = f1_score(y_te_f, pred, average="macro")

    return {
        "accuracy": acc, "top5": top5_acc, "macro_f1": macro_f1,
        "n_test": len(y_te_f), "y_true": y_te_f, "y_pred": pred,
        "model": model, "classes": classes
    }


def fingerprint_doh3(df_slice: pd.DataFrame, jobs: int, n_perm: int, cols=None, seed=SEED, n_est: int = 10):
    """Rigorous evaluation: leave-one-repeat-out across every unique repeat, pooled Wilson CI."""
    cols = cols or FEATS
    d = df_slice.dropna(subset=cols).copy()
    if d["domain"].nunique() < 5 or d["repeat"].nunique() < 2:
        return None

    unique_reps = np.sort(d["repeat"].unique())
    fold_accuracies = []
    fold_top5 = []
    fold_macro_f1 = []
    pooled_y_true = []
    pooled_y_pred = []

    # Permutation baseline logic
    rng = np.random.default_rng(seed)
    perm = []

    for r in unique_reps:
        tr_mask = d["repeat"] != r
        te_mask = d["repeat"] == r

        X_tr = d.loc[tr_mask, cols].to_numpy(float)
        y_tr = d.loc[tr_mask, "domain"].to_numpy()
        X_te = d.loc[te_mask, cols].to_numpy(float)
        y_te = d.loc[te_mask, "domain"].to_numpy()

        eval_out = evaluate_split(X_tr, y_tr, X_te, y_te, jobs, "rf", n_est=n_est)

        fold_accuracies.append(eval_out["accuracy"])
        fold_top5.append(eval_out["top5"])
        fold_macro_f1.append(eval_out["macro_f1"])
        pooled_y_true.extend(eval_out["y_true"])
        pooled_y_pred.extend(eval_out["y_pred"])

        # Permutation baseline logic inside the same loop
        for _ in range(n_perm):
            y_tr_shuffled = rng.permutation(y_tr)
            p_res = evaluate_split(X_tr, y_tr_shuffled, X_te, y_te, jobs, "rf", n_est=n_est)
            perm.append(p_res["accuracy"])

    avg_acc = float(np.mean(fold_accuracies))
    avg_top5 = float(np.mean(fold_top5))
    avg_f1 = float(np.mean(fold_macro_f1))

    pooled_y_true = np.array(pooled_y_true)
    pooled_y_pred = np.array(pooled_y_pred)
    n_pooled = len(pooled_y_true)
    k_pooled = int((pooled_y_true == pooled_y_pred).sum())
    lo, hi = wilson(k_pooled, n_pooled)

    perm = np.array(perm) if perm else np.array([np.nan])
    chance_1_over_k = round(1.0 / d["domain"].nunique(), 4)
    p_95 = round(float(np.nanpercentile(perm, 95)), 4) if n_perm else chance_1_over_k
    p_mean = round(float(np.nanmean(perm)), 4) if n_perm else chance_1_over_k
    p_val = round((1 + int((perm >= avg_acc).sum())) / (1 + len(perm)), 4) if n_perm else np.nan

    return {
        "n": len(d),
        "n_test": n_pooled,
        "n_domains": int(d["domain"].nunique()),
        "chance_1_over_K": chance_1_over_k,
        "accuracy": round(avg_acc, 4),
        "ci95_lo": round(lo, 4),
        "ci95_hi": round(hi, 4),
        "top5": round(avg_top5, 4),
        "macro_f1": round(avg_f1, 4),
        "perm_mean": p_mean,
        "perm_p95": p_95,
        "p_value": p_val,
        "y_true": pooled_y_true,
        "y_pred": pooled_y_pred,
    }


def md_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_No data available_\n"
    head = "| " + " | ".join(map(str, df.columns)) + " |\n"
    sep  = "| " + " | ".join("---" for _ in df.columns) + " |\n"
    body = "".join("| " + " | ".join(str(v) for v in row) + " |\n"
                   for row in df.itertuples(index=False))
    return head + sep + body


# ═══════════════════════════════════════════════════════════════════════════════
# RQ1: DoH/3 Domain Query Identification (Can queries be distinguished?)
# ═══════════════════════════════════════════════════════════════════════════════
def run_rq1(doh3: pd.DataFrame, a, out_dir: Path):
    print("\n" + "=" * 65, flush=True)
    print("RQ1: DoH/3 Domain Query Identification (Fingerprinting)", flush=True)
    print("=" * 65, flush=True)

    rows = []
    # 1. Overall DoH/3 domain fingerprinting (all resolvers)
    res_all = fingerprint_doh3(doh3, a.jobs, a.perm, n_est=a.n_est)
    if res_all:
        is_sig = "Yes" if res_all["p_value"] < 0.05 else "No"
        rows.append({
            "target": "DoH/3 (All Resolvers)",
            "total_samples": res_all["n"],
            "test_samples": res_all["n_test"],
            "domains": res_all["n_domains"],
            "chance_baseline": res_all["chance_1_over_K"],
            "accuracy": res_all["accuracy"],
            "top5_accuracy": res_all["top5"],
            "macro_f1": res_all["macro_f1"],
            "perm_p95": res_all["perm_p95"],
            "stat_significant": is_sig,
        })
        print(f"  [All Resolvers] Accuracy: {res_all['accuracy']*100:.2f}% | Top-5: {res_all['top5']*100:.2f}% | Random Chance: {res_all['chance_1_over_K']*100:.2f}%", flush=True)

    # 2. Per-Resolver DoH/3 fingerprinting
    resolvers = sorted(doh3.resolver.unique())
    cm_to_plot = None
    for res_name in resolvers:
        slice_df = doh3[doh3.resolver == res_name]
        res_r = fingerprint_doh3(slice_df, a.jobs, a.perm, n_est=a.n_est)
        if res_r:
            is_sig = "Yes" if res_r["p_value"] < 0.05 else "No"
            rows.append({
                "target": f"DoH/3 ({res_name.title()})",
                "total_samples": res_r["n"],
                "test_samples": res_r["n_test"],
                "domains": res_r["n_domains"],
                "chance_baseline": res_r["chance_1_over_K"],
                "accuracy": res_r["accuracy"],
                "top5_accuracy": res_r["top5"],
                "macro_f1": res_r["macro_f1"],
                "perm_p95": res_r["perm_p95"],
                "stat_significant": is_sig,
            })
            print(f"  [{res_name.title():10s}] Accuracy: {res_r['accuracy']*100:.2f}% | Top-5: {res_r['top5']*100:.2f}% | Macro-F1: {res_r['macro_f1']:.4f}", flush=True)
            if cm_to_plot is None:
                cm_to_plot = (res_r["y_true"], res_r["y_pred"], res_name.title())

    rq1_df = pd.DataFrame(rows)
    rq1_df.to_csv(out_dir / "RQ1_doh3_domain_identification.csv", index=False)

    # Plot RQ1: Confusion matrix (top 15 domains)
    if cm_to_plot:
        y_true, y_pred, title_res = cm_to_plot
        top_domains = pd.Series(y_true).value_counts().head(15).index.tolist()
        mask = [yt in top_domains and yp in top_domains for yt, yp in zip(y_true, y_pred)]
        if sum(mask) > 5:
            yt_sub = [y for y, m in zip(y_true, mask) if m]
            yp_sub = [y for y, m in zip(y_pred, mask) if m]
            labels = sorted(top_domains)
            cm = confusion_matrix(yt_sub, yp_sub, labels=labels)

            fig, ax = plt.subplots(figsize=(8, 7))
            im = ax.imshow(cm, cmap="Blues")
            ax.set_xticks(range(len(labels)))
            ax.set_yticks(range(len(labels)))
            ax.set_xticklabels([l.replace(".com", "").replace(".gov.in", "") for l in labels], rotation=45, ha="right", fontsize=9)
            ax.set_yticklabels([l.replace(".com", "").replace(".gov.in", "") for l in labels], fontsize=9)
            ax.set_xlabel("Predicted Domain", fontsize=11, fontweight="bold")
            ax.set_ylabel("True Domain", fontsize=11, fontweight="bold")
            ax.set_title(f"RQ1: DoH/3 Domain Fingerprinting Confusion Matrix\n({title_res} Resolver - Top 15 Domains)", fontsize=12, pad=12)

            for i in range(len(labels)):
                for j in range(len(labels)):
                    if cm[i, j] > 0:
                        ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                                color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=8)

            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            fig.tight_layout()
            fig.savefig(out_dir / "RQ1_doh3_confusion_matrix.png", dpi=200)
            plt.close(fig)
            print(f"  Saved confusion matrix -> {out_dir / 'RQ1_doh3_confusion_matrix.png'}", flush=True)

    return rq1_df


# ═══════════════════════════════════════════════════════════════════════════════
# RQ2: Traffic-Analysis Resistance across DoH/3 Resolvers
# ═══════════════════════════════════════════════════════════════════════════════
def run_rq2(doh3: pd.DataFrame, a, out_dir: Path):
    print("\n" + "=" * 65, flush=True)
    print("RQ2: DoH/3 Domain Fingerprinting Across Resolvers", flush=True)
    print("=" * 65, flush=True)

    resolvers = sorted(doh3.resolver.unique())
    rows = []

    for res in resolvers:
        sub = doh3[doh3.resolver == res]
        r = fingerprint_doh3(sub, a.jobs, a.perm, n_est=a.n_est)
        if r:
            rows.append({
                "resolver": res.title(),
                "n_samples": r["n"],
                "accuracy": r["accuracy"],
                "ci95_low": r["ci95_lo"],
                "ci95_high": r["ci95_hi"],
                "top5_accuracy": r["top5"],
                "macro_f1": r["macro_f1"],
                "chance_baseline": r["chance_1_over_K"],
                "perm_p95": r["perm_p95"],
                "p_value": r["p_value"],
            })
            print(f"  {res.title():10s} | Accuracy: {r['accuracy']*100:.2f}% (95% CI: {r['ci95_lo']*100:.1f}%-{r['ci95_hi']*100:.1f}%) | p={r['p_value']}", flush=True)

    rq2_df = pd.DataFrame(rows)
    rq2_df.to_csv(out_dir / "RQ2_doh3_resolver_resistance.csv", index=False)

    # Plot RQ2: Comparative Bar Chart
    if not rq2_df.empty:
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        names = rq2_df["resolver"].tolist()
        accs = rq2_df["accuracy"].to_numpy() * 100
        err_low = np.maximum(0, accs - (rq2_df["ci95_low"].to_numpy() * 100))
        err_high = np.maximum(0, (rq2_df["ci95_high"].to_numpy() * 100) - accs)
        p95s = rq2_df["perm_p95"].to_numpy() * 100

        x = np.arange(len(names))
        width = 0.45

        bars = ax.bar(x, accs, width, yerr=[err_low, err_high], capsize=5,
                      color="#2b5c8f", edgecolor="black", linewidth=0.8,
                      label="DoH/3 Fingerprinting Accuracy (95% CI)")

        ax.scatter(x, p95s, color="#d95f02", marker="D", s=45, zorder=5,
                   label="Permutation Chance (95th pctl)")


        ax.set_ylabel("Fingerprinting Accuracy (%)", fontsize=11, fontweight="bold")
        ax.set_xlabel("DoH/3 Resolver Implementation", fontsize=11, fontweight="bold")
        ax.set_title("RQ2: DoH/3 Domain Fingerprinting Across Resolvers", fontsize=12, pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=10)
        ax.set_ylim(bottom=0, top=max(accs.max() * 1.35, 18))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax.grid(axis="y", linestyle=":", alpha=0.6)
        ax.legend(fontsize=9, loc="upper right")

        for bar, val in zip(bars, accs):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

        fig.tight_layout()
        fig.savefig(out_dir / "RQ2_doh3_resolver_resistance.png", dpi=200)
        plt.close(fig)
        print(f"  Saved resistance plot -> {out_dir / 'RQ2_doh3_resolver_resistance.png'}", flush=True)

    return rq2_df


# ═══════════════════════════════════════════════════════════════════════════════
# RQ3: Traffic Characteristics Contributing Most to DoH/3 Leakage
# ═══════════════════════════════════════════════════════════════════════════════
def run_rq3(doh3: pd.DataFrame, a, out_dir: Path):
    print("\n" + "=" * 65, flush=True)
    print("RQ3: Traffic Characteristics Driving DoH/3 Metadata Leakage", flush=True)
    print("=" * 65, flush=True)

    X = doh3[FEATS].to_numpy(float)
    y = doh3.domain.to_numpy()
    le = LabelEncoder().fit(y)
    y_enc = le.transform(y)

    # MDI is retained for diagnostics only; permutation importance is the reported rank.
    rf = RandomForestClassifier(n_estimators=100, random_state=SEED, n_jobs=a.jobs)
    rf.fit(X, y_enc)
    mdi_importances = pd.Series(rf.feature_importances_, index=FEATS)
    perm_result = permutation_importance(rf, X, y_enc, n_repeats=10, random_state=SEED, n_jobs=a.jobs)
    importances = pd.Series(perm_result.importances_mean, index=FEATS).sort_values(ascending=False)

    top20_df = importances.head(20).round(4).reset_index()
    top20_df.columns = ["feature", "permutation_importance"]
    top20_df["group"] = top20_df["feature"].map(GROUP_OF)
    top20_df["mdi_importance"] = top20_df["feature"].map(mdi_importances)
    top20_df.to_csv(out_dir / "RQ3_doh3_top_features.csv", index=False)

    # 2. Cumulative group importance
    grp_sums = {g: round(float(importances[cols].sum()), 4) for g, cols in GROUPS.items()}
    grp_df = pd.DataFrame([{"feature_group": g, "total_importance": v, "num_features": len(GROUPS[g])}
                           for g, v in sorted(grp_sums.items(), key=lambda x: -x[1])])
    grp_df["pct_of_total"] = (grp_df["total_importance"] * 100).round(1)
    grp_df.to_csv(out_dir / "RQ3_doh3_group_importance.csv", index=False)
    print("\n  DoH/3 Feature Group Importance:", flush=True)
    print(grp_df.to_string(index=False), flush=True)

    # 3. Systematic Group Ablation Study on DoH/3
    base_res = fingerprint_doh3(doh3, a.jobs, n_perm=0, n_est=a.n_est)
    base_acc = base_res["accuracy"] if base_res else 0.0

    ablation_rows = [{
        "setting": "All Features (Baseline)",
        "accuracy": base_acc,
        "delta_vs_baseline": 0.0,
        "interpretation": "Full feature baseline",
    }]

    print(f"\n  Running feature group ablations (Baseline Acc: {base_acc*100:.2f}%)...", flush=True)
    for gname, cols in GROUPS.items():
        # Without group
        remaining = [c for c in FEATS if c not in cols]
        res_wo = fingerprint_doh3(doh3, a.jobs, n_perm=0, cols=remaining, n_est=a.n_est)
        acc_wo = res_wo["accuracy"] if res_wo else 0.0
        delta_wo = round(acc_wo - base_acc, 4)

        ablation_rows.append({
            "setting": f"Without {gname.replace('_', ' ').title()}",
            "accuracy": acc_wo,
            "delta_vs_baseline": delta_wo,
            "interpretation": f"Impact of removing {gname}",
        })

        # Only group
        res_only = fingerprint_doh3(doh3, a.jobs, n_perm=0, cols=cols, n_est=a.n_est)
        acc_only = res_only["accuracy"] if res_only else 0.0
        delta_only = round(acc_only - base_acc, 4)

        ablation_rows.append({
            "setting": f"Only {gname.replace('_', ' ').title()}",
            "accuracy": acc_only,
            "delta_vs_baseline": delta_only,
            "interpretation": f"Standalone power of {gname}",
        })
        print(f"    Without {gname:12s}: {acc_wo*100:.2f}% (delta: {delta_wo*100:+.2f}%) | Only {gname:12s}: {acc_only*100:.2f}%", flush=True)

    ablation_df = pd.DataFrame(ablation_rows)
    ablation_df.to_csv(out_dir / "RQ3_doh3_ablation.csv", index=False)

    # 4. ANOVA F-statistic for domain discriminative power
    F_vals, _ = f_classif(X, y_enc)
    f_df = pd.DataFrame({
        "feature": FEATS,
        "group": [GROUP_OF[f] for f in FEATS],
        "F_statistic": np.nan_to_num(F_vals).round(2),
    }).sort_values("F_statistic", ascending=False)
    f_df.to_csv(out_dir / "RQ3_doh3_anova_signal.csv", index=False)

    # Plots:
    # Feature Importance Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    group_colors = {
        "volume": "#2b5c8f",
        "size_stats": "#e66101",
        "timing": "#d7191c",
        "bursts": "#5e3c99",
        "first20": "#0571b0",
    }

    top15 = importances.head(15)
    c_list = [group_colors.get(GROUP_OF[f], "#888") for f in top15.index]
    y_pos = np.arange(len(top15))

    ax1.barh(y_pos, top15.values, color=c_list, edgecolor="black", linewidth=0.5)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(top15.index, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("Importance (MDI Gini)", fontsize=10, fontweight="bold")
    ax1.set_title("Top 15 Leaking Features in DoH/3", fontsize=11, fontweight="bold")
    ax1.grid(axis="x", linestyle=":", alpha=0.6)

    # Group bar chart
    g_names = [g["feature_group"].replace("_", " ").title() for _, g in grp_df.iterrows()]
    g_vals = [g["pct_of_total"] for _, g in grp_df.iterrows()]
    g_cols = [group_colors.get(g["feature_group"], "#888") for _, g in grp_df.iterrows()]

    bars2 = ax2.bar(g_names, g_vals, color=g_cols, edgecolor="black", linewidth=0.5)
    ax2.set_ylabel("Share of Total Importance (%)", fontsize=10, fontweight="bold")
    ax2.set_title("Importance by Traffic Category (DoH/3)", fontsize=11, fontweight="bold")
    ax2.set_xticklabels(g_names, rotation=25, ha="right", fontsize=9)
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    for bar, val in zip(bars2, g_vals):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out_dir / "RQ3_doh3_feature_importance.png", dpi=200)
    plt.close(fig)
    print(f"  Saved feature importance plot -> {out_dir / 'RQ3_doh3_feature_importance.png'}", flush=True)

    # Ablation Delta Plot
    fig, ax = plt.subplots(figsize=(8, 4.5))
    wo_rows = ablation_df[ablation_df.setting.str.startswith("Without")].copy()
    wo_rows["name"] = wo_rows["setting"].str.replace("Without ", "")

    bars = ax.barh(wo_rows["name"], wo_rows["delta_vs_baseline"] * 100,
                   color="#d7191c", edgecolor="black", linewidth=0.6)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Accuracy Change when Feature Group is Removed (%)", fontsize=10, fontweight="bold")
    ax.set_title("RQ3: Feature Group Ablation on DoH/3\n(Negative drop = critical feature group)", fontsize=11, fontweight="bold")
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    for bar, delta in zip(bars, wo_rows["delta_vs_baseline"] * 100):
        ha = "right" if delta < 0 else "left"
        x_pos = delta - 0.1 if delta < 0 else delta + 0.1
        ax.text(x_pos, bar.get_y() + bar.get_height()/2, f"{delta:+.2f}%",
                va="center", ha=ha, fontsize=9, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out_dir / "RQ3_doh3_ablation.png", dpi=200)
    plt.close(fig)
    print(f"  Saved ablation plot -> {out_dir / 'RQ3_doh3_ablation.png'}", flush=True)

    return top20_df, grp_df, ablation_df, f_df


# ═══════════════════════════════════════════════════════════════════════════════
# Main Runner & Report Generator
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "dataset.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "doh3")
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--perm", type=int, default=200, help="permutations for empirical baseline")
    ap.add_argument("--n-est", type=int, default=100, help="number of trees")
    ap.add_argument("--quick", action="store_true", help="deprecated; retains the complete configured permutation count")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    if not args.dataset.exists():
        sys.exit(f"Error: {args.dataset} not found. Run extract_features.py first.")

    raw_df = pd.read_csv(args.dataset)
    doh3 = raw_df[raw_df["protocol"] == "doh3"].copy().reset_index(drop=True)
    doh3, dropped_domains = select_headline_data(doh3)
    if doh3.empty:
        sys.exit("Error: No DoH/3 rows found in dataset.csv!")

    print("=" * 65, flush=True)
    print("DOH/3 PRIVACY ANALYSIS (RQ1 - RQ2 - RQ3)", flush=True)
    print("=" * 65, flush=True)
    print(f"Loaded {len(doh3)} DoH/3 samples across {doh3.resolver.nunique()} resolvers and {doh3.domain.nunique()} domains.", flush=True)
    print(f"Headline repeats: 8-19; target successful repeats: 10; "
          f"dropped domains: {dropped_domains or 'none'}", flush=True)
    overview = doh3.groupby("resolver").agg(
        samples=("domain", "size"),
        domains=("domain", "nunique"),
        max_repeats=("repeat", "max"),
    ).reset_index()
    print(overview.to_string(index=False), flush=True)

    t0 = time.time()
    rq1_df = run_rq1(doh3, args, args.out)
    rq2_df = run_rq2(doh3, args, args.out)
    top_feats, grp_imp, abl_df, anova_df = run_rq3(doh3, args, args.out)

    report_content = f"""# DoH/3 (DNS-over-HTTP/3) Privacy Evaluation: RQ1, RQ2, and RQ3

**Dataset:** `{args.dataset}`  
**Protocol:** DNS-over-HTTP/3 (`doh3`)  
**Total DoH/3 Samples:** {len(doh3)}  
**Domains:** {doh3.domain.nunique()}  
**Resolvers:** {", ".join(sorted(doh3.resolver.unique()))}  

---

## 1. DoH/3 Dataset Overview
{md_table(overview)}

---

## 2. RQ1: Can DNS queries over DoH/3 be distinguished using traffic metadata?
**Research Question:** *Can an passive eavesdropper identify which domain or website is being queried over DoH/3 by observing encrypted traffic flow metadata?*

### Results:
{md_table(rq1_df)}

### Interpretation for RQ1:
Interpret the computed accuracy, interval, and empirical p-value in the table above. A non-significant result means no detectable leakage at this sample size. This DoH/3-only analysis does not support protocol-comparison claims.

---

## 3. RQ2: How does traffic-analysis resistance compare across DoH/3 resolvers?
**Research Question:** *How strong is the traffic-analysis resistance of DoH/3 in practice, and how does resolver implementation (Cloudflare, Google, Quad9, AdGuard) impact privacy?*

### Results:
{md_table(rq2_df)}

### Interpretation for RQ2:
Resolver rows are descriptive. Do not rank resolvers unless a supported paired comparison reports separated intervals and a significant difference.

---

## 4. RQ3: Which traffic characteristics contribute most to DoH/3 leakage?
**Research Question:** *Which features (packet sizes, timing, bursts, directionality, flow statistics) drive metadata leakage in DoH/3?*

### Feature Group Importance:
{md_table(grp_imp)}

### Top 10 Individual Leaking Features:
{md_table(top_feats.head(10))}

### Feature Group Ablation Study:
{md_table(abl_df)}

### Interpretation for RQ3:
Use the computed ablation and permutation-importance results to assess feature groups. MDI importance alone is not evidence of leakage because it can favour continuous features.
"""

    report_path = args.out / "DoH3_RQ123_Report.md"
    report_path.write_text(report_content, encoding="utf-8")
    print("\n" + "=" * 65, flush=True)
    print(f"Analysis successfully completed in {time.time() - t0:.1f}s!", flush=True)
    print(f"Report saved to: {report_path}", flush=True)
    print(f"Figures and CSVs saved to: {args.out}", flush=True)
    print("=" * 65, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
