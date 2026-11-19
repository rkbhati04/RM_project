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
import hashlib
import ipaddress
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
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
PROTOCOLS = ("doh3", "doh")
PROTOCOL_PORTS = {
    "doh": {"tcp": 443},
    "doh3": {"udp": 443},
}

MANIFEST_FIELDS = [
    "timestamp", "run_id", "batch", "order_mode", "network", "machine_id", "public_ip",
    "rtt_ms", "q_version", "client", "resolver", "protocol", "workload",
    "domain", "repeat", "returncode", "latency_s", "packets", "bytes",
    "answer_count", "cname_count", "ttl_min", "padding_present",
    "udp_blocked_flag", "status", "server_ips", "pcap_path", "note",
]


def uri_for(protocol: str, host: str, path: str) -> tuple[str, list[str]]:
    """Return (server URI, extra q flags). q has no h3:// scheme: DoH/3 is
    https:// plus --http3, and DoH is pinned to HTTP/2 with --http2."""
    if protocol == "doh":
        return f"https://{host}{path}", ["--http2"]
    if protocol == "doh3":
        return f"https://{host}{path}", ["--http3"]
    raise ValueError(f"Unsupported protocol: {protocol}")


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
    search_dirs = [
        wireshark_dir, "/opt/homebrew/bin", "/usr/local/bin",
        r"C:\Program Files\Wireshark", r"C:\Program Files\Q",
    ]
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


def build_filter(ips: list[str], protocol: str) -> str:
    hosts = " or ".join(f"host {ip}" for ip in ips)
    ports = " or ".join(
        f"{transport} port {port}" for transport, port in PROTOCOL_PORTS[protocol].items()
    )
    return f"({hosts}) and ({ports})"


def count_packets(tshark: str, pcap: Path) -> tuple[int, int]:
    out = subprocess.run(
        [tshark, "-r", str(pcap), "-T", "fields", "-e", "frame.len"],
        capture_output=True, text=True,
    ).stdout.split()
    sizes = [int(x) for x in out if x.isdigit()]
    return len(sizes), sum(sizes)


def parse_q_json(output: str) -> dict[str, str]:
    """Parse q JSON output across minor schema variations; blanks mean unavailable."""
    empty = {"answer_count": "", "cname_count": "", "ttl_min": "", "padding_present": "unknown"}
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        start, end = output.find("{"), output.rfind("}")
        if start < 0 or end <= start:
            return empty
        try:
            payload = json.loads(output[start:end + 1])
        except json.JSONDecodeError:
            return empty
    nodes: list[dict] = []
    def walk(value):
        if isinstance(value, dict):
            nodes.append(value)
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(payload)
    answer_records = []
    for node in nodes:
        for key, value in node.items():
            if str(key).lower() in {"answer", "answers"} and isinstance(value, list):
                answer_records.extend(item for item in value if isinstance(item, dict))
            elif str(key).lower() in {"answer", "answers"} and isinstance(value, dict):
                answer_records.extend(item for item in value.values() if isinstance(item, dict))
    answers = answer_records or [
        node for node in nodes
        if str(next((value for key, value in node.items() if str(key).lower() == "type"), "")).upper() not in {"", "OPT"}
        and any(str(key).lower() in {"ttl", "data"} for key in node)
    ]
    def field(node: dict, name: str):
        value = next((value for key, value in node.items() if str(key).lower() == name), None)
        if value is not None:
            return value
        header = next((value for key, value in node.items() if str(key).lower() == "hdr"), None)
        if isinstance(header, dict):
            return next((value for key, value in header.items() if str(key).lower() == name), "")
        return ""

    def rr_type(node: dict) -> str:
        value = field(node, "type")
        if value == "":
            value = field(node, "rrtype")
        return {1: "A", 5: "CNAME", "1": "A", "5": "CNAME"}.get(value, str(value).upper())

    answers = [node for node in answers if rr_type(node) != "OPT"]
    ttls = []
    for node in answers:
        value = field(node, "ttl")
        match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s?)?$", str(value).strip())
        if match and any(match.groups()):
            hours, minutes, seconds = match.groups()
            ttls.append(int(float(hours or 0) * 3600 + float(minutes or 0) * 60 + float(seconds or 0)))
    if not ttls:
        for node in nodes:
            for key, value in node.items():
                normalized = re.sub(r"[^a-z]", "", str(key).lower())
                if normalized in {"minttl", "ttl"}:
                    match = re.search(r"\d+(?:\.\d+)?", str(value))
                    if match and float(match.group()) > 0:
                        ttls.append(int(float(match.group())))
    encoded = json.dumps(payload).upper()
    has_opt = any(rr_type(node) == "OPT" for node in nodes)
    has_padding = "PADDING" in encoded or ('"12"' in encoded and "OPTION" in encoded)
    return {
        "answer_count": str(len(answers)),
        "cname_count": str(sum(rr_type(node) == "CNAME" for node in answers)),
        "ttl_min": str(min(ttls)) if ttls else "",
        "padding_present": "true" if has_padding else ("false" if has_opt else "unknown"),
    }


