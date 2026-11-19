# KU1 — Airtel WP3–WP6 Results Review

**Reviewer:** Kunal  
**Date:** 2026-11-14  
**Run reviewed:** `results/airtel_final_20261111/`  
**Reference:** `docs/METHODOLOGY.md`, `docs/TEAM_PLAN.md`

---

## 1. What Was Checked

- `results/airtel_final_20261111/REPORT.md` — headline fingerprinting table (WP3/WP4)
- `results/airtel_final_20261111/rq1_rq2_fingerprinting.csv` — raw numbers backing the report
- `results/airtel_final_20261111/baselines.csv` — WP4 length-only baselines
- `results/airtel_final_20261111/run_metadata.json` — evaluation config
- `results/airtel_final_20261111/checkpoint_*.json` — per-slice checkpoints (all 16 slices)
- `results/airtel_final_20261110/qa_summary.txt` — dataset health and domain-set policy
- `results/airtel_final_20261110/confounds.txt` — capture success rates by repeat and hour
- `docs/claims_ledger.csv` — recorded claims (FP-1 through FP-16)
- `docs/AUDIT.md` — prior audit findings
- `docs/OPEN_ITEMS.md` — known open issues

---

## 2. Methodology Compliance Checklist

| Check | Expected (per METHODOLOGY.md) | Observed | Status |
|---|---|---|---|
| Folds | 5 grouped folds, 2 repeats held out | `"5 folds, 2 repeats held out"` in `run_metadata.json` | ✅ |
| Real trees | 100 | `"real_trees": 100` | ✅ |
| Null trees | 50 | `"null_trees": 50` | ✅ |
| Permutations | 200 | `"n_permutations": 200` on all rows | ✅ |
| Target k | 10 repeats per domain | `"target_k": 10` | ✅ |
| Wilson intervals | Required | `ci_low`/`ci_high` present on all rows | ✅ |
| Empirical p-values | Required | `p_value` present on all rows | ✅ |
| Feature exclusions | No IPs, ports, labels | Not directly verifiable from outputs; assumed enforced by pipeline | ⚠️ Cannot verify from outputs alone |
| Domains per slice | ≥ 60 for k=10 policy | Global: 99–100 ✅; India: 85–100 — see anomaly A2 below | ⚠️ |
| Non-significant = "no detectable leakage" | Stated in report | Present at bottom of REPORT.md | ✅ |
| Machine label | Salted token only, no hostname | `run_metadata.json` has no hostname field | ✅ |
| Commit hash in ledger | Required | All 16 claims show `"unrecorded"` — **see anomaly A1** | ❌ |

---

## 3. Anomalies and Flags

### 🔴 A1 — Commit hash missing from all claims ledger entries (Critical)

**File:** `docs/claims_ledger.csv`  
**All 16 entries (FP-1 through FP-16) have `commit = "unrecorded"`.**

This violates the team rule: *"No result number is typed by hand; numbers come from `results/` and the claims ledger."* Without a commit hash, there is no way to link each ledger value back to the exact code and dataset that produced it. Verification round S1 on 15 Nov requires this linkage.

**Action required:** Re-run `python -m encdns ledger` (or equivalent) after confirming the git commit that produced `airtel_final_20261111/`, and backfill the `commit` column for FP-1 through FP-16.

---

### 🟡 A2 — India domain survival at k=10 is below the 60-domain threshold for AdGuard

**File:** `results/airtel_final_20261110/qa_summary.txt`

```
quad9/doh3 k10=64  k8=92  (India)
adguard/doh k10=65  k8=74  (India)
adguard/doh3 k10=65  k8=74 (India)
intersection_k10=40
intersection_k8=64
recommendation=use intersection k10 ... India retains 40/100 (<60%), so report k8=64 as sensitivity
```

The `qa_summary.txt` explicitly recommends **k8=64 as headline for India** because k=10 yields only 40 domains (< the 60-domain threshold in TEAM_PLAN.md). However, `REPORT.md` and `rq1_rq2_fingerprinting.csv` report **all India slices at k=10** (87–100 domains per slice), not the intersection of 40.

This discrepancy means each India slice is evaluated on its own surviving domains rather than the common intersection set. Cross-resolver comparisons for India (WP5) are therefore **not on a matched domain set**, which is a methodological inconsistency. The numbers are real but should be labelled as unmatched-domain results, not as direct resolver comparisons.

**Action required:** Confirm with the project lead whether the per-slice evaluation was intentional. If WP5 India comparisons are being made, they must note the unmatched domain set, or be rerun on the intersection (k8=64 India).

---

### 🟡 A3 — Quad9 DoH/3 completion rate is notably lower than other slices

**File:** `results/airtel_final_20261110/confounds.txt` and `qa_summary.txt`

```
quad9/doh3 repeats=8:164/200, 9:163/200, ... 19:145/200
quad9/doh3 k10=85 (Global), k10=64 (India)
```

Quad9 DoH/3 completes only 145–186/200 jobs per repeat (73–93%), while all other slices are 90–100%. The `confounds.txt` notes:  
> *"Quad9 doh3 failures are concentrated across repeats and hours rather than one domain alone; hour 08–09 and 18 have lower observed rates across slices, indicating time-of-day drift/throttling risk."*

