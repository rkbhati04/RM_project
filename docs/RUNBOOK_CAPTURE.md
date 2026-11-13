# Capture runbook

Install Python, Wireshark with Npcap, and `q`. Before each session, confirm the active capture interface, resolver reachability, available disk space, and that only test traffic will be captured. Use a label such as `jio` or `campus`; never record a raw hostname or public IP. For a phone hotspot, enable the hotspot, connect the laptop to its SSID, and confirm the active interface. Confirm UDP 443 is not blocked with the approved live preflight.

Run one fresh query per capture, keep repeats as the outer loop, randomize new repeats, never run concurrent queries to one resolver, and resume interrupted batches. After a session, run `python -m encdns status`, inspect failures by resolver and protocol, and preserve the manifest even when captures fail.

Before an overnight session, turn the VPN off, use one access network, pause Windows Update, and prevent sleep (`powercfg /change standby-timeout-ac 0` in an elevated Windows terminal; restore your normal setting afterwards). On macOS use `caffeinate -i`; on Linux use `systemd-inhibit`. Keep analysis limited to two threads or fewer while capturing.

The Airtel overnight plan has 19,200 captures. The existing manifest's median capture-start gap is 4 seconds, or 21.3 hours; with a 20% margin, schedule **about 25.6 hours**. The supplied wrappers wait 60 seconds after a failed driver invocation and stop after three consecutive failures.

The overnight wrappers create a new UTC-stamped directory under
`data/raw/overnight_runs/` for every invocation and pass it as `--run-dir`.
Each run therefore has its own `manifest.csv` and `pcaps/`; it never appends to
the historical `data/raw/manifest.csv` or reuses historical PCAP paths.
Do not pass the shared manifest or PCAP directory when collecting overnight
data. Analyze a run by passing that run's manifest explicitly to downstream
tools.

Do not capture other users' traffic or commit pcaps, credentials, raw public IPs, or resolver profile identifiers. Nothing else runs on the capture laptop during collection.
