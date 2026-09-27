"""Pilot analysis of encrypted-DNS metadata leakage (E1-E5) with honest statistics.

Reads  data/processed/dataset.csv
Writes results/*.csv, results/*.png and results/summary.md

Design rules
  * Features are sizes, timing, direction and bursts only (no ports, IPs or transport).
  * Protocol / workload classification uses folds GROUPED BY DOMAIN (test domains are unseen).
  * Domain fingerprinting cannot be grouped by domain (the model must know the domain), so it
    uses leave-one-repeat-out: train on the other repeats, test on the held-out repeat.
  * Every fingerprinting score is compared with an EMPIRICAL chance level (label-permutation
    test) and a 95% Wilson interval, because accuracies of a few percent on ~50 classes are
    easily noise.
  * Fair comparison across protocols = one resolver at a time (Quad9 has all three protocols).

Example:
    python src\\analysis_v2.py             # full run
    python src\\analysis_v2.py --quick     # fast smoke test
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
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBClassifier

    HAVE_XGB = True
except Exception:  # xgboost is optional
    HAVE_XGB = False

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
SEED = 7

GROUPS = {
    "volume": ["n_pkts", "n_up", "n_down", "bytes_up", "bytes_down", "bytes_total", "ratio_bytes_down_up"],
    "size_stats": ["up_mean", "up_std", "up_max", "down_mean", "down_std", "down_max"],
    "timing": ["duration", "iat_mean", "iat_std", "iat_median", "iat_max", "t_first_down"],
    "bursts": ["n_bursts", "burst_len_mean", "burst_len_max", "burst_bytes_mean", "burst_bytes_max"],
    "first20": [f"pkt_{i:02d}" for i in range(20)],
}
FEATS = [c for cols in GROUPS.values() for c in cols]


# ----------------------------------------------------------------------------- helpers
def make_model(name: str, jobs: int):
    if name == "rf":
        return RandomForestClassifier(n_estimators=200, class_weight="balanced_subsample",
                                      n_jobs=jobs, random_state=SEED)
    return XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, subsample=0.9,
                         colsample_bytree=0.9, n_jobs=jobs, random_state=SEED,
                         eval_metric="mlogloss", tree_method="hist", verbosity=0)


def fit_predict(name, Xtr, ytr, Xte, jobs):
    """Returns (predicted labels, probabilities, class labels). Handles XGBoost's need for 0..K-1."""
    le = LabelEncoder().fit(ytr)
    model = make_model(name, jobs).fit(Xtr, le.transform(ytr))
    proba = model.predict_proba(Xte)
    return le.classes_[proba.argmax(1)], proba, le.classes_


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def group_folds(groups, k, seed):
    """Assign whole groups (domains) to k folds, round-robin after shuffling."""
    rng = np.random.default_rng(seed)
    uniq = np.array(sorted(set(groups)))
    rng.shuffle(uniq)
    fold_of = {g: i % k for i, g in enumerate(uniq)}
    return np.array([fold_of[g] for g in groups])


def cv_group(name, X, y, groups, k, seed, jobs):
    k = min(k, len(set(groups)))
    folds = group_folds(groups, k, seed)
    pred = np.empty(len(y), dtype=object)
    for f in range(k):
        te = folds == f
        tr = ~te
        if len(set(y[tr])) < 2:
            pred[te] = y[tr][0]
            continue
        pred[te] = fit_predict(name, X[tr], y[tr], X[te], jobs)[0]
    return pred


def loro(X, y, rep, jobs, want_top5=False):
    """Leave-one-repeat-out random-forest fingerprinting. Returns (pred, top5 hits)."""
    pred = np.empty(len(y), dtype=object)
    top5 = np.zeros(len(y), dtype=bool)
    for r in np.unique(rep):
        te = rep == r
        tr = ~te
        p, proba, classes = fit_predict("rf", X[tr], y[tr], X[te], jobs)
        pred[te] = p
        if want_top5:
            idx = np.argsort(-proba, axis=1)[:, :min(5, proba.shape[1])]
            yt = y[te]
            top5[te] = [yt[i] in set(classes[idx[i]]) for i in range(len(yt))]
    return pred, top5