This is consistent with the README's finding (~85% Quad9 QUIC completion). The result is valid but must be **stated explicitly** in the paper as a limitation when Quad9 results are discussed. The paper must not rank Quad9 DoH/3 against other resolvers' DoH/3 without noting the lower sample and survival rate.

**Action required:** Add a limitation note to the paper text when Quad9 DoH/3 results appear in tables or comparisons. Flag for AM6 (Aman's paper-writing task).

---

### 🟡 A4 — WP5 and WP6 outputs are absent from `airtel_final_20261111/`

**File:** `results/airtel_final_20261111/` directory listing

The directory contains WP3 (`rq1_rq2_fingerprinting.csv`) and WP4 (`baselines.csv`) outputs. There are **no files for WP5 (resolver comparison) or WP6 (Global vs India)**. The `progress.log` ends with `"WP3/WP4 headline analyses complete"` at 4738s, then jumps to `"complete"` at 9224s with no WP5/WP6 log lines.

This means WP5 and WP6 either:
- ran and produced no separate output files (results embedded elsewhere), or
- did not run / were not part of this analysis script.

**Action required:** Confirm with the project lead what the 9224s–4738s = ~4486s of post-WP4 compute produced, and where WP5/WP6 outputs are stored. If WP5/WP6 have not been run yet, this is a gap that must be filled before KU4 and KU6.

---

### 🟡 A5 — Google DoH and DoH/3 accuracies are nearly identical (unexpected)

**File:** `results/airtel_final_20261111/rq1_rq2_fingerprinting.csv`

```
global/google/doh  accuracy=0.1693
global/google/doh3 accuracy=0.1687
```

For every other resolver, DoH/3 accuracy is substantially lower than DoH (AdGuard: 0.279 vs 0.080; Cloudflare: 0.212 vs 0.054; Quad9: 0.347 vs 0.041). Google is the only resolver where DoH and DoH/3 accuracy are within 0.001 of each other. This is counter-intuitive and may reflect that Google's DoH/3 responses are structured similarly to its DoH responses (same CDN, same padding behaviour), or a data artefact.

**Action required:** Flag this for WP3 (DoH vs DoH/3 head-to-head) analysis. The bootstrap comparison for Google should be reported and explicitly discussed. This is not necessarily an error — it may be a genuine finding — but it needs a stated explanation.

---

### 🟢 A6 — Baselines correctly show negative effect-over-length for DoH/3 (expected)

**File:** `results/airtel_final_20261111/baselines.csv`

All DoH/3 slices show negative `effect_over_length` (full model performs *worse* than length-only baseline). This is the expected result for DoH/3, where HTTP/3 framing and multiplexing add noise that actually hurts the classifier beyond what name-length alone provides. This is internally consistent and matches the paper's RQ2 finding.

No action required.

---

### 🟢 A7 — All p-values are at the minimum resolvable level (expected)

All 16 slices: `p_value = 0.004975124378109453` (= 1/201, the minimum for 200 permutations).  
All results are significant. This is consistent: every slice has accuracy well above chance. No anomaly.

---

### 🟡 A8 — `run_metadata.json` domain counts differ from `qa_summary.txt`

**File:** `results/airtel_final_20261111/run_metadata.json`

```json
"domain_counts": { "global": {"k10": 100, "k8": 100}, "india": {"k10": 100, "k8": 100} }
```

But `qa_summary.txt` reports `intersection_k10=84` (Global) and `intersection_k10=40` (India). The metadata records 100 domains for both workloads at both k values, while the QA report shows far fewer survive the intersection policy.

This suggests the analysis was run **per-slice** (each resolver/protocol evaluated independently on its own surviving domains), not on the **shared intersection**. That is not wrong per se, but it means the `domain_counts` in `run_metadata.json` reflects the per-slice count for the best-performing slices, not the matched set. This directly relates to A2.

**Action required:** Clarify in the paper and claims ledger that domain counts are per-slice, not an intersection. Add a note to WP5 results stating that cross-resolver comparisons use unmatched domain sets.

---

## 4. Summary

| Severity | Count | IDs |
|---|---|---|
| 🔴 Critical | 1 | A1 (missing commit hashes in claims ledger) |
| 🟡 Needs attention | 5 | A2, A3, A4, A5, A8 |
| 🟢 OK / expected | 2 | A6, A7 |

**Overall assessment:** The core evaluation protocol (folds, trees, permutations, Wilson intervals) is correctly implemented and matches `METHODOLOGY.md`. The numbers appear internally consistent. However:

1. **The claims ledger must be backfilled** with commit hashes before S1 verification is possible.
2. **WP5 and WP6 outputs are missing** — confirm their location before writing the paper.
3. **India cross-resolver comparisons must note the unmatched domain set** (intersection is only 40 domains at k=10, below the 60-domain policy threshold).
4. **Google's DoH ≈ DoH/3 accuracy** is a genuine finding that needs an explicit discussion in WP3.
5. **Quad9 DoH/3 completion rate** must be stated as a limitation whenever Quad9 appears in comparisons.
