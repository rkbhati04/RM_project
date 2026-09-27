"""Which features carry DOMAIN information, per protocol? (supports RQ3 and explains E2)

For each protocol (one resolver at a time) this computes the ANOVA F-statistic of every
feature against the domain label: F = variance BETWEEN domains / variance WITHIN a domain's
repeats. A large F means the feature is stable for one domain and different across domains,
which is exactly what a fingerprinting attacker needs. Small F everywhere means the flow
shape is dominated by run-to-run noise.

Example:
    python src\\feature_signal.py --resolver quad9
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_selection import f_classif

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "volume": ["n_pkts", "n_up", "n_down", "bytes_up", "bytes_down", "bytes_total", "ratio_bytes_down_up"],
    "size_stats": ["up_mean", "up_std", "up_max", "down_mean", "down_std", "down_max"],
    "timing": ["duration", "iat_mean", "iat_std", "iat_median", "iat_max", "t_first_down"],
    "bursts": ["n_bursts", "burst_len_mean", "burst_len_max", "burst_bytes_mean", "burst_bytes_max"],
    "first20": [f"pkt_{i:02d}" for i in range(20)],
}
FEATS = [c for cols in GROUPS.values() for c in cols]
GROUP_OF = {f: g for g, cols in GROUPS.items() for f in cols}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "dataset.csv")
    ap.add_argument("--resolver", default="quad9")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "feature_signal.csv")
    a = ap.parse_args()

    df = pd.read_csv(a.dataset)
    df = df[df.resolver == a.resolver].dropna(subset=FEATS)
    rows = []
    for proto, s in df.groupby("protocol"):
        s = s[s.groupby("domain")["domain"].transform("size") >= 2]
        if s.domain.nunique() < 5:
            continue
        F, _ = f_classif(s[FEATS].to_numpy(float), s.domain.to_numpy())
        for f, v in zip(FEATS, np.nan_to_num(F)):
            rows.append({"resolver": a.resolver, "protocol": proto, "feature": f,
                         "group": GROUP_OF[f], "F": round(float(v), 2)})
    out = pd.DataFrame(rows)
    if out.empty:
        print("Not enough repeated domains for this resolver.")
        return
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)

    for proto, s in out.groupby("protocol"):
        print(f"\n=== {a.resolver} / {proto} ===")
        print("Top 6 features by F:")
        print(s.sort_values("F", ascending=False).head(6)[["feature", "group", "F"]].to_string(index=False))
        print("Median F by feature group:")
        print(s.groupby("group")["F"].median().round(2).sort_values(ascending=False).to_string())
    print("\nRule of thumb: median F near 1 = no domain signal; well above 2 = stable, domain-specific feature.")
    print(f"Saved {a.out}")


if __name__ == "__main__":
    main()