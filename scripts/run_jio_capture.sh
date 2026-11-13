#!/usr/bin/env bash
# ==============================================================================
# run_jio_capture.sh
# 
# Master runner for Jio cellular hotspot capture on macOS.
# Performs preflight verification (DNS, QUIC/UDP 443, dumpcap, disk space),
# prevents macOS sleep with caffeinate, and runs the 6,000-query Jio matrix.
#
# Matrix:
#   - Workload: Both (50 Global + 50 India = 100 domains)
#   - Resolvers: Cloudflare, Google, AdGuard (Quad9 omitted on Jio)
#   - Protocols: DoH (HTTP/2), DoH/3 (HTTP/3 / QUIC)
#   - Repeats: 10 shuffled repeats
#   - Total: 6,000 captures (~6.5 - 7.5 hours)
#
# Usage:
#   ./scripts/run_jio_capture.sh            # Full 6,000-capture overnight run
#   ./scripts/run_jio_capture.sh --test     # 12-capture quick test (1 minute)
#   ./scripts/run_jio_capture.sh --dry-run  # Dry-run test (no network traffic)
# ==============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Ensure Homebrew and standard paths are available
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Auto-detect active default network interface (e.g. en0 for Wi-Fi, en5 for iPhone USB)
DEFAULT_IFACE="$(route get default 2>/dev/null | awk '/interface:/ {print $2}')"
INTERFACE="${DEFAULT_IFACE:-en0}"
TEST_MODE=false
DRY_RUN=false
DOMAIN_LIMIT=50
REPEATS=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test)
      TEST_MODE=true
      DOMAIN_LIMIT=2
      REPEATS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      DOMAIN_LIMIT=2
      REPEATS=1
      shift
      ;;
    --interface)
      INTERFACE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--test] [--dry-run] [--interface <name>]" >&2
      exit 2
      ;;
  esac
done

echo "============================================================"
echo "  Jio Hotspot Capture Testbed"
echo "  Mode: $(if [[ "$TEST_MODE" == true ]]; then echo "TEST (12 queries)"; elif [[ "$DRY_RUN" == true ]]; then echo "DRY RUN"; else echo "FULL OVERNIGHT (6,000 queries)"; fi)"
echo "  Interface: $INTERFACE"
echo "============================================================"

# --- 1. Tool verification ---
echo -n "[1/5] Checking tools (python3, q, dumpcap, tshark)... "
for tool in python3 q dumpcap tshark; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "FAILED"
    echo "ERROR: Missing required tool '$tool'. Please ensure it is installed and on PATH." >&2
    exit 1
  fi
done
echo "OK"

# --- 2. Disk space check (> 20 GB free) ---
echo -n "[2/5] Checking available disk space... "
FREE_KB="$(df -Pk . | awk 'NR==2 {print $4}')"
if (( FREE_KB < 20971520 )); then
  FREE_GB=$(( FREE_KB / 1048576 ))
  echo "WARNING: Only ${FREE_GB} GB free. Recommend at least 20 GB for PCAPs."
else
  FREE_GB=$(( FREE_KB / 1048576 ))
  echo "OK (${FREE_GB} GB free)"
fi

# --- 3. Hotspot connectivity & DoH/DoH3 reachability test ---
if [[ "$DRY_RUN" == false ]]; then
  echo -n "[3/5] Verifying internet connectivity (DoH HTTP/2 to Cloudflare)... "
  if ! q google.com A @https://cloudflare-dns.com/dns-query --http2 >/dev/null 2>&1; then
    echo "FAILED"
    echo "ERROR: Could not resolve via DoH over this connection."
    echo "Please ensure mobile data / tethering is active." >&2
    exit 1
  fi
  echo "OK"
  
  echo -n "      Probing DoH/3 (UDP 443 QUIC)... "
  if q google.com A @https://cloudflare-dns.com/dns-query --http3 >/dev/null 2>&1; then
    echo "OK (QUIC/DoH3 reachable)"
  else
    echo "DROPPED (Carrier blocks UDP 443; will capture and record as udp_blocked_flag=true)"
  fi
else
  echo "[3/5] Skipping network check (dry-run mode)"
fi

# --- 4. Setup output directory & lock ---
STAMP="$(date -u +%Y%m%d_%H%M%S)"
RUN_DIR="data/raw/network_runs/jio_${STAMP}"
LOCK_FILE="data/raw/capture.lock"

if [[ -e "$LOCK_FILE" ]]; then
  echo "ERROR: Capture lock exists ($LOCK_FILE). Is another capture already running?" >&2
  exit 1
fi

mkdir -p "$RUN_DIR"
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT INT TERM

echo "[4/5] Run directory prepared: $RUN_DIR"

# --- 5. Launch capture with caffeinate ---
echo "[5/5] Launching capture (system sleep prevented via caffeinate)..."
echo "------------------------------------------------------------"

CAPTURE_ARGS=(
  python3 src/probe_and_capture.py
  --iface "$INTERFACE"
  --network jio
  --machine-label jio
  --run-id "jio_${STAMP}"
  --batch "jio_${STAMP}"
  --workload both
  --limit "$DOMAIN_LIMIT"
  --all-domains
  --resolvers cloudflare google adguard
  --protocols doh doh3
  --repeats "$REPEATS"
  --repeat-start 0
  --shuffle-from 0
  --warmup 0.3
  --capture-seconds 3
  --run-dir "$RUN_DIR"
  --resume
)

if [[ "$DRY_RUN" == true ]]; then
  CAPTURE_ARGS+=(--dry-run)
fi

# Run under caffeinate to prevent sleep on macOS
MAX_RETRIES=3
ATTEMPT=1
SUCCESS=false

while (( ATTEMPT <= MAX_RETRIES )); do
  echo "Starting capture attempt $ATTEMPT of $MAX_RETRIES..."
  if caffeinate -d -i -m -s "${CAPTURE_ARGS[@]}"; then
    SUCCESS=true
    break
  fi
  echo "Capture process exited with non-zero status."
  if (( ATTEMPT < MAX_RETRIES )); then
    echo "Waiting 60 seconds before resuming attempt $(( ATTEMPT + 1 ))..."
    sleep 60
  fi
  (( ATTEMPT++ ))
done

echo "------------------------------------------------------------"
if [[ "$SUCCESS" == true ]]; then
  echo "Capture finished successfully!"
  echo "Manifest: $RUN_DIR/manifest.csv"
  echo "PCAPs:    $RUN_DIR/pcaps/"
  
  if [[ -f "$RUN_DIR/manifest.csv" ]]; then
    TOTAL_ROWS="$(wc -l < "$RUN_DIR/manifest.csv" | tr -d ' ')"
    TOTAL_ROWS=$(( TOTAL_ROWS - 1 )) # subtract header
    OK_ROWS="$(grep -c ",ok," "$RUN_DIR/manifest.csv" || true)"
    echo "Total captures: $TOTAL_ROWS (OK: $OK_ROWS)"
  fi
  
  echo ""
  echo "Next step (feature extraction):"
  echo "python3 src/extract_features.py --manifest $RUN_DIR/manifest.csv --root . --max-latency 1.5"
  exit 0
else
  echo "Capture failed after $MAX_RETRIES attempts. Inspect $RUN_DIR/manifest.csv for details." >&2
  exit 1
fi
