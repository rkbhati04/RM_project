#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_ID="${AIRTEL_RUN_ID:-airtel_topup_20261113}"
PERMUTATIONS="${AIRTEL_PERMUTATIONS:-200}"
JOBS="${AIRTEL_JOBS:-4}"
ADVANCED_OUT="${AIRTEL_ADVANCED_OUT:-results/airtel_advanced_20261113}"
QUICK=false
SKIP_ADVANCED=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick)
      QUICK=true
      shift
      ;;
    --skip-advanced)
      SKIP_ADVANCED=true
      shift
      ;;
    *)
      echo "Usage: $0 [--quick] [--skip-advanced]" >&2
      exit 2
      ;;
  esac
done

[[ -f data/processed/dataset_v2.csv ]] || {
  echo "Missing data/processed/dataset_v2.csv" >&2
  exit 1
}

echo "Running supported Airtel analysis: $RUN_ID"
PYTHONPATH=src python3 -m encdns analyze \
  --run-id "$RUN_ID" \
  --permutations "$PERMUTATIONS" \
  --resume

PYTHONPATH=src python3 -m encdns report "$RUN_ID"
PYTHONPATH=src python3 -m encdns ledger "$RUN_ID"

if [[ "$SKIP_ADVANCED" == true ]]; then
  echo "Skipped advanced E1-E5 analysis."
  exit 0
fi

advanced_args=(
  --dataset data/processed/dataset_v2.csv
  --out "$ADVANCED_OUT"
  --jobs "$JOBS"
  --shuffled-from 8
)

if [[ "$QUICK" == true ]]; then
  advanced_args+=(--quick)
else
  advanced_args+=(--perm "$PERMUTATIONS" --folds 5 --seeds 3)
fi

echo "Running Airtel-only advanced E1-E5 analysis"
python3 src/analysis_v2.py "${advanced_args[@]}"

echo "Airtel analysis complete."
echo "Core outputs: results/$RUN_ID/"
echo "Advanced outputs: $ADVANCED_OUT/"
