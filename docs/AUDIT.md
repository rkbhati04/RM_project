# Repository Audit

Date: 2026-11-09

## Verified state

- The processed dataset has 2,797 rows from four resolvers, 50 domains, and Airtel only.
- The raw manifest has 3,843 records; 2,934 are successful captures.
- The scope is DoH and DoH/3. No DoQ records occur in the active manifests or dataset.
- `data_status.py` reports a hard-coded `50/50 complete` value and an obsolete run order.
- `plot_results.py` contains typed-in matrices, accuracies, and feature importances rather than reading result tables.
- `run_experiments.py` is a stale single-split runner with a resistance score and incompatible evaluation rules.
- `doh3_rq123_analysis.py` uses a fixed seed, low-permutation quick analysis behaviour, and mixes a percentile comparison with empirical p-values.

## Audit commands run

```text
python src/data_status.py
python src/doh3_rq123_analysis.py --quick
python -m compileall -q src
```

The status command completed. The legacy DoH/3 analysis began and loaded the expected dataset, but is unsuitable as the project entry point because it does not implement a consistent, multi-seed evaluation protocol.

## Git note

Creating the requested `setup/restructure` branch failed because this checkout could not create the nested ref `refs/heads/setup/restructure`. No branch or remote was changed. The repository already has an `origin` remote; no push was attempted.

## Refactor direction

The new `encdns` package and CLI are the supported interface. The legacy scripts remain as compatibility wrappers only until the team removes them after reviewing the new outputs.

## Additional verified defects

- `doh3_rq123_analysis.py` contains numeric report prose, including stale workload counts, instead of deriving prose from result tables.
- Its report language makes a protocol-comparison claim although the script analyses DoH/3 only.
- Its RQ2 output uses a derived resistance score instead of accuracy, interval, and p-value.
- Its MDI-only importance output is biased toward continuous features; permutation importance is absent.
- The legacy capture filter was previously hard-coded to port 443.
- Legacy scripts use inconsistent random seeds and a ten-tree permutation model despite a larger real model.

## Capture-path remediation

The capture driver now uses a backward-compatible extended manifest, per-protocol port mappings, configurable q JSON parsing, structured metadata fields, and a no-network dry-run. A six-row dry-run (three domains by two protocols) passed on 2026-11-09.
