#!/usr/bin/env bash
set -euo pipefail
interface="${1:-Wi-Fi}"; network="${2:-airtel}"
stamp="$(date -u +%Y%m%d_%H%M%S)_$$"; run_dir="data/raw/drift_runs/$stamp"; lock="data/raw/capture.lock"
[[ ! -e "$lock" ]] || { echo "Capture lock exists: $lock" >&2; exit 1; }
mkdir -p "$run_dir"; touch "$lock"; trap 'rm -f "$lock"' EXIT INT TERM
python3 src/probe_and_capture.py --iface "$interface" --network "$network" --batch T1 \
  --run-id "T1-$stamp" --run-dir "$run_dir" --workload both --all-domains \
  --resolvers adguard quad9 --protocols doh doh3 --repeats 3 --repeat-start 100 \
  --shuffle-from 100 --resume