def fingerprint_transfer(d: pd.DataFrame, train_reps, test_reps, jobs: int):
    """Train on some repeats, test on others (e.g. fixed-order repeats -> randomized-order repeats)."""
    tr = d[d["repeat"].isin(train_reps)]
    te = d[d["repeat"].isin(test_reps)]
    te = te[te.domain.isin(set(tr.domain))]
    if len(tr) < 20 or len(te) < 20 or tr.domain.nunique() < 5:
        return None
    pred, proba, classes = fit_predict("rf", tr[FEATS].to_numpy(float), tr.domain.to_numpy(),
                                       te[FEATS].to_numpy(float), jobs)
    y = te.domain.to_numpy()
    k = int((pred == y).sum())
    lo, hi = wilson(k, len(y))
    return {"n_train": len(tr), "n_test": len(y), "n_domains": int(tr.domain.nunique()),
            "chance_1_over_K": round(1 / tr.domain.nunique(), 4), "accuracy": round(k / len(y), 4),
            "ci95_lo": round(lo, 4), "ci95_hi": round(hi, 4)}


def fingerprint(d: pd.DataFrame, jobs: int, n_perm: int, cols=None, seed=SEED):
    """Domain fingerprinting for one (resolver, protocol[, workload]) slice."""
    cols = cols or FEATS
    d = d[d.groupby("domain")["repeat"].transform("nunique") >= 2]
    if d.domain.nunique() < 5 or d["repeat"].nunique() < 2:
        return None
    X = d[cols].to_numpy(float)
    y = d.domain.to_numpy()
    rep = d["repeat"].to_numpy()
    pred, top5 = loro(X, y, rep, jobs, want_top5=True)
    n = len(y)
    k = int((pred == y).sum())
    lo, hi = wilson(k, n)
    rng = np.random.default_rng(seed)
    # label-permutation baseline: shuffle domain labels, rerun the identical procedure
    perm = []
    for _ in range(n_perm):
        yp = rng.permutation(y)
        pp, _ = loro(X, yp, rep, jobs)
        perm.append(float(np.mean(pp == yp)))
    perm = np.array(perm) if perm else np.array([np.nan])
    return {
        "n": n, "n_domains": int(d.domain.nunique()), "repeats_per_domain": round(n / d.domain.nunique(), 1),
        "chance_1_over_K": round(1 / d.domain.nunique(), 4),
        "accuracy": round(k / n, 4), "ci95_lo": round(lo, 4), "ci95_hi": round(hi, 4),
        "top5": round(float(top5.mean()), 4),
        "macro_f1": round(f1_score(y, pred, average="macro"), 4),
        "perm_mean": round(float(np.nanmean(perm)), 4),
        "perm_p95": round(float(np.nanpercentile(perm, 95)), 4),
        "p_value": round((1 + int((perm >= k / n).sum())) / (1 + len(perm)), 4) if n_perm else np.nan,
    }


def ablation(eval_fn):
    base = eval_fn(FEATS)
    rows = [{"setting": "all features", "score": round(base, 4), "delta_vs_all": 0.0}]
    for g, cols in GROUPS.items():
        rest = [c for c in FEATS if c not in cols]
        for label, use in ((f"without {g}", rest), (f"only {g}", cols)):
            s = eval_fn(use)
            rows.append({"setting": label, "score": round(s, 4), "delta_vs_all": round(s - base, 4)})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_no data_\n"
    head = "| " + " | ".join(map(str, df.columns)) + " |\n"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |\n"
    body = "".join("| " + " | ".join(str(v) for v in row) + " |\n" for row in df.itertuples(index=False))
    return head + sep + body


