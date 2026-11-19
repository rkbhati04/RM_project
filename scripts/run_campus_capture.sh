#!/usr/bin/env bash
# scripts/run_campus_capture.sh
# Automated Campus Capture Preflight and Execution Script (Linux)
# Designed for Task KU7 (Kunal - Campus vantage point capture)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Default configuration
NETWORK="campus"
MACHINE_LABEL="kunal_linux"
DOMAIN_LIMIT=50
REPEATS=10
RESOLVERS=("google" "adguard" "cloudflare" "quad9")
PROTOCOLS=("doh" "doh3")
INTERFACE=""
DRY_RUN=0
TEST_MODE=0
SKIP_PREFLIGHT=0

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Campus Capture runner for Linux systems.

Options:
  --interface <iface>         Network interface (default: auto-detect wlp*/wlan*)
  --network <label>           Network label (default: campus)
  --machine-label <label>     Machine label hashed into machine_id (default: kunal_linux)
  --domain-limit <n>          Number of domains per workload (default: 50)
  --repeats <n>               Repeats per domain (default: 10)
  --resolvers <r1,r2,...>     Comma-separated resolvers (default: google,adguard,cloudflare,quad9)
  --protocols <p1,p2,...>     Comma-separated protocols (default: doh,doh3)
  --dry-run                   Simulate capture without raw packet capture
  --test                      Run preflight diagnostic checks only and exit (GO/NO-GO)
  --skip-preflight            Bypass preflight environment checks
  -h, --help                  Show this help message
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interface) INTERFACE="$2"; shift 2 ;;
    --network) NETWORK="$2"; shift 2 ;;
    --machine-label) MACHINE_LABEL="$2"; shift 2 ;;
    --domain-limit) DOMAIN_LIMIT="$2"; shift 2 ;;
    --repeats) REPEATS="$2"; shift 2 ;;
    --resolvers) IFS=',' read -r -a RESOLVERS <<< "$2"; shift 2 ;;
    --protocols) IFS=',' read -r -a PROTOCOLS <<< "$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --test) TEST_MODE=1; shift ;;
    --skip-preflight) SKIP_PREFLIGHT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Error: Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

