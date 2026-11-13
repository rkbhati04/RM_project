# Project To-Do

Combined checklist for the remaining project work.

## Current handover context

- Current branch: `main`.
- Current branch tip after the latest organization commit: `b60605b`.
- `main` is ahead of `origin/main`; do not push unless explicitly requested.
- The working tree is clean. The ignored imported Airtel raw directory is intentionally present.
- Airtel live checks, top-up processing, dataset recomputation, and core WP3-WP6 analysis are complete.
- No Airtel hotspot is needed for local feature extraction or analysis.
- Jio hotspot connectivity is required only for live Jio capture and network-health measurements.
- Campus work is permanently out of scope for this project.

### Airtel data and results

- Imported raw Airtel data is stored outside Git under `data/raw/airtel_T0_raw_20261111/`.
- The imported run contains 20,262 manifest rows representing 19,200 unique capture keys and 1,062 retry rows.
- The latest retry status recovered 789 captures to `ok`; 273 retry attempts remained non-`ok`.
- The extractor produced 18,926 feature rows in `data/processed/dataset_v2.csv`.
- One row was dropped for `too_few_packets`; drop details are in `data/processed/drop_reasons_v2.csv`.
- The final headline policy selected `k=10`.
- Both Global and India retained 100 domains at `k=10`.
- Core Airtel output directory: `results/airtel_topup_20261113/`.
- Core report: `results/airtel_topup_20261113/REPORT.md`.
- Core result table: `results/airtel_topup_20261113/rq1_rq2_fingerprinting.csv`.
- Core baselines: `results/airtel_topup_20261113/baselines.csv`.
- The result table contains 16 slices: 2 workloads x 4 resolvers x 2 protocols.
- Resolvers: AdGuard, Cloudflare, Google, and Quad9.
- Protocols: DoH and DoH/3.
- Headline analysis uses repeats 8-19, configured seeds 17/42/101, and 200 permutations.
- Claims ledger: `docs/claims_ledger.csv`, currently containing 16 Airtel entries.
- Live-check raw JSON files are ignored under `docs/live_checks/`; findings are documented in `docs/LIVE_CHECKS.md`.
- The eight live checks completed with q 0.19.12. Google showed a one-observation answer-count mismatch between HTTP/2 and HTTP/3; no exposed EDNS0 padding option was observed.

### Airtel commands

Run from the repository root.

Recompute features from the imported Airtel manifest:

```bash
python3 src/extract_features.py \
  --manifest 'data/raw/airtel_T0_raw_20261111/20261109_230331_22448\manifest.csv' \
  --root . \
  --output data/processed/dataset_v2.csv \
  --drops data/processed/drop_reasons_v2.csv \
  --cache data/processed/.extract_cache_airtel_topup.json \
  --workers 4 \
  --max-latency 1.5
```

Run the supported core Airtel analysis with saved-checkpoint resume:

```bash
PYTHONPATH=src python3 -m encdns analyze \
  --run-id airtel_topup_20261113 \
  --permutations 200 \
  --resume
PYTHONPATH=src python3 -m encdns report airtel_topup_20261113
PYTHONPATH=src python3 -m encdns ledger airtel_topup_20261113
```

Run the defined Airtel-only remaining analyses:

```bash
./scripts/run_airtel_analysis.sh --skip-advanced
```

Run the faster exploratory variant:

```bash
./scripts/run_airtel_analysis.sh --quick --skip-advanced
```

The runner executes the core pipeline plus WP7, WP10, and WP11. It does not
perform Jio work. The optional E1-E5 legacy analysis can be enabled by omitting
`--skip-advanced`, but it is computationally expensive.

Standalone WP10 command:

```bash
python3 scripts/run_airtel_scaling.py
```

WP7/WP11 standalone command:

```bash
python3 scripts/run_airtel_defined_analysis.py
```

### Script and analysis limitations

