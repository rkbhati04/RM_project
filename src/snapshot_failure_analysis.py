"""Read-only failure concentration and common-domain analysis."""
from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    with args.manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    slices: dict[tuple[str, str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in rows:
        if int(row.get("repeat") or -1) < 8:
            continue
        key = (row["resolver"], row["protocol"], row["workload"])
        domain = row["domain"]
        if row.get("status") == "ok":
            slices[key][domain].add(row["repeat"])
    eligible = {key: {domain for domain, repeats in domains.items() if len(repeats) >= args.k}
                for key, domains in slices.items()}
    below_sets = [{domain for domain, repeats in domains.items() if len(repeats) < args.k}
                  for domains in slices.values()]
    all_sets = list(eligible.values())
    intersection = set.intersection(*all_sets) if all_sets else set()
    union = set.union(*all_sets) if all_sets else set()
    below_intersection = set.intersection(*below_sets) if below_sets else set()
    below_union = set.union(*below_sets) if below_sets else set()
    rows_out = []
    for key in sorted(slices):
        counts = slices[key]
        below = {domain for domain, repeats in counts.items() if len(repeats) < args.k}
        rows_out.append({
            "resolver": key[0], "protocol": key[1], "workload": key[2],
            "domains_seen": len(counts), "domains_below_k": len(below),
            "eligible_domains": len(eligible.get(key, set())),
            "below_k_examples": ";".join(sorted(below)[:20]),
            "success_rate_note": "status-based; see health.csv for hourly rates",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_out[0]) if rows_out else
                                ["resolver", "protocol", "workload", "domains_seen",
                                 "domains_below_k", "eligible_domains", "below_k_examples",
                                 "success_rate_note"])
        writer.writeheader()
        writer.writerows(rows_out)
    seed = 17
    random.seed(seed)
    (args.output.with_name("failure_policy.txt")).write_text(
        f"k={args.k}\n"
        f"slice_count={len(eligible)}\n"
        f"intersection_domains={len(intersection)}\n"
        f"union_domains={len(union)}\n"
        f"below_k_intersection={len(below_intersection)}\n"
        f"below_k_union={len(below_union)}\n"
        f"policy=intersection of domains meeting k in every slice, then sample exactly k repeats per domain with seed {seed}\n"
        f"keeps={len(intersection)} domains; each slice uses {args.k} repeats per kept domain\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
