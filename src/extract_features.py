"""Turn captured pcaps into one feature row per query -> data/processed/dataset.csv

Uses only the standard library plus tshark (Wireshark). Features are built from
packet SIZES, TIMING, DIRECTION and BURSTS only. Ports, IPs and the transport
protocol are deliberately NOT features: DoQ uses UDP/853 while DoH/3 uses
UDP/443, so a port would give the label away and prove nothing about leakage.

Example:
    python src\\extract_features.py
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import os
import shutil
import statistics as st
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
N_FIRST = 20  # signed sizes of the first N packets (+ = client->server, - = server->client)
LABELS = ["network", "resolver", "protocol", "workload", "domain", "repeat", "pcap_path"]


def find_tshark(wireshark_dir: str) -> str:
    found = shutil.which("tshark")
    if found:
        return found
    search_dirs = [wireshark_dir, "/opt/homebrew/bin", "/usr/local/bin", r"C:\Program Files\Wireshark"]
    for d in search_dirs:
        if d and Path(d).is_dir():
            cand = shutil.which("tshark", path=d)
            if cand:
                return cand
    dirs = [d.strip().strip('"') for d in os.environ.get("PATH", "").split(os.pathsep)]
    found = shutil.which("tshark", path=os.pathsep.join(dirs))
    if not found:
        sys.exit("Cannot find tshark. Pass --wireshark-dir.")
    return found


def read_packets(tshark: str, pcap: Path) -> list[tuple[float, int, str]]:
    """Return [(relative_time, frame_len, src_ip)] for every packet."""
    out = subprocess.run(
        [tshark, "-r", str(pcap), "-T", "fields", "-E", "separator=,", "-E", "occurrence=f",
         "-e", "frame.time_relative", "-e", "frame.len", "-e", "ip.src", "-e", "ipv6.src"],
        capture_output=True, text=True,
    ).stdout
    pkts = []
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) < 4 or not parts[0] or not parts[1]:
            continue
        src = parts[2] or parts[3]
        if src:
            pkts.append((float(parts[0]), int(parts[1]), norm_ip(src)))
    return pkts


def norm_ip(text: str) -> str:
    """Canonical IP text (drops IPv6 zone ids like %12 and formatting differences)."""
    text = text.strip().split("%")[0]
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return text


def _mean(xs):
    return st.fmean(xs) if xs else 0.0


def _std(xs):
    return st.pstdev(xs) if len(xs) > 1 else 0.0


def compute_features(pkts: list[tuple[float, int, str]], server_ips: set[str]) -> dict:
    """pkts must be time-ordered. Direction: -1 when the source is a resolver IP."""
    t0 = pkts[0][0]
    times = [p[0] - t0 for p in pkts]
    sizes = [p[1] for p in pkts]
    dirs = [-1 if p[2] in server_ips else 1 for p in pkts]

    up = [s for s, d in zip(sizes, dirs) if d == 1]
    down = [s for s, d in zip(sizes, dirs) if d == -1]
    iats = [b - a for a, b in zip(times, times[1:])]

    # bursts = runs of consecutive packets in the same direction
    bursts_len, bursts_bytes = [], []
    run_len, run_bytes = 1, sizes[0]
    for i in range(1, len(pkts)):
        if dirs[i] == dirs[i - 1]:
            run_len += 1
            run_bytes += sizes[i]
        else:
            bursts_len.append(run_len)
            bursts_bytes.append(run_bytes)
            run_len, run_bytes = 1, sizes[i]
    bursts_len.append(run_len)
    bursts_bytes.append(run_bytes)

    t_first_down = next((t for t, d in zip(times, dirs) if d == -1), 0.0)
    feats = {
        "n_pkts": len(pkts), "n_up": len(up), "n_down": len(down),
        "bytes_up": sum(up), "bytes_down": sum(down), "bytes_total": sum(sizes),
        "ratio_bytes_down_up": round(sum(down) / sum(up), 4) if up and sum(up) else 0.0,
        "duration": round(times[-1], 6),
        "up_mean": round(_mean(up), 3), "up_std": round(_std(up), 3), "up_max": max(up, default=0),
        "down_mean": round(_mean(down), 3), "down_std": round(_std(down), 3), "down_max": max(down, default=0),
        "iat_mean": round(_mean(iats), 6), "iat_std": round(_std(iats), 6),
        "iat_median": round(st.median(iats), 6) if iats else 0.0, "iat_max": round(max(iats, default=0.0), 6),
        "t_first_down": round(t_first_down, 6),
        "n_bursts": len(bursts_len), "burst_len_mean": round(_mean(bursts_len), 3),
        "burst_len_max": max(bursts_len), "burst_bytes_mean": round(_mean(bursts_bytes), 3),
        "burst_bytes_max": max(bursts_bytes),
    }
    signed = [s * d for s, d in zip(sizes, dirs)][:N_FIRST]
    signed += [0] * (N_FIRST - len(signed))
    for i, v in enumerate(signed):
        feats[f"pkt_{i:02d}"] = v
    return feats


def load_manifest(path: Path) -> list[dict]:
    """Newest row per pcap wins (a pcap that was re-captured is overwritten on disk),
    then only successful captures are kept."""
    latest: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            latest[row["pcap_path"]] = row
    return [r for r in latest.values() if r.get("status") == "ok"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=RAW / "manifest.csv")
    ap.add_argument("--output", type=Path, default=OUT / "dataset.csv")
    ap.add_argument("--wireshark-dir", default=r"C:\\Program Files\\Wireshark")
    ap.add_argument("--max-latency", type=float, default=1.5,
                    help="drop queries slower than this: the fixed 3 s capture window (1 s warmup) "
                         "may have cut them off")
    args = ap.parse_args()

    tshark = find_tshark(args.wireshark_dir)
    rows = load_manifest(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    written, skipped = 0, Counter()
    skipped_detail: list[str] = []
    per_group: Counter = Counter()
    pkts_by_proto: dict[str, list[int]] = {}
    writer = None
    with args.output.open("w", newline="", encoding="utf-8") as out:
        for i, row in enumerate(rows, 1):
            if float(row.get("latency_s") or 99) > args.max_latency:
                skipped["slow_query_possibly_truncated"] += 1
                continue
            pcap = ROOT / row["pcap_path"].replace("\\", "/")
            if not pcap.exists():
                skipped["missing_pcap"] += 1
                continue
            pkts = read_packets(tshark, pcap)
            if len(pkts) < 3:
                skipped["too_few_packets"] += 1
                continue
            servers = {norm_ip(x) for x in row["server_ips"].split(";") if x}
            if not any(p[2] in servers for p in pkts):
                skipped["no_server_packets"] += 1  # direction would be wrong, so skip
                skipped_detail.append(
                    f"{row['pcap_path']} ({row['resolver']}/{row['protocol']}, {len(pkts)} pkts) "
                    f"sources seen: {sorted({p[2] for p in pkts})}")
                continue
            feats = compute_features(pkts, servers)
            record = {k: row[k] for k in LABELS} | {"latency_s": row["latency_s"]} | feats
            if writer is None:
                writer = csv.DictWriter(out, fieldnames=list(record))
                writer.writeheader()
            writer.writerow(record)
            written += 1
            per_group[(row["resolver"], row["protocol"])] += 1
            pkts_by_proto.setdefault(row["protocol"], []).append(len(pkts))
            if i % 100 == 0:
                print(f"  {i}/{len(rows)} pcaps processed")

    print(f"\nWrote {written} rows to {args.output}")
    if skipped:
        print("Skipped:", dict(skipped))
        for line in skipped_detail[:10]:
            print("  -", line)
    print("\nRows per resolver x protocol:")
    for (res, proto), n in sorted(per_group.items()):
        print(f"  {res:10s} {proto:5s} {n}")
    print("\nMean packets per protocol (sanity check):")
    for proto, xs in sorted(pkts_by_proto.items()):
        print(f"  {proto:5s} {sum(xs) / len(xs):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())