def detect_q_json_flag(q: str) -> str:
    """Discover q's supported structured-output flag from its own help."""
    help_text = subprocess.run([q, "--help"], capture_output=True, text=True, check=False)
    combined = help_text.stdout + "\n" + help_text.stderr
    if re.search(r"(?:--|/)?format", combined, re.IGNORECASE) and "json" in combined.lower():
        return "--format=json"
    raise RuntimeError("Installed q does not advertise JSON output in q --help")


def fetch_public_ip(network: str) -> str:
    """Return a salted public-IP token; never return or persist the raw address."""
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
            value = response.read().decode("ascii").strip()
        ipaddress.ip_address(value)
        return anonymize_public_ip(value)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"WARNING: public IP lookup failed for network {network}: {exc}", file=sys.stderr)
        return ""


def upgrade_manifest(manifest: Path) -> None:
    """Migrate legacy manifests, backing up before any in-place rewrite."""
    if not manifest.exists():
        return
    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        old_fields = reader.fieldnames or []
        rows = list(reader)
    with manifest.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.reader(handle))
    fields = MANIFEST_FIELDS
    row_lengths = {len(row) for row in raw_rows[1:]}
    if row_lengths and any(length not in {len(old_fields), len(fields)} for length in row_lengths):
        raise ValueError(f"Manifest has unsupported legacy row lengths: {sorted(row_lengths)}")
    needs_migration = old_fields != fields or row_lengths != {len(fields)}
    if not needs_migration:
        return
    backup = manifest.with_name("manifest_pre_migration.csv")
    shutil.copy2(manifest, backup)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            public_ip = (row.get("public_ip") or "").strip()
            try:
                ipaddress.ip_address(public_ip)
            except ValueError:
                pass
            else:
                row["public_ip"] = anonymize_public_ip(public_ip)
            writer.writerow(row)
    print(f"Migrated manifest in place; backup: {backup}")


def validate_manifest(manifest: Path) -> set[int]:
    """Reject malformed manifests before appending a new capture row."""
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return set()
    expected = len(rows[0])
    lengths = {len(row) for row in rows}
    if lengths != {expected}:
        raise ValueError(f"Manifest has inconsistent row lengths: {sorted(lengths)}")
    if rows[0] != MANIFEST_FIELDS:
        raise ValueError("Manifest header is not the supported schema after migration")
    return lengths


def anonymize_public_ip(value: str) -> str:
    """Store a stable salted token, never a literal public IP address."""
    if not value:
        return ""
    salt = os.environ.get("ENCDNS_IP_SALT", "local-network-label")
    return "hash:" + hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]


def anonymize_machine_id(label: str) -> str:
    """Store a stable machine token without persisting the hostname."""
    if not label:
        return ""
    salt = os.environ.get("ENCDNS_MACHINE_SALT", os.environ.get("ENCDNS_IP_SALT", "local-machine-label"))
    return "machine:" + hashlib.sha256(f"{salt}:{label}".encode()).hexdigest()[:16]


