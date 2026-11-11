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
            smoke_rows = [row for row in rows if row.get("batch", "").lower() == "smoke"]
            print(f"\n    Smoke summary: {len(smoke_rows)} manifest rows; "
                  f"{sum(row.get('status') == 'ok' for row in smoke_rows)} successful")
            if smoke_rows:
                print("    Smoke rows are excluded from analysis counts.")
            rows = [row for row in rows if row.get("batch", "").lower() != "smoke"]
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
        workload_counts = {
            name: len((ROOT / "data" / "workloads" / f"{name}.txt").read_text(encoding="utf-8").split())
            for name in ("global", "india") if (ROOT / "data" / "workloads" / f"{name}.txt").exists()
        }
        expected_domains = sum(workload_counts.values())
        print(f"    DoH/3 unique domains: {doh3_df.domain.nunique()} ({expected_domains} expected from frozen workloads)")
        print(f"    DoH/3 repeats captured: 0 to {doh3_df.repeat.max()}")

        print(f"\n    DoH/3 rows per resolver:")
        for res, count in doh3_df.groupby("resolver").size().items():
            print(f"      - {res.title():12s}: {count} rows")

        if manifest.exists():
            manifest_df = pd.read_csv(manifest)
            if "batch" in manifest_df.columns:
                manifest_df = manifest_df[manifest_df["batch"].fillna("").str.lower() != "smoke"]
            success = manifest_df[manifest_df["status"] == "ok"].copy()
            success["latency_s"] = pd.to_numeric(success["latency_s"], errors="coerce")
            dataset_paths = set(df.get("pcap_path", pd.Series(dtype=str)).dropna().astype(str))
            print("\n[3b] Manifest-to-dataset drop reasons by resolver and protocol:")
            for (resolver, protocol), group in success.groupby(["resolver", "protocol"]):
                slow = int((group["latency_s"] > 1.5).sum())
                few_packets = int((pd.to_numeric(group["packets"], errors="coerce") < 2).sum())
                missing_pcap = int((~group["pcap_path"].astype(str).isin(dataset_paths)).sum())
                processed = int(((df["resolver"] == resolver) & (df["protocol"] == protocol)).sum())
                print(f"      - {resolver}/{protocol}: manifest_ok={len(group)}, dataset={processed}, "
                      f"latency_gt_1.5s={slow}, too_few_packets={few_packets}, missing_or_not_extracted={missing_pcap}")
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
    print("RECOMMENDED RUN ORDER")
    print("=" * 65)
    print("Step 1: Check status:      python src\\data_status.py")
    print("Step 2: Capture dry-run:   python src\\probe_and_capture.py --network dryrun --dry-run")
    print("Step 3: Collect:           scripts\\run_overnight.ps1")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
