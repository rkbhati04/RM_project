# Project To-Do

Combined checklist for the remaining project work.

## Immediate setup and validation

- [x] Install or locate `q` and run the eight serialized live checks.
- [x] Save the live-check JSON outputs under `docs/live_checks/`.
- [x] Update `docs/LIVE_CHECKS.md` with answer/CNAME parity, extra records, and EDNS0 padding findings.
- [x] Run the final Airtel top-up pass for failed and slow captures. Imported run evidence: 20,262 manifest rows covering 19,200 unique capture keys, including 1,062 retries.
- [x] Recompute the final Airtel dataset, drop reasons, domain-set policy, and success-rate summaries.
- [x] Complete the Airtel integrity reset and verify that all headline results use the agreed seeds, 200 permutations, and target repeat policy.

## Jio network

- [ ] Obtain permission and prepare the Jio capture laptop.
- [ ] Run the Jio matrix: Cloudflare, Google, and AdGuard; DoH and DoH/3; first 100 domains; 10 shuffled repeats.
- [ ] Merge the Jio manifest and extract Jio features.
- [ ] Run within-Jio fingerprinting (N1).
- [ ] Run Airtel-to-Jio and Jio-to-Airtel transfer tests (N2).
- [ ] Run pooled multi-network training and per-network evaluation (N3).
- [ ] Produce Jio network-health summaries (N8).

## Airtel analyses

- [x] Run DoH vs DoH/3 head-to-head comparisons with the configured evaluation protocol (WP3).
- [x] Run baselines and headline fingerprinting analysis (WP4).
- [x] Generate Airtel resolver comparison outputs (WP5).
- [x] Generate Global vs Indian workload outputs (WP6).
- [x] Review all Airtel WP3-WP6 outputs against `docs/METHODOLOGY.md`.
- [x] Add verified results to `docs/claims_ledger.csv`.

## Additional analysis

- [ ] Implement and evaluate richer packet-size, burst n-gram, and post-handshake features (WP7).
- [ ] Generate accuracy-vs-domain-count and accuracy-vs-repeat scaling curves (WP10). Script ready: `python3 scripts/run_airtel_scaling.py`.
- [ ] Compare pilot repeats with T0 for time stability (WP11).
- [ ] Analyze cross-network feature shift, resolver ranking consistency, per-network DoH vs DoH/3, and Global vs Indian behavior (N4-N7).
- [ ] Train and evaluate CNN/GRU sequence models if time permits (WP8).
- [ ] Add open-world monitored-vs-unmonitored evaluation if time permits (WP9).
- [ ] Simulate padding and delay defenses, clearly labelled as simulations (WP13).
- [ ] Re-run the final analyses after all accepted datasets are merged.

## Paper and slides

- [ ] Write the Introduction.
- [ ] Write Related Work and include the research gap.
- [ ] Write the Threat Model and Methodology.
- [ ] Write Results for RQ1-RQ5 using only verified ledger values.
- [ ] Write Discussion, Limitations, Ethics, and Reproducibility sections.
- [ ] Create the slide deck using figures generated from `results/`.
- [ ] State all exclusions and limitations: page loads, other clients, DoQ, ODoH, and Quad9 on Jio.

## Verification and release

- [ ] Each teammate’s work is independently recomputed from the raw CSVs.
- [ ] Verify every paper and slide number against `docs/claims_ledger.csv`.
- [ ] Fix all ledger mismatches and regenerate affected outputs.
- [ ] Run the test suite and required lint/type checks.
- [ ] Confirm no pcaps, credentials, raw IPs, or tool/assistant names are committed.
- [ ] Clean up README and reproduction instructions.
- [ ] Proofread the paper, slides, and repository documentation.
- [ ] Create the final repository tag and submit.

## Optional or cut-first work

- [ ] Browser-driven page-load traces (WP12).

If time is limited, cut WP12 first, then CNN/GRU, defense simulations, and open-world analysis. Do not cut baselines, integrity checks, or verification.
