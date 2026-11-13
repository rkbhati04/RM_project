# Teammate network collection quickstart

## Install and clone

Install Python 3, Wireshark/Npcap (including `dumpcap` and `tshark`), and q.
Clone the repository, create/activate the project virtual environment, and
run commands from the repository root.

Use a network label such as `jio` or `campus`. To use a
phone hotspot, enable the phone's hotspot, connect the laptop to that SSID,
and verify the laptop's active interface before preflight. Confirm UDP 443 is
not blocked with the preflight live check; use `--no-live` only while another
capture is active. Nothing else may run on the capture laptop during a run.

## Preflight

On PowerShell:

```powershell
.\scripts\preflight.ps1 -Network airtel_home -Interface "Wi-Fi" -NoLive
```

On Bash:

```bash
./scripts/preflight.sh --network airtel_home --interface Wi-Fi --no-live
```

Omit `--no-live` only when no capture lock exists and a one-query live test is
approved. A `NO-GO` must be fixed before collection.

## Start the run

PowerShell:

```powershell
.\scripts\run_network.ps1 -Network airtel_home -Interface "Wi-Fi"
```

Bash:

```bash
./scripts/run_network.sh airtel_home Wi-Fi
```

The default run uses the first 50 Global and first 50 India domains, three
resolvers, two protocols, and ten repeats (6,000 jobs), with shuffled order
and resume support. Estimated duration is about 7.5 hours with a 20% margin.
Use labels such as `jio` or `campus`; do not use personal
names or raw locations. The run writes to its own directory under
`data/raw/network_runs/` and creates a capture lock.

## Morning checks and handoff

Check the run manifest for uniform 28-column rows, status counts, missing PCAPs,
latency over 1.5 seconds, and query failures. Confirm the lock is gone only
after the process exits. Send the run directory name, manifest summary,
failure notes, and network label to the study owner; do not send raw public
IPs, credentials, or unapproved PCAPs.
