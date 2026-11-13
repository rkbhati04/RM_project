# Experiment Protocol Template

Fill this before collecting the first trace. A completed copy is the source of
truth for each collection batch.

## Batch identity

- Batch ID:
- Collector and date/time zone:
- OS and client tool/version:
- Access-network label and connection type:
- Consent/privacy check (only test traffic captured):

## DNS configuration

| Field | DoH | DoH/3 |
| --- | --- | --- |
| Resolver name and endpoint | Yes | Yes |
| Client command/configuration | | |
| Verified negotiated transport | | |
| Record type | A | A |
| Timeout/retry policy | | |
| Cache-clearing procedure | | |

## Workload and collection

- Workload manifest version:
- Domains per group:
- Repetitions per domain:
- Ordering/randomization method:
- Capture interface and filter:
- PCAP filename convention: `<batch>_<protocol>_<resolver>_<network>_<domain-id>_<trial>.pcapng`
- Run isolation: each collection run uses its own `data/raw/overnight_runs/<UTC-stamp>/`
  directory containing `manifest.csv` and `pcaps/`; historical manifests and PCAPs are read-only.

## Post-capture validation

- [ ] Query completed successfully.
- [ ] Protocol negotiation is present in the trace/log.
- [ ] Capture contains only test traffic for this trial.
- [ ] Domain ID maps to the workload manifest without ambiguity.
- [ ] Failures/retries are recorded rather than discarded silently.