def capture_one(dumpcap, q, iface, bpf, uri, extra, domain, pcap, seconds, warmup, q_json_flag):
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
        # Enforce 2s timeout for q to match max_latency and avoid hanging on dropped UDP
        command = [q, domain, "A", f"@{uri}", "--opt", "--timeout=2s", *extra]
        if q_json_flag:
            command.append(q_json_flag)
        r = subprocess.run(command, capture_output=True,
                           text=True, timeout=10, env=q_env)
        rc, latency = r.returncode, time.time() - t0
        if rc != 0:
            note = (r.stderr or r.stdout).strip().replace("\n", " ")[:200]
    except subprocess.TimeoutExpired:
        rc, latency, note = -1, time.time() - t0, "q timeout"
    
    # Allow a brief 150ms window for trailing ACKs/FINs, then flush dumpcap immediately
    time.sleep(0.15)
    if cap.poll() is None:
        try:
            cap.send_signal(signal.SIGINT)
        except Exception:
            cap.terminate()

    try:
        _, cap_err = cap.communicate(timeout=seconds + 5)
    except subprocess.TimeoutExpired:
        cap.kill()
        _, cap_err = cap.communicate()
    if not note and cap.returncode != 0:
        note = "dumpcap: " + (cap_err or "").strip().replace("\n", " ")[:200]
    metadata = parse_q_json(r.stdout) if "r" in locals() and q_json_flag else {
        "answer_count": "", "cname_count": "", "ttl_min": "", "padding_present": "unknown"
    }
    return rc, latency, note, int(t0), metadata


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
    ap.add_argument("--machine-label", default="", help="local label hashed into machine_id; never persisted raw")
    ap.add_argument("--run-id", default="", help="stable identifier for this collection run")
    ap.add_argument("--batch", default="T0")
    ap.add_argument("--public-ip", default="", help=argparse.SUPPRESS)
    ap.add_argument("--workload", default="global", choices=["global", "india", "both"])
    ap.add_argument("--domain", help="single domain (default: first line of the workload file)")
    ap.add_argument("--all-domains", action="store_true", help="capture every domain in the workload(s)")
    ap.add_argument("--limit", type=int, help="cap domains per workload (useful for dry-runs)")
    ap.add_argument("--resolvers", nargs="+", default=list(RESOLVERS))
    ap.add_argument("--protocols", nargs="+", default=["doh3"], help="protocols to capture (default: doh3)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--repeat-start", type=int, default=0, help="first repeat number; --repeats is a count")
    ap.add_argument("--capture-seconds", type=int, default=3)
    ap.add_argument("--warmup", type=float, default=1.0)
    ap.add_argument("--max-latency", type=float,
                    help="queries slower than this are marked 'incomplete' (the fixed capture "
                         "window may have cut them off). Default: capture-seconds - warmup - 0.5")
    ap.add_argument("--shuffle-from", type=int, default=None,
                    help="randomize the capture order (domain x resolver x protocol) for repeats >= N, "
                         "so a domain is not always captured at the same point of a pass (order control)")
    ap.add_argument("--resume", action="store_true", help="skip captures already complete in the manifest")
    ap.add_argument("--wireshark-dir", default=default_ws)
    ap.add_argument("--q-path", help=r"full path to q executable (defaults to ./bin/q or PATH)")
    ap.add_argument("--q-json-flag", default="", help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="write valid manifest rows without network commands")
    ap.add_argument("--run-dir", type=Path,
                    help="isolated run directory; writes manifest.csv and pcaps/ here")
    ap.add_argument("--manifest", type=Path, default=None, help="manifest output path")
    ap.add_argument("--pcap-dir", type=Path, default=None, help="PCAP output directory")
    args = ap.parse_args()

    if args.run_dir:
        args.run_dir = args.run_dir.resolve()
        args.manifest = args.manifest or args.run_dir / "manifest.csv"
        args.pcap_dir = args.pcap_dir or args.run_dir / "pcaps"
    else:
        args.manifest = args.manifest or RAW / "manifest.csv"
        args.pcap_dir = args.pcap_dir or RAW / "pcaps"
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.pcap_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        dumpcap = tshark = q = "dry-run"
    else:
        dumpcap = find_tool("dumpcap", args.wireshark_dir)
        tshark = find_tool("tshark", args.wireshark_dir)
        q = find_tool("q", args.wireshark_dir, args.q_path)
        args.q_json_flag = args.q_json_flag or detect_q_json_flag(q)
        if not args.public_ip:
            args.public_ip = fetch_public_ip(args.network)
    args.run_id = args.run_id or f"run-{int(time.time())}"
    args.machine_id = anonymize_machine_id(args.machine_label or os.environ.get("COMPUTERNAME", ""))

    max_latency = args.max_latency if args.max_latency is not None else (
        args.capture_seconds - args.warmup - 0.5)
    wl_names = ["global", "india"] if args.workload == "both" else [args.workload]
    targets: list[tuple[str, str]] = []  # (workload, domain)
    for wl in wl_names:
        lines = (WORKLOADS / f"{wl}.txt").read_text().split()
        if args.limit is not None:
            lines = lines[:args.limit]
        if args.all_domains or (args.batch.lower() == "smoke" and args.limit is not None):
            targets += [(wl, d) for d in lines]
        else:
            targets.append((wl, args.domain or lines[0]))
            break

    pcap_dir = args.pcap_dir.resolve()
    manifest = args.manifest
    upgrade_manifest(manifest)
    if manifest.exists():
        validate_manifest(manifest)
    new_file = not manifest.exists()
    done = load_done(manifest, max_latency) if args.resume else set()

    # Resolver IPs are resolved once, before any capture starts.
    res_info = {r: (RESOLVERS[r][0], RESOLVERS[r][1], resolve_ips(RESOLVERS[r][0])) for r in args.resolvers}

    # Repeat is the OUTER loop, so every batch spreads over time of day evenly.
    jobs = []
    for rep in range(args.repeat_start, args.repeat_start + args.repeats):
        block = [(rep, wl, dom, res, proto)
                 for wl, dom in targets for res in args.resolvers for proto in args.protocols]
        if args.shuffle_from is not None and rep >= args.shuffle_from:
            random.Random(1000 + rep).shuffle(block)  # fixed seed per repeat: reproducible
        jobs += block
    planned_skip = sum(
        str((pcap_dir / f"{args.network}_{res}_{proto}_{wl}_{domain}_{rep}.pcap").relative_to(ROOT)) in done
        for rep, wl, domain, res, proto in jobs
    )
    print(f"Plan: jobs={len(jobs)}, resume_skip={planned_skip}, repeats={args.repeat_start}-{args.repeat_start + args.repeats - 1}")
    if args.batch.lower() == "smoke" and len(jobs) != 16:
        raise ValueError(f"Smoke batch must plan exactly 16 jobs, got {len(jobs)}")
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
            if args.dry_run:
                rc, lat, note, ts = "", "", "No network command executed.", int(time.time())
                metadata, pkts, nbytes, status = parse_q_json(""), "", "", "dry_run"
            else:
                rc, lat, note, ts, metadata = capture_one(
                    dumpcap, q, args.iface, build_filter(ips, proto), uri, extra,
                    domain, pcap, args.capture_seconds, args.warmup, args.q_json_flag)
                pkts, nbytes = count_packets(tshark, pcap) if pcap.exists() else (0, 0)
                status = ""
            if args.dry_run:
                status = "dry_run"
            elif rc != 0:
                status = "query_failed"
            elif pkts == 0:
                status = "no_packets"
            elif lat > max_latency:
                status = "incomplete"  # capture window may have ended before the flow did
            elif (
                not metadata.get("answer_count", "").isdigit()
                or int(metadata["answer_count"]) < 1
                or not metadata.get("ttl_min", "").isdigit()
                or int(metadata["ttl_min"]) <= 0
            ):
                status = "bad_metadata"
            else:
                status = "ok"
            st = stats.setdefault((res, proto), [0, 0])
            st[1] += 1
            st[0] += status == "ok"
            w.writerow({
                "timestamp": ts, "run_id": args.run_id, "batch": args.batch,
                "order_mode": "shuffled" if args.shuffle_from is not None and rep >= args.shuffle_from else "fixed",
                "network": args.network, "machine_id": args.machine_id,
                "public_ip": anonymize_public_ip(args.public_ip), "rtt_ms": round(lat * 1000, 1) if not args.dry_run else "",
                "q_version": "" if args.dry_run else (lambda version: (version.stdout or version.stderr).strip())(subprocess.run([q, "--version"], capture_output=True, text=True)), "client": "q",
                "resolver": res,
                "protocol": proto, "workload": wl, "domain": domain,
                "repeat": rep, "returncode": rc, "latency_s": round(lat, 4) if not args.dry_run else "",
                "packets": pkts, "bytes": nbytes, **metadata,
                "udp_blocked_flag": str(proto == "doh3" and status in {"query_failed", "no_packets", "incomplete"}).lower(), "status": status,
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