- `scripts/run_airtel_analysis.sh` is an Airtel-only local runner.
- `scripts/run_airtel_scaling.py` generates `results/airtel_scaling_20261113/scaling_curves.csv` and `scaling_curves.png`.
- `scripts/run_airtel_defined_analysis.py` generates WP7 and WP11 CSV outputs under `results/airtel_defined_20261113/`.
- WP7 currently computes packet-size and post-handshake n-grams.
- True burst n-grams are not reported because the committed feature table stores burst aggregates, not the original burst sequence.
- The legacy `analysis_v2.py` full run was too slow for interactive completion; only its E1 protocol-identification output was produced during the attempted run.
- Do not describe the burst n-gram part of WP7 as completed unless burst sequences are extracted from PCAPs.
- Do not describe cross-network effects or Jio results until Jio captures and analyses exist.
- Synthetic data must never be presented as measured Jio data.

### Relevant commits

- `0924696`: merged `handover` into `main`.
- `1af9073`: recorded live q protocol checks.
- `3c70995`: recorded Airtel top-up status.
- `4279809`: committed recomputed Airtel dataset, core results, ledger, and documentation.
- `6b49466`: added the Airtel core/advanced analysis runner.
- `52eb8b5`: added the Airtel scaling script.
- `1783e4c`: separated Airtel and Jio work in this checklist.
- `35dced7`: added the defined Airtel WP7/WP11 runner.
- `a6f1708`: added earlier handover context.
- `b60605b`: organized imported Airtel raw data under ignored storage.

### Defined Airtel analysis command

Run from the repository root:

```bash
./scripts/run_airtel_analysis.sh --skip-advanced
```

For a faster exploratory run:

```bash
./scripts/run_airtel_analysis.sh --quick --skip-advanced
```

The runner executes the core Airtel pipeline plus WP7, WP10, and WP11. WP7
reports packet-size and post-handshake n-grams; true burst n-grams are not
reported because the processed dataset contains burst aggregates rather than
the original burst sequences.

## Airtel work completed

- [x] Install or locate `q` and run the eight serialized live checks.
- [x] Save the live-check JSON outputs under `docs/live_checks/`.
- [x] Update `docs/LIVE_CHECKS.md` with answer/CNAME parity, extra records, and EDNS0 padding findings.
- [x] Run the final Airtel top-up pass for failed and slow captures. Imported run evidence: 20,262 manifest rows covering 19,200 unique capture keys, including 1,062 retries.
- [x] Recompute the final Airtel dataset, drop reasons, domain-set policy, and success-rate summaries.
- [x] Complete the Airtel integrity reset and verify that all headline results use the agreed seeds, 200 permutations, and target repeat policy.

## Airtel work remaining

- [ ] Implement and evaluate richer packet-size, burst n-gram, and post-handshake features (WP7). Runner: `python3 scripts/run_airtel_defined_analysis.py`.
- [ ] Generate accuracy-vs-domain-count and accuracy-vs-repeat scaling curves (WP10). Script ready: `python3 scripts/run_airtel_scaling.py`.
- [ ] Compare pilot repeats with T0 for time stability (WP11). Runner: `python3 scripts/run_airtel_defined_analysis.py`.
- [ ] Train and evaluate CNN/GRU sequence models if time permits (WP8).
- [ ] Add open-world monitored-vs-unmonitored evaluation if time permits (WP9).
- [ ] Simulate padding and delay defenses, clearly labelled as simulations (WP13).

## Jio work remaining

- [ ] Obtain permission and prepare the Jio capture laptop and hotspot.
- [ ] Run the Jio matrix: Cloudflare, Google, and AdGuard; DoH and DoH/3; first 100 domains; 10 shuffled repeats.
- [ ] Merge the Jio manifest and extract Jio features.
- [ ] Run within-Jio fingerprinting (N1).
- [ ] Run Airtel-to-Jio and Jio-to-Airtel transfer tests (N2).
- [ ] Run pooled multi-network training and per-network evaluation (N3).
- [ ] Produce Jio network-health summaries (N8).
- [ ] Analyze cross-network feature shift, resolver ranking consistency, per-network DoH vs DoH/3, and Global vs Indian behavior (N4-N7).
- [ ] Re-run final combined analyses after Jio data is merged.

## Paper and slides

- [ ] Write the Introduction.
- [ ] Write Related Work and include the research gap.
- [ ] Write the Threat Model and Methodology.
- [ ] Write Airtel Results using only verified ledger values.
- [ ] Add Jio and cross-network Results after Jio analysis is complete.
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
