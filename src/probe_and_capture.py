"""Vertical slice: probe resolver x protocol support and capture one labelled
query per combination (one fresh connection, one pcap, one manifest row each).

Windows-native: uses dumpcap/tshark (Wireshark + Npcap) and the `q` DNS client.

Example:
    dumpcap -D                       # list interfaces, pick the Airtel one
    python src\\probe_and_capture.py --iface "Wi-Fi" --network airtel
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
WORKLOADS = ROOT / "data" / "workloads"

# host + DoH path per resolver. URIs for every protocol are generated, and the
# probe reveals which ones the resolver actually answers.
RESOLVERS = {
    "adguard": ("dns.adguard-dns.com", "/dns-query"),
    "cloudflare": ("cloudflare-dns.com", "/dns-query"),
    "google": ("dns.google", "/dns-query"),
    "quad9": ("dns.quad9.net", "/dns-query"),
}
PROTOCOLS = ("doh", "doh3", "doq")

MANIFEST_FIELDS = [
    "timestamp", "network", "resolver", "protocol", "workload", "domain",
    "repeat", "returncode", "latency_s", "packets", "bytes", "status",
    "server_ips", "pcap_path", "note",
]


def uri_for(protocol: str, host: str, path: str) -> tuple[str, list[str]]:
    """Return (server URI, extra q flags). q has no h3:// scheme: DoH/3 is
    https:// plus --http3, and DoH is pinned to HTTP/2 with --http2."""
    if protocol == "doh":
        return f"https://{host}{path}", ["--http2"]
    if protocol == "doh3":
        return f"https://{host}{path}", ["--http3"]
    return f"quic://{host}", []  # doq


def find_tool(name: str, wireshark_dir: str, explicit: str | None = None) -> str:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return str(p.resolve())
        sys.exit(f"{name} not found at {explicit}")
    # Check local workspace bin/
    local_bin = ROOT / "bin" / name
    if local_bin.is_file():
        return str(local_bin.resolve())
    # Check standard which
    found = shutil.which(name)
    if found:
        return found
    # Check common install locations across macOS, Linux, and Windows
    search_dirs = [wireshark_dir, "/opt/homebrew/bin", "/usr/local/bin", r"C:\Program Files\Wireshark"]
    for d in search_dirs:
        if d and Path(d).is_dir():
            cand = shutil.which(name, path=d)
            if cand:
                return cand
    dirs = [d.strip().strip('"') for d in os.environ.get("PATH", "").split(os.pathsep)]
    found = shutil.which(name, path=os.pathsep.join(dirs))
    if not found:
        sys.exit(f"Cannot find {name}. Pass its full path (--q-path) or fix PATH.")
    return found



def resolve_ips(host: str) -> list[str]:
    """All A/AAAA addresses of the resolver host (bootstrap, done before capture)."""
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def build_filter(ips: list[str]) -> str:
    hosts = " or ".join(f"host {ip}" for ip in ips)
    return f"({hosts}) and (udp port 443 or udp port 853 or tcp port 443)"


def count_packets(tshark: str, pcap: Path) -> tuple[int, int]:
    out = subprocess.run(
        [tshark, "-r", str(pcap), "-T", "fields", "-e", "frame.len"],
        capture_output=True, text=True,
    ).stdout.split()
    sizes = [int(x) for x in out if x.isdigit()]
    return len(sizes), sum(sizes)


