"""Build frozen, reproducible Global and Indian DNS workloads.

Global workload : the top-ranked live domains of a pinned Tranco list.
Indian workload : live domains from the same list that either end in ".in"
                  or appear in INDIA_SEED_DOMAINS, taken in Tranco rank order.

Run this ONCE, on ONE network, then commit the output files. Never regenerate
the lists per network or per experiment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "workloads"

# Tranco lists registered domains (eTLD+1), so subdomains such as
# timesofindia.indiatimes.com can never match; use indiatimes.com instead.
INDIA_SEED_DOMAINS = frozenset(
    {
        "flipkart.com",
        "hotstar.com",
        "indiatimes.com",
        "jio.com",
        "myntra.com",
        "paytm.com",
        "phonepe.com",
        "swiggy.com",
        "tatacliq.com",
        "zomato.com",
    }
)


def download_tranco(list_id: str, limit: int) -> list[str]:
    """Download the top `limit` domains of a pinned Tranco list, in rank order."""
    url = f"https://tranco-list.eu/download/{list_id}/{limit}"
    request = Request(url, headers={"User-Agent": "RM-Project-workload-builder/1.0"})
    with urlopen(request, timeout=120) as response:
        rows = response.read().decode("utf-8").splitlines()

    domains: list[str] = []
    seen: set[str] = set()
    for row in csv.reader(rows):
        if len(row) >= 2 and row[0].strip().isdigit():
            domain = row[1].strip().lower().rstrip(".")
            if domain and domain not in seen:
                seen.add(domain)
                domains.append(domain)
    if not domains:
        raise ValueError(f"No domains found in Tranco list {list_id}")
    return domains


def is_live(domain: str) -> bool:
    """A domain is live if the system resolver returns an address for it."""
    try:
        socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return True


def take_live(candidates: Iterable[str], count: int, skip_resolution: bool) -> list[str]:
    """Return the first `count` live candidates, resolving lazily and stopping early."""
    selected: list[str] = []
    for domain in candidates:
        if skip_resolution or is_live(domain):
            selected.append(domain)
            if len(selected) == count:
                break
    return selected


def write_domains(path: Path, domains: list[str]) -> None:
    path.write_text("\n".join(domains) + "\n", encoding="utf-8")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranco-id", required=True, help="Pinned Tranco list ID")
    parser.add_argument("--count", type=int, default=25, help="Domains per workload")
    parser.add_argument(
        "--pool",
        type=int,
        default=1_000_000,
        help="How many top Tranco domains to download as the candidate pool",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-resolution", action="store_true")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    if args.pool < args.count:
        parser.error("--pool must be at least --count")

    domains = download_tranco(args.tranco_id, args.pool)

    # Global: top-ranked live domains. Resolution stops as soon as `count` is reached.
    global_domains = take_live(domains, args.count, args.skip_resolution)

    # India: .in domains plus seeds, kept in Tranco rank order (deterministic).
    india_candidates = (
        d for d in domains if d.endswith(".in") or d in INDIA_SEED_DOMAINS
    )
    india_domains = take_live(india_candidates, args.count, args.skip_resolution)

    if len(global_domains) < args.count or len(india_domains) < args.count:
        raise RuntimeError(
            "Could not build both workloads: "
            f"Global={len(global_domains)}, India={len(india_domains)} "
            f"(requested {args.count}, pool {len(domains)})"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    global_path = args.output / "global.txt"
    india_path = args.output / "india.txt"
    write_domains(global_path, global_domains)
    write_domains(india_path, india_domains)

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tranco_list_id": args.tranco_id,
        "tranco_url": f"https://tranco-list.eu/list/{args.tranco_id}",
        "pool_size_requested": args.pool,
        "pool_size_downloaded": len(domains),
        "requested_domains_per_workload": args.count,
        "resolution_filter_applied": not args.skip_resolution,
        "india_definition": "domains ending in .in, plus INDIA_SEED_DOMAINS, in Tranco rank order",
        "india_seed_domains": sorted(INDIA_SEED_DOMAINS),
        "global_file": global_path.name,
        "global_sha256": sha256_of(global_path),
        "india_file": india_path.name,
        "india_sha256": sha256_of(india_path),
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "global": len(global_domains),
                "india": len(india_domains),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())