# ----------------------------------------------------------------------------- experiments
def run_e1(df, a, out):
    sub = df[df.resolver.isin(["adguard", "quad9"])]
    tasks = {
        "3-way DoH/DoH3/DoQ": sub,
        "DoH3 vs DoQ": sub[sub.protocol.isin(["doh3", "doq"])],
        "3-way, Quad9 only": sub[sub.resolver == "quad9"],
        "3-way, AdGuard only": sub[sub.resolver == "adguard"],
    }
    rows, conf = [], None
    for tname, d in tasks.items():
        if d.protocol.nunique() < 2 or d.domain.nunique() < 5:
            continue
        X, y, g = d[FEATS].to_numpy(float), d.protocol.to_numpy(), d.domain.to_numpy()
        for m in a.models:
            accs, f1s = [], []
            for s in range(a.seeds):
                pred = cv_group(m, X, y, g, a.folds, SEED + s, a.jobs)
                accs.append(accuracy_score(y, pred))
                f1s.append(f1_score(y, pred, average="macro"))
                if s == 0 and m == "rf" and tname == "3-way DoH/DoH3/DoQ":
                    labels = sorted(set(y))
                    conf = (labels, confusion_matrix(y, pred, labels=labels))
            rows.append({"task": tname, "model": m, "n": len(y),
                         "majority_baseline": round(pd.Series(y).value_counts(normalize=True).max(), 4),
                         "accuracy": round(np.mean(accs), 4), "acc_sd_over_seeds": round(np.std(accs), 4),
                         "macro_f1": round(np.mean(f1s), 4)})
    res = pd.DataFrame(rows)
    res.to_csv(out / "E1_protocol_id.csv", index=False)
    if conf:
        labels, cm = conf
        fig, ax = plt.subplots(figsize=(4.2, 3.8))
        ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(len(labels)), labels)
        ax.set_yticks(range(len(labels)), labels)
        ax.set_xlabel("predicted")
        ax.set_ylabel("true")
        ax.set_title("E1 protocol identification (unseen domains)")
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
        fig.tight_layout()
        fig.savefig(out / "E1_confusion_3way.png", dpi=160)
        plt.close(fig)
    return res


def run_e2(df, a, out):
    rows = []
    for res, prots in (("quad9", ["doh", "doh3", "doq"]), ("google", ["doh", "doh3"])):
        for p in prots:
            r = fingerprint(df[(df.resolver == res) & (df.protocol == p)], a.jobs, a.perm)
            if r:
                rows.append({"resolver": res, "protocol": p, **r})
                print(f"    E2 {res}/{p}: acc={r['accuracy']:.3f} chance={r['perm_mean']:.3f} p={r['p_value']}")
    res_df = pd.DataFrame(rows)
    res_df.to_csv(out / "E2_fingerprinting.csv", index=False)
    if not res_df.empty:
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        labels = [f"{r.resolver}\n{r.protocol}" for r in res_df.itertuples()]
        acc = res_df.accuracy.to_numpy()
        err = np.array([acc - res_df.ci95_lo.to_numpy(), res_df.ci95_hi.to_numpy() - acc])
        ax.bar(labels, acc * 100, yerr=err * 100, capsize=4, color="#4c78a8", label="accuracy (95% CI)")
        ax.plot(range(len(labels)), res_df.perm_p95 * 100, "r_", markersize=22, mew=2,
                label="chance 95th percentile (label permutation)")
        ax.axhline(100 / max(res_df.n_domains.max(), 1), ls="--", c="gray", label="1/K random guess")
        ax.set_ylabel("domain fingerprinting accuracy (%)")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(out / "E2_accuracy.png", dpi=160)
        plt.close(fig)
    return res_df


def run_e2_order_control(df, a, out):
    """Is the fingerprinting signal an artifact of capture ORDER or TIME?
    Repeats < shuffled_from were captured in a fixed domain order; repeats >= shuffled_from in random order.
      (b) leave-one-repeat-out inside the randomized repeats only: order cannot help here.
      (c) train on fixed-order repeats, test on randomized, later repeats: tests order AND time stability."""
    k0 = a.shuffled_from
    rows = []
    for p in ["doh", "doh3", "doq"]:
        d = df[(df.resolver == "quad9") & (df.protocol == p)]
        rnd = d[d["repeat"] >= k0]
        if rnd["repeat"].nunique() >= 3:
            r = fingerprint(rnd, a.jobs, a.perm)
            if r:
                rows.append({"resolver": "quad9", "protocol": p, "test": f"(b) LORO within randomized repeats >= {k0}",
                             "n": r["n"], "accuracy": r["accuracy"], "ci95_lo": r["ci95_lo"],
                             "ci95_hi": r["ci95_hi"], "chance": r["perm_mean"], "p_value": r["p_value"]})
        t = fingerprint_transfer(d, list(range(k0)), sorted(set(d["repeat"]) - set(range(k0))), a.jobs)
        if t:
            rows.append({"resolver": "quad9", "protocol": p, "test": f"(c) train repeats < {k0}, test randomized repeats >= {k0}",
                         "n": t["n_test"], "accuracy": t["accuracy"], "ci95_lo": t["ci95_lo"],
                         "ci95_hi": t["ci95_hi"], "chance": t["chance_1_over_K"], "p_value": ""})
    res = pd.DataFrame(rows)
    res.to_csv(out / "E2b_order_control.csv", index=False)
    return res


