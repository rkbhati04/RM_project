#!/usr/bin/env bash
set -euo pipefail
network=""; interface="Wi-Fi"; no_live=0
while (($#)); do case "$1" in --network) network="$2"; shift 2;; --interface) interface="$2"; shift 2;; --no-live) no_live=1; shift;; *) echo "unknown option: $1" >&2; exit 2;; esac; done
checks=0
command -v python3 >/dev/null || checks=1
[[ -n "${VIRTUAL_ENV:-}" ]] || checks=1
command -v q >/dev/null || checks=1
command -v dumpcap >/dev/null || checks=1
command -v tshark >/dev/null || checks=1
q --version 2>&1 | head -1 || true
dumpcap -D 2>/dev/null | grep -F "$interface" >/dev/null || checks=1
[[ -n "$network" ]] || checks=1
free_kb="$(df -Pk . | awk 'NR==2 {print $4}')"; (( free_kb > 20971520 )) || checks=1
if (( no_live == 0 )) && [[ ! -e data/raw/capture.lock ]] && (( checks == 0 )); then
  live_dir="data/raw/preflight_runs/$(date -u +%Y%m%d_%H%M%S)"
  python3 src/probe_and_capture.py --iface "$interface" --network "$network" --workload global --limit 1 \
    --resolvers adguard --protocols doh --repeats 1 --run-dir "$live_dir" || checks=1
fi
if (( checks == 0 )); then echo GO; else echo NO-GO; exit 1; fi