def capture_one(dumpcap, q, iface, bpf, uri, extra, domain, pcap, seconds, warmup):
    cap = subprocess.Popen(
        [dumpcap, "-i", iface, "-f", bpf, "-F", "pcap", "-w", str(pcap),
         "-a", f"duration:{seconds}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    time.sleep(warmup)  # let dumpcap start listening
    t0 = time.time()
    note = ""
    # Strip any HTTP proxy environment variables so q queries resolvers directly over the network interface
    q_env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    try:
        r = subprocess.run([q, domain, "A", f"@{uri}", *extra], capture_output=True,
                           text=True, timeout=20, env=q_env)
        rc, latency = r.returncode, time.time() - t0
        if rc != 0:
            note = (r.stderr or r.stdout).strip().replace("\n", " ")[:200]
    except subprocess.TimeoutExpired:
        rc, latency, note = -1, time.time() - t0, "q timeout"
    try:
        _, cap_err = cap.communicate(timeout=seconds + 15)  # timed stop flushes the pcap
    except subprocess.TimeoutExpired:
        cap.kill()
        _, cap_err = cap.communicate()
    if not note and cap.returncode != 0:
        note = "dumpcap: " + (cap_err or "").strip().replace("\n", " ")[:200]
    return rc, latency, note, int(t0)


def load_done(manifest: Path, max_latency: float) -> set[str]:
    """pcap paths already captured completely (used by --resume). The newest row
    per pcap wins, and slow queries count as NOT done so they get re-captured."""
    if not manifest.exists():
        return set()
    latest: dict[str, dict] = {}
    with manifest.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            latest[r["pcap_path"]] = r
    return {
        path for path, r in latest.items()
        if r.get("status") == "ok" and float(r.get("latency_s") or 99) <= max_latency
    }


def main() -> int:
    default_iface = "en0" if sys.platform == "darwin" else "Wi-Fi"
    default_ws = "/opt/homebrew/bin" if sys.platform == "darwin" and Path("/opt/homebrew/bin").is_dir() else r"C:\Program Files\Wireshark"
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iface", default=default_iface, help=f'dumpcap interface NAME (default: {default_iface})')
    ap.add_argument("--network", default="airtel")
    ap.add_argument("--workload", default="global", choices=["global", "india", "both"])
    ap.add_argument("--domain", help="single domain (default: first line of the workload file)")
    ap.add_argument("--all-domains", action="store_true", help="capture every domain in the workload(s)")
    ap.add_argument("--resolvers", nargs="+", default=list(RESOLVERS))
    ap.add_argument("--protocols", nargs="+", default=list(PROTOCOLS))
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--capture-seconds", type=int, default=3)
    ap.add_argument("--warmup", type=float, default=1.0)
    ap.add_argument("--max-latency", type=float,
                    help="queries slower than this are marked 'incomplete' (the fixed capture "
                         "window may have cut them off). Default: capture-seconds - warmup - 0.5")
    ap.add_argument("--resume", action="store_true", help="skip captures already complete in the manifest")
    ap.add_argument("--wireshark-dir", default=default_ws)
    ap.add_argument("--q-path", help=r"full path to q executable (defaults to ./bin/q or PATH)")
    args = ap.parse_args()

    dumpcap = find_tool("dumpcap", args.wireshark_dir)
    tshark = find_tool("tshark", args.wireshark_dir)
    q = find_tool("q", args.wireshark_dir, args.q_path)

    max_latency = args.max_latency if args.max_latency is not None else (
        args.capture_seconds - args.warmup - 0.5)
    wl_names = ["global", "india"] if args.workload == "both" else [args.workload]
    targets: list[tuple[str, str]] = []  # (workload, domain)
    for wl in wl_names:
        lines = (WORKLOADS / f"{wl}.txt").read_text().split()
        if args.all_domains:
            targets += [(wl, d) for d in lines]
        else:
            targets.append((wl, args.domain or lines[0]))
            break

    pcap_dir = RAW / "pcaps"
    pcap_dir.mkdir(parents=True, exist_ok=True)
    manifest = RAW / "manifest.csv"
    new_file = not manifest.exists()
    done = load_done(manifest, max_latency) if args.resume else set()

    # Resolver IPs are resolved once, before any capture starts.
    res_info = {r: (RESOLVERS[r][0], RESOLVERS[r][1], resolve_ips(RESOLVERS[r][0])) for r in args.resolvers}

    # Repeat is the OUTER loop, so every batch spreads over time of day evenly.
    jobs = [
        (rep, wl, dom, res, proto)
        for rep in range(args.repeats)
        for wl, dom in targets
        for res in args.resolvers
        for proto in args.protocols
    ]
    stats: dict[tuple[str, str], list[int]] = {}
    start = time.time()
    with manifest.open("a", newline="", encoding="utf-8") as mf:
        w = csv.DictWriter(mf, fieldnames=MANIFEST_FIELDS)
        if new_file:
            w.writeheader()
        for i, (rep, wl, domain, res, proto) in enumerate(jobs, 1):
            host, path, ips = res_info[res]
            name = f"{args.network}_{res}_{proto}_{wl}_{domain}_{rep}.pcap"
            pcap = pcap_dir / name
            rel = str(pcap.relative_to(ROOT))
            if rel in done:
                continue
            uri, extra = uri_for(proto, host, path)
            rc, lat, note, ts = capture_one(
                dumpcap, q, args.iface, build_filter(ips), uri, extra,
                domain, pcap, args.capture_seconds, args.warmup)
            pkts, nbytes = count_packets(tshark, pcap) if pcap.exists() else (0, 0)
            if rc != 0:
                status = "query_failed"
            elif pkts == 0:
                status = "no_packets"
            elif lat > max_latency:
                status = "incomplete"  # capture window may have ended before the flow did
            else:
                status = "ok"
            st = stats.setdefault((res, proto), [0, 0])
            st[1] += 1
            st[0] += status == "ok"
            w.writerow({
                "timestamp": ts, "network": args.network, "resolver": res,
                "protocol": proto, "workload": wl, "domain": domain,
                "repeat": rep, "returncode": rc, "latency_s": round(lat, 4),
                "packets": pkts, "bytes": nbytes, "status": status,
                "server_ips": ";".join(ips), "pcap_path": rel, "note": note,
            })
            mf.flush()
            eta_min = (time.time() - start) / i * (len(jobs) - i) / 60
            print(f"[{i}/{len(jobs)}] {res:10s} {proto:5s} {wl:6s} {domain:28s} rep{rep} "
                  f"-> {status} ({pkts} pkts) ETA {eta_min:.0f} min")

    print("\nSuccess rate per resolver x protocol (ok/total):")
    print("resolver".ljust(12) + "".join(p.ljust(14) for p in args.protocols))
    for res in args.resolvers:
        cells = []
        for p_ in args.protocols:
            ok, tot = stats.get((res, p_), [0, 0])
            cells.append(f"{ok}/{tot}".ljust(14))
        print(res.ljust(12) + "".join(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())