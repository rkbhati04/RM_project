#!/usr/bin/env bash
set -euo pipefail
interface="${1:-Wi-Fi}"
network="${2:-airtel}"
run_stamp="$(date -u +%Y%m%d_%H%M%S)_$$"
run_dir="data/raw/overnight_runs/$run_stamp"
batch="overnight-$run_stamp"
lock_file="data/raw/capture.lock"
if [[ -e "$lock_file" ]]; then
  echo "Capture lock exists: $lock_file" >&2
  exit 1
fi
if [[ -e "$run_dir" ]]; then
  echo "Refusing to reuse existing overnight run directory: $run_dir" >&2
  exit 1
fi
mkdir -p "$run_dir"
touch "$lock_file"
trap 'rm -f "$lock_file"' EXIT INT TERM
failures=0
maximum_failures=3
while (( failures < maximum_failures )); do
  if python3 src/probe_and_capture.py \
    --iface "$interface" --network "$network" --batch "$batch" --run-id "$batch" \
    --run-dir "$run_dir" --workload both --all-domains \
    --resolvers adguard cloudflare google quad9 --protocols doh doh3 \
    --repeats 12 --repeat-start 8 --shuffle-from 8 --resume; then
    exit 0
  fi
  ((failures+=1))
  if (( failures < maximum_failures )); then
    echo "Capture driver failed; retrying in 60 seconds ($failures/$maximum_failures)." >&2
    sleep 60
  fi
done
echo "Capture driver failed $maximum_failures consecutive times. Inspect the manifest before retrying." >&2
exit 1