# Auto-detect Wi-Fi / wireless interface if not explicitly provided
detect_wifi_interface() {
  local iface=""
  # 1. Search sysfs for wireless devices
  for dev in /sys/class/net/*; do
    if [[ -d "$dev/wireless" ]]; then
      iface="$(basename "$dev")"
      break
    fi
  done
  # 2. Search common interface names (wlp*, wlan*, wl*)
  if [[ -z "$iface" ]]; then
    iface="$(ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | grep -E '^(wlan|wlp|wl)' | head -n1 || true)"
  fi
  # 3. Check dumpcap interfaces
  if [[ -z "$iface" ]] && command -v dumpcap >/dev/null 2>&1; then
    iface="$(dumpcap -D 2>/dev/null | awk '{print $2}' | grep -E '^(wlan|wlp|wl)' | head -n1 || true)"
  fi
  echo "${iface:-wlp2s0}"
}

if [[ -z "$INTERFACE" ]]; then
  INTERFACE="$(detect_wifi_interface)"
fi

echo "======================================================================"
echo "KU7 Campus Capture Suite — Vantage Point: $NETWORK ($MACHINE_LABEL)"
echo "Interface: $INTERFACE | Domain Limit: $DOMAIN_LIMIT | Repeats: $REPEATS"
echo "Resolvers: ${RESOLVERS[*]} | Protocols: ${PROTOCOLS[*]}"
echo "======================================================================"

# Locate tools
PYTHON_BIN=""
if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ -x "$VIRTUAL_ENV/bin/python3" ]]; then
  PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
elif [[ -x "$REPO_ROOT/.venv/bin/python3" ]]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
else
  PYTHON_BIN="$(command -v python3 || true)"
fi

Q_BIN=""
if [[ -x "$REPO_ROOT/bin/q" ]]; then
  Q_BIN="$REPO_ROOT/bin/q"
else
  Q_BIN="$(command -v q || true)"
fi

# Preflight Checks
run_preflight() {
  local checks_passed=1
  echo "[Preflight] Checking environment and prerequisites..."

  # 1. Python environment
  if [[ -n "$PYTHON_BIN" ]] && "$PYTHON_BIN" -c "import pandas, sklearn, numpy" >/dev/null 2>&1; then
    echo "  [OK] Python virtual environment ready: $PYTHON_BIN"
  else
    echo "  [FAIL] Python environment missing or required packages not installed." >&2
    checks_passed=0
  fi

  # 2. q client binary
  if [[ -n "$Q_BIN" ]] && [[ -x "$Q_BIN" ]]; then
    local q_ver
    q_ver="$("$Q_BIN" --version 2>&1 | head -n 1 || true)"
    echo "  [OK] q DNS client available: $q_ver"
  else
    echo "  [FAIL] q DNS client not found in ./bin/q or PATH." >&2
    checks_passed=0
  fi

  # 3. dumpcap and tshark
  if command -v dumpcap >/dev/null 2>&1 && command -v tshark >/dev/null 2>&1; then
    echo "  [OK] Packet capture tools found: dumpcap and tshark"
  else
    echo "  [FAIL] dumpcap or tshark missing from PATH." >&2
    checks_passed=0
  fi

  # 4. Network interface availability
  if ip link show "$INTERFACE" >/dev/null 2>&1; then
    echo "  [OK] Network interface '$INTERFACE' is available."
  else
    echo "  [FAIL] Network interface '$INTERFACE' not found on system." >&2
    checks_passed=0
  fi

  # 5. Free disk space (> 20 GB)
  local free_kb
  free_kb="$(df -Pk "$REPO_ROOT" | awk 'NR==2 {print $4}')"
  local min_kb=20971520 # 20 GB
  if (( free_kb > min_kb )); then
    local free_gb=$(( free_kb / 1024 / 1024 ))
    echo "  [OK] Sufficient disk space: ${free_gb} GB available (minimum 20 GB required)."
  else
    echo "  [FAIL] Insufficient disk space: $(( free_kb / 1024 )) MB free. Need >= 20 GB." >&2
    checks_passed=0
  fi

  # 6. Internet connectivity probe
  if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1 || curl -s --max-time 3 -I https://www.google.com >/dev/null 2>&1; then
    echo "  [OK] External network connectivity confirmed."
  else
    echo "  [WARN] External ping/HTTP check did not respond. Check Wi-Fi connection."
  fi

  # 7. UDP 443 / 853 blocking probe (Carrier Middlebox Detection)
  echo "[Preflight] Probing carrier transport availability (UDP 443 / 853)..."
  local udp_blocked=0
  if [[ -n "$Q_BIN" ]] && [[ -x "$Q_BIN" ]]; then
    # Test DoH/3 (UDP 443) probe to Google DNS
    if "$Q_BIN" example.com @https://dns.google/dns-query --http3 --format json >/dev/null 2>&1; then
      echo "  [OK] UDP port 443 (DoH/3 / QUIC) is OPEN on this network."
    else
      echo "  [NOTICE] UDP port 443 (DoH/3 / QUIC) timed out or failed."
      echo "           Carrier middlebox may be filtering UDP 443 (similar to Reliance Jio)."
      echo "           Captures will proceed; DoH/3 status will be recorded as empirical finding."
      udp_blocked=1
    fi
  fi

  if (( checks_passed == 1 )); then
    echo "[Preflight] Status: GO (All critical checks passed)"
    return 0
  else
    echo "[Preflight] Status: NO-GO (Critical checks failed)" >&2
    return 1
  fi
}

if (( SKIP_PREFLIGHT == 0 )); then
  if ! run_preflight; then
    if (( TEST_MODE == 1 )); then
      exit 1
    else
      echo "Error: Preflight failed. Use --skip-preflight to override." >&2
      exit 1
    fi
  fi
fi

if (( TEST_MODE == 1 )); then
  echo "Test mode complete: System is ready for Campus capture."
  exit 0
fi

# Run Capture
STAMP="$(date -u +%Y%m%d_%H%M%S)_$$"
RUN_DIR="data/raw/network_runs/${NETWORK}-${STAMP}"
LOCK_FILE="data/raw/capture.lock"

# Calculate estimated jobs
TOTAL_JOBS=$(( ${#RESOLVERS[@]} * ${#PROTOCOLS[@]} * DOMAIN_LIMIT * 2 * REPEATS ))
echo ""
echo "Capture Plan: $TOTAL_JOBS queries scheduled."
echo "Output Directory: $RUN_DIR"

if [[ -e "$LOCK_FILE" ]]; then
  echo "Error: Capture lock file exists at $LOCK_FILE. Another capture may be active." >&2
  exit 1
fi

mkdir -p "$RUN_DIR"
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT INT TERM

CMD=("$PYTHON_BIN" "src/probe_and_capture.py" \
  --iface "$INTERFACE" \
  --network "$NETWORK" \
  --machine-label "$MACHINE_LABEL" \
  --batch "$NETWORK" \
  --run-id "${NETWORK}-${STAMP}" \
  --run-dir "$RUN_DIR" \
  --workload both \
  --limit "$DOMAIN_LIMIT" \
  --resolvers "${RESOLVERS[@]}" \
  --protocols "${PROTOCOLS[@]}" \
  --repeats "$REPEATS" \
  --repeat-start 0 \
  --shuffle-from 0 \
  --resume)

if [[ -n "$Q_BIN" ]]; then
  CMD+=(--q-path "$Q_BIN")
fi

if (( DRY_RUN == 1 )); then
  CMD+=(--dry-run)
  echo "Running in DRY-RUN mode (manifest simulation)..."
fi

echo "Executing capture process..."
"${CMD[@]}"

echo ""
echo "Capture execution complete."
echo "Manifest and PCAPs saved to: $RUN_DIR"
