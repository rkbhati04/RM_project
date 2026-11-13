#!/usr/bin/env bash
set -euo pipefail
network="${1:?network label required}"; interface="${2:-Wi-Fi}"
shift 2 || true
domain_limit=50; repeats=10; machine_label=""; resolvers=(cloudflare google adguard); protocols=(doh doh3)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain-limit) domain_limit="$2"; shift 2 ;;
    --repeats) repeats="$2"; shift 2 ;;
    --machine-label) machine_label="$2"; shift 2 ;;
    --resolvers) IFS=',' read -r -a resolvers <<< "$2"; shift 2 ;;
    --protocols) IFS=',' read -r -a protocols <<< "$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
stamp="$(date -u +%Y%m%d_%H%M%S)_$$"; run_dir="data/raw/network_runs/$network-$stamp"; lock="data/raw/capture.lock"
jobs=$(( ${#resolvers[@]} * ${#protocols[@]} * domain_limit * 2 * repeats ))
printf 'Plan: jobs=%s, estimate=%.1f hours including 20%% margin\n' "$jobs" "$(awk "BEGIN {print $jobs * 3.75 * 1.2 / 3600}")"
[[ ! -e "$lock" ]] || { echo "Capture lock exists: $lock" >&2; exit 1; }
mkdir -p "$run_dir"; touch "$lock"; trap 'rm -f "$lock"' EXIT INT TERM
cmd=(python3 src/probe_and_capture.py --iface "$interface" --network "$network" --batch "$network" \
  --run-id "$network-$stamp" --run-dir "$run_dir" --workload both --limit "$domain_limit" \
  --resolvers "${resolvers[@]}" --protocols "${protocols[@]}" --repeats "$repeats" --repeat-start 0 \
  --shuffle-from 0 --resume)
if [[ -n "$machine_label" ]]; then cmd+=(--machine-label "$machine_label"); fi
"${cmd[@]}"