def run_e3(df, a, out, e2):
    sub = df[df.resolver.isin(["adguard", "quad9"])]
    X_all, y, g = sub[FEATS].to_numpy(float), sub.protocol.to_numpy(), sub.domain.to_numpy()
    idx = {c: i for i, c in enumerate(FEATS)}

    def e1_score(cols):
        ci = [idx[c] for c in cols]
        pred = cv_group("rf", X_all[:, ci], y, g, a.folds, SEED, a.jobs)
        return f1_score(y, pred, average="macro")

    abl = ablation(e1_score)
    abl.insert(0, "task", "E1 protocol id (macro-F1)")
    parts = [abl]
    if e2 is not None and not e2.empty:
        for r in e2[e2.p_value <= 0.05].itertuples():
            d = df[(df.resolver == r.resolver) & (df.protocol == r.protocol)]

            def fp_score(cols, d=d):
                out_ = fingerprint(d, a.jobs, 0, cols=cols)
                return out_["accuracy"] if out_ else float("nan")

            ab = ablation(fp_score)
            ab.insert(0, "task", f"E2 fingerprinting {r.resolver}/{r.protocol} (accuracy)")
            parts.append(ab)
    abl_all = pd.concat(parts, ignore_index=True)
    abl_all.to_csv(out / "E3_ablation.csv", index=False)

    model = make_model("rf", a.jobs).fit(X_all, LabelEncoder().fit_transform(y))
    imp = pd.Series(model.feature_importances_, index=FEATS).sort_values(ascending=False)
    imp.head(20).round(4).rename("importance").to_csv(out / "E3_importance_E1.csv")
    grp = {gname: round(float(imp[cols].sum()), 4) for gname, cols in GROUPS.items()}
    return abl_all, imp.head(10).round(4).reset_index().rename(columns={"index": "feature", 0: "importance"}), grp


def run_e4(df, a, out):
    rows = []

    def add(name, tr, te, labels_note=""):
        for m in a.models:
            if tr.protocol.nunique() < 2 or te.empty:
                continue
            pred = fit_predict(m, tr[FEATS].to_numpy(float), tr.protocol.to_numpy(),
                               te[FEATS].to_numpy(float), a.jobs)[0]
            y = te.protocol.to_numpy()
            k = int((pred == y).sum())
            lo, hi = wilson(k, len(y))
            rows.append({"train": name[0], "test": name[1], "task": labels_note, "model": m, "n_test": len(y),
                         "accuracy": round(k / len(y), 4), "ci95": f"{lo:.3f}-{hi:.3f}",
                         "macro_f1": round(f1_score(y, pred, average="macro"), 4)})

    for tr_r, te_r in (("adguard", "quad9"), ("quad9", "adguard")):
        add((tr_r, te_r), df[df.resolver == tr_r], df[df.resolver == te_r], "3-way protocol id")
    dd = df[df.protocol.isin(["doh", "doh3"])]
    for te_r in ("google", "cloudflare"):
        add(("adguard+quad9", te_r), dd[dd.resolver.isin(["adguard", "quad9"])],
            dd[dd.resolver == te_r], "DoH vs DoH3 (unseen resolver)")
    res = pd.DataFrame(rows)
    res.to_csv(out / "E4_cross_resolver.csv", index=False)
    return res


