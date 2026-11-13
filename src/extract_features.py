"""Turn captured pcaps into one feature row per query -> data/processed/dataset.csv

Uses only the standard library plus tshark (Wireshark). Features are built from
packet SIZES, TIMING, DIRECTION and BURSTS only. Ports, IPs and transport
identifiers are deliberately NOT features, ensuring the model learns pure
side-channel traffic metadata leakage without trivial shortcuts.

Example:
    python src\\extract_features.py
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import os
import shutil
import statistics as st
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def read_packets(tshark: str, pcap: Path, timeout: float = 20.0) -> list[tuple[float, int, str]]:
    """Return [(relative_time, frame_len, src_ip)] for every packet."""
    completed = subprocess.run(
        [tshark, "-r", str(pcap), "-T", "fields", "-E", "separator=,", "-E", "occurrence=f",
         "-e", "frame.time_relative", "-e", "frame.len", "-e", "ip.src", "-e", "ipv6.src"],
        capture_output=True, text=True, timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip()[:200] or "tshark failed")
    out = completed.stdout
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


def load_manifest(path: Path) -> tuple[list[dict], list[dict[str, str]]]:
    """Newest row per pcap wins (a pcap that was re-captured is overwritten on disk),
    then only successful captures are kept."""
    latest: dict[str, dict] = {}
    drops: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if len(header) != len(set(header)):
            raise ValueError("Manifest has duplicate column names")
        for line_number, values in enumerate(reader, 2):
            if len(values) != len(header):
                drops.append({"pcap_path": "", "reason": "incomplete_manifest_row",
                              "detail": f"line {line_number}: {len(values)} fields; expected {len(header)}"})
                continue
            row = dict(zip(header, values))
            latest[row["pcap_path"]] = row
    return [r for r in latest.values()
            if r.get("status") == "ok" and r.get("batch", "").lower() != "smoke"], drops


def process_capture(item: tuple[dict, str, float, float, Path]) -> dict:
    row, tshark, timeout, max_latency, data_root = item
    pcap = data_root / row["pcap_path"].replace("\\", "/")
    result = {"pcap_path": row["pcap_path"], "reason": "", "row": row, "features": None}
    if not pcap.exists():
        result["reason"] = "missing_file"
        return result
    if float(row.get("latency_s") or 99) > max_latency:
        result["reason"] = "slow_query"
        return result
    try:
        pkts = read_packets(tshark, pcap, timeout)
    except subprocess.TimeoutExpired:
        result["reason"] = "timeout"
        return result
    except (OSError, ValueError, RuntimeError) as exc:
        result["reason"] = "tshark_failure"
        result["detail"] = str(exc)[:200]
        return result
    if len(pkts) < 3:
        result["reason"] = "too_few_packets"
        return result
    servers = {norm_ip(x) for x in row["server_ips"].split(";") if x}
    if not any(p[2] in servers for p in pkts):
        result["reason"] = "server_packets_missing"
        return result
    result["features"] = compute_features(pkts, servers)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=RAW / "manifest.csv")
    ap.add_argument("--output", type=Path, default=OUT / "dataset.csv")
    ap.add_argument("--wireshark-dir", default=r"C:\\Program Files\\Wireshark")
    ap.add_argument("--max-latency", type=float, default=1.5,
                    help="drop queries slower than this: the fixed 3 s capture window (1 s warmup) "
                         "may have cut them off")
    ap.add_argument("--timeout", type=float, default=20.0, help="tshark timeout per PCAP")
    ap.add_argument("--workers", type=int, default=4, help="worker processes (2-4 recommended)")
    ap.add_argument("--limit", type=int, help="maximum manifest PCAPs to process")
    ap.add_argument("--cache", type=Path, help="JSON cache path; defaults beside output")
    ap.add_argument("--drops", type=Path, help="drop-reason CSV; defaults beside output")
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="repository root used to resolve manifest PCAP paths")
    args = ap.parse_args()

    tshark = find_tshark(args.wireshark_dir)
    rows, manifest_drops = load_manifest(args.manifest)
    if args.limit is not None:
        rows = rows[:args.limit]
    args.workers = max(2, min(args.workers, 4))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cache_path = args.cache or args.output.with_name(".extract_cache.json")
    drops_path = args.drops or args.output.with_name("extract_drops.csv")
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        cache = {}

    written, skipped = 0, Counter()
    per_group: Counter = Counter()
    pkts_by_proto: dict[str, list[int]] = {}
    results = []
    pending = []
    for row in rows:
        pcap = args.root / row["pcap_path"].replace("\\", "/")
        key = row["pcap_path"]
        try:
            stat = pcap.stat()
            cache_key = f"{key}|{stat.st_size}|{stat.st_mtime_ns}"
        except OSError:
            cache_key = f"{key}|missing"
        cached = cache.get(cache_key)
        if cached is not None:
            results.append(cached)
        else:
            pending.append((row, tshark, args.timeout, args.max_latency, args.root))
    batch_size = 500
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for batch_start in range(0, len(pending), batch_size):
            batch = pending[batch_start:batch_start + batch_size]
            futures = [pool.submit(process_capture, item) for item in batch]
            for future in as_completed(futures):
                result = future.result()
                cache_key = result["pcap_path"]
                pcap = args.root / cache_key.replace("\\", "/")
                try:
                    stat = pcap.stat()
                    cache[f"{cache_key}|{stat.st_size}|{stat.st_mtime_ns}"] = result
                except OSError:
                    pass
                results.append(result)
            print(f"Processed {min(batch_start + batch_size, len(pending))}/{len(pending)} pending PCAPs",
                  flush=True)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    drop_rows = list(manifest_drops)
    for result in results:
        if result.get("reason"):
            skipped[result["reason"]] += 1
            drop_rows.append({"pcap_path": result["pcap_path"], "reason": result["reason"],
                              "detail": result.get("detail", "")})
    writer = None
    with args.output.open("w", newline="", encoding="utf-8") as out:
        for result in results:
            if not result.get("features"):
                continue
            row = result["row"]
            feats = result["features"]
            record = {k: row[k] for k in LABELS} | {"latency_s": row["latency_s"]} | feats
            if writer is None:
                writer = csv.DictWriter(out, fieldnames=list(record))
                writer.writeheader()
            writer.writerow(record)
            written += 1
            per_group[(row["resolver"], row["protocol"])] += 1
            pkts_by_proto.setdefault(row["protocol"], []).append(feats["n_pkts"])

    print(f"\nWrote {written} rows to {args.output}")
    if skipped:
        print("Skipped:", dict(skipped))
    with drops_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pcap_path", "reason", "detail"])
        writer.writeheader()
        writer.writerows(drop_rows)
    print(f"Drop reasons: {drops_path}")
    print("\nRows per resolver x protocol:")
    for (res, proto), n in sorted(per_group.items()):
        print(f"  {res:10s} {proto:5s} {n}")
    print("\nMean packets per protocol (sanity check):")
    for proto, xs in sorted(pkts_by_proto.items()):
        print(f"  {proto:5s} {sum(xs) / len(xs):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
