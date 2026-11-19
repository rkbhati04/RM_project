"""Equal-class Global accuracy for comparison with the 79-domain India workload."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from encdns.analysis.fingerprinting import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true",
                        help="Use two draws, one fit seed and no null fits.")
    args = parser.parse_args()
    run = ROOT / "results/airtel_shared_20261116"
    dataset = ROOT / "data/processed/dataset_v2_shared.csv"
    metadata = json.loads((run / "run_metadata.json").read_text())
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != metadata["dataset_sha256"]:
        raise ValueError("Shared-run dataset checksum mismatch")
    frame = pd.read_csv(dataset)
    global_rows = frame[frame.workload == "global"]
    domains = sorted(global_rows.domain.unique())
    if len(domains) != 99:
        raise ValueError("Expected 99 shared Global domains")

    draws = 2 if args.smoke else 20
    scores = []
    for draw in range(draws):
        selected = np.random.default_rng(17 + draw).choice(domains, 79, replace=False)
        subset = global_rows[global_rows.domain.isin(selected)]
        for (resolver, protocol), group in subset.groupby(["resolver", "protocol"]):
            result = evaluate(group, [17] if args.smoke else [17, 42, 101],
                              0, 100)
            if not result or result["n"] != 790 or result["domains"] != 79:
                raise ValueError(f"Incomplete draw {draw} for {resolver}/{protocol}")
            scores.append((resolver, protocol, result["accuracy"]))
    frame = pd.DataFrame(scores, columns=["resolver", "protocol", "accuracy"])
    grouped = frame.groupby(["resolver", "protocol"]).accuracy
    summary = grouped.agg(draws="count", mean_accuracy="mean",
                          draw_p025=lambda x: x.quantile(0.025),
                          draw_p975=lambda x: x.quantile(0.975))
    if len(summary) != 8 or not summary.draws.eq(draws).all():
        raise ValueError("Incomplete resolver/protocol coverage")
    output = run / ("rq5_subsampled_smoke.csv" if args.smoke else "rq5_subsampled.csv")
    summary.to_csv(output)
    print(f"{draws} draws across all eight slices written to {output}")


if __name__ == "__main__":
    main()
