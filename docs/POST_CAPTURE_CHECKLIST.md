# Post-capture checklist

Do not run this checklist while a capture is active. Use the completed run's
manifest and PCAP directory, not the shared historical files.

## Required live q comparison

After capture completion, run exactly two single-domain queries with identical
flags except transport, save the raw JSON, and compare the parsed answer,
CNAME, and TTL records:

```powershell
q example.com A @https://dns.adguard-dns.com/dns-query --opt --http2 --format=json > doh.json
q example.com A @https://dns.adguard-dns.com/dns-query --opt --http3 --format=json > doh3.json
```

Repeat for a resolver/domain representative of any mismatch found in the
snapshot. Preserve both raw JSON files locally and record q version, flags,
resolver, domain, and timestamp. Do not commit raw public IPs or raw JSON
containing sensitive data.

## Top-up pass

Run this only after the overnight process has exited and in daytime, not while
the original capture is active. Reuse the same run directory and manifest; the
driver's `--resume` considers only successful rows at or below the latency
cutoff complete, so failed, `bad_metadata`, slow, and missing-PCAP rows are
eligible for retry:

```powershell
python src\probe_and_capture.py --iface "Wi-Fi" --network airtel `
  --batch T0 --run-id <same-run-id> --run-dir data\raw\overnight_runs\<same-run> `
  --workload both --all-domains --resolvers adguard cloudflare google quad9 `
  --protocols doh doh3 --repeats 12 --repeat-start 8 --shuffle-from 8 --resume
```

The retry reads `data\raw\overnight_runs\<same-run>\manifest.csv` and writes
new rows and PCAPs in that same run folder. Confirm the capture lock is absent
before starting the daytime top-up.

## Snapshot comparison

- Confirm the snapshot timestamp and source run directory.
- Compare `answer_count`, `cname_count`, and `ttl_min` by resolver/domain.
- Report `answer_count` disagreement and `cname_count` disagreement separately,
  including counts and shares; do not combine them into one disagreement field.
- Report TTL differences separately. TTL differences reflect resolver cache
  state and are not a protocol effect.
- Treat mismatches as evidence requiring the two-query live comparison, not as
  proof of protocol-specific DNS behavior.

## Health and padding

- Confirm 28 manifest columns (including salted `machine_id`) and uniform row width.
- Report status, latency-cutoff, and hourly success tables per resolver/protocol.
- Recheck packet-size clustering as an inference only; q output does not prove
  EDNS0 padding presence.
- For one completed query per resolver and protocol, inspect q's raw JSON and
  check whether the response OPT record contains an EDNS0 padding option.
