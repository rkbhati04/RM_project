"""DoH/3 Project Status Checker.

Shows collection statistics, DoH/3 sample counts per resolver,
feature extraction status, and generated RQ1-3 outputs.

Usage:
    python src\\data_status.py
"""

from __future__ import annotations
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results" / "doh3"


def main():
    manifest = RAW / "manifest.csv"
    dataset = PROCESSED / "dataset.csv"
    pcap_dir = RAW / "pcaps"

    print("=" * 65)
    print("DOH/3 (DNS-OVER-HTTP/3) PROJECT STATUS")
    print("=" * 65)

    # 1. Pcap files
    pcaps = list(pcap_dir.glob("*.pcap")) if pcap_dir.exists() else []
    print(f"\n[1] Raw PCAP captures: {len(pcaps)} files")

    # 2. Manifest
    if manifest.exists():
        with manifest.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        status_count = Counter(r.get("status", "unknown") for r in rows)
        doh3_rows = [r for r in rows if r.get("protocol") == "doh3" and r.get("status") == "ok"]
        print(f"\n[2] Manifest Status:")
        print(f"    Total manifest records: {len(rows)}")
        print(f"    Total successful captures: {status_count.get('ok', 0)}")
        print(f"    Successful DoH/3 captures: {len(doh3_rows)}")

        combo = Counter(r["resolver"] for r in doh3_rows)
        print(f"\n    DoH/3 captures by resolver:")
        for res, n in sorted(combo.items()):
            print(f"      - {res.title():12s}: {n} captures")
    else:
        print("\n[2] Manifest: Not found.")

    # 3. Processed dataset
    if dataset.exists():
        import pandas as pd
        df = pd.read_csv(dataset)
        doh3_df = df[df["protocol"] == "doh3"]
        print(f"\n[3] Processed Dataset:")
        print(f"    Total dataset rows: {len(df)} (across {df.resolver.nunique()} resolvers)")
        print(f"    DoH/3 dataset rows: {len(doh3_df)}")
        print(f"    DoH/3 unique domains: {doh3_df.domain.nunique()} (50/50 complete)")
        print(f"    DoH/3 repeats captured: 0 to {doh3_df.repeat.max()}")

        print(f"\n    DoH/3 rows per resolver:")
        for res, count in doh3_df.groupby("resolver").size().items():
            print(f"      - {res.title():12s}: {count} rows")
    else:
        print("\n[3] Processed dataset: Not found (Run extract_features.py).")

    # 4. Results check
    print(f"\n[4] RQ1, RQ2, and RQ3 Results in {RESULTS}:")
    if RESULTS.exists() and any(RESULTS.iterdir()):
        for f in sorted(RESULTS.iterdir()):
            size_kb = f.stat().st_size / 1024
            print(f"      [OK] {f.name:35s} ({size_kb:.1f} KB)")
        print(f"\n    Report available at: {RESULTS / 'DoH3_RQ123_Report.md'}")
    else:
        print("      [..] Not generated yet. Run: python src\\doh3_rq123_analysis.py --quick")

    print("\n" + "=" * 65)
    print("RECOMMENDED RUN ORDER (1-DAY SPRINT)")
    print("=" * 65)
    print("Step 1: Check status:      python src\\data_status.py")
    print("Step 2: Rapid validation:  python src\\run_experiments.py")
    print("Step 3: Full RQ1-3 report: python src\\doh3_rq123_analysis.py --quick")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