def run_e5(df, a, out):
    q = df[df.resolver == "quad9"]
    rows = []
    for p in ["doh", "doh3", "doq"]:
        d = q[q.protocol == p]
        if d.workload.nunique() < 2 or d.domain.nunique() < 6:
            continue
        X, y, g = d[FEATS].to_numpy(float), d.workload.to_numpy(), d.domain.to_numpy()
        pred = cv_group("rf", X, y, g, a.folds, SEED, a.jobs)
        k = int((pred == y).sum())
        lo, hi = wilson(k, len(y))
        rows.append({"analysis": "workload classification (unseen domains)", "resolver": "quad9", "protocol": p,
                     "slice": "global vs india", "n": len(y),
                     "accuracy": round(k / len(y), 4), "ci95_lo": round(lo, 4), "ci95_hi": round(hi, 4),
                     "chance": round(pd.Series(y).value_counts(normalize=True).max(), 4), "p_value": ""})
    for wl in ("global", "india"):
        for p in ["doh", "doh3", "doq"]:
            r = fingerprint(q[(q.protocol == p) & (q.workload == wl)], a.jobs, max(a.perm // 2, 0))
            if r:
                rows.append({"analysis": "domain fingerprinting", "resolver": "quad9", "protocol": p,
                             "slice": wl, "n": r["n"], "accuracy": r["accuracy"], "ci95_lo": r["ci95_lo"],
                             "ci95_hi": r["ci95_hi"], "chance": r["perm_mean"], "p_value": r["p_value"]})
    res = pd.DataFrame(rows)
    res.to_csv(out / "E5_workloads.csv", index=False)
    return res


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "dataset.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    ap.add_argument("--jobs", type=int, default=2, help="CPU threads (keep low while capturing)")
    ap.add_argument("--perm", type=int, default=20, help="label permutations per fingerprint test")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seeds", type=int, default=3, help="repeated group-fold splits for E1")
    ap.add_argument("--shuffled-from", type=int, default=3,
                    help="first repeat that was captured in randomized order (probe_and_capture --shuffle-from)")
    ap.add_argument("--quick", action="store_true", help="tiny settings for a smoke test")
    a = ap.parse_args()
    if a.quick:
        a.perm, a.seeds = 4, 1
    a.models = ["rf"] + (["xgb"] if HAVE_XGB else [])
    a.out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.dataset)
    missing = [c for c in FEATS + ["protocol", "resolver", "domain", "workload", "repeat"] if c not in df.columns]
    if missing:
        sys.exit(f"dataset.csv is missing columns: {missing}")
    df = df.dropna(subset=FEATS).reset_index(drop=True)

    overview = df.groupby(["resolver", "protocol"]).agg(
        rows=("domain", "size"), domains=("domain", "nunique"),
        max_repeat=("repeat", "max")).reset_index()
    print("Dataset overview:\n", overview.to_string(index=False), "\n")
    t0 = time.time()

    print("[E1] protocol identification ..."); e1 = run_e1(df, a, a.out)
    print("[E2] domain fingerprinting ..."); e2 = run_e2(df, a, a.out)
    print("[E2b] order/time control ..."); e2b = run_e2_order_control(df, a, a.out)
    print("[E3] feature importance + ablation ..."); e3, top, grp = run_e3(df, a, a.out, e2)
    print("[E4] cross-resolver transfer ..."); e4 = run_e4(df, a, a.out)
    print("[E5] workloads ..."); e5 = run_e5(df, a, a.out)

    notes = (
        "## How to read these tables\n"
        "- **E1/E4/E5a** use unseen-domain or unseen-resolver test data. `majority_baseline`/`chance` is what a "
        "trivial classifier gets.\n"
        "- **E2/E5b** accuracy is compared with `perm_mean` (accuracy when labels are shuffled) and `perm_p95`; "
        "a result counts as real leakage only if it clearly exceeds `perm_p95` (small `p_value`) and its "
        "95% interval excludes the chance level.\n"
        "- Accuracy *below* 1/K is noise, not evidence of extra privacy.\n"
        "- Ablation deltas of about 1-2 points are within run-to-run noise; only large drops are meaningful.\n"
    )
    summary = (
        "# Pilot results\n\n## Dataset\n" + md_table(overview) + "\n## E1 Protocol identification\n" + md_table(e1)
        + "\n## E2 Domain fingerprinting (one resolver at a time)\n" + md_table(e2)
        + "\n## E2b Order / time control (is the fingerprint an artifact?)\n" + md_table(e2b)
        + "\n## E3 Ablation\n" + md_table(e3) + "\nTop RF importances (E1):\n\n" + md_table(top)
        + f"\nImportance by feature group: {grp}\n\n## E4 Cross-resolver\n" + md_table(e4)
        + "\n## E5 Workloads\n" + md_table(e5) + "\n" + notes
    )
    (a.out / "summary.md").write_text(summary, encoding="utf-8")
    print(f"\nDone in {time.time() - t0:.0f}s. Open {a.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())