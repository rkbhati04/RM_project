# Team Plan: Remaining Work (2026-11-11 to 2026-11-17)

This file supersedes every earlier network plan in `HANDOVER.md`, the runbook, the quickstart and `docs/issues/`. Two teammates carry the project from here: **Aman** and **Kunal**. Work continues until the night of **2026-11-17**.

---

## 1. Networks, machines and dates

| Network | Label | Who captures | Machine | When |
|---|---|---|---|---|
| Airtel | `airtel` | Project lead (done) | Project lead's laptop | Complete |
| Jio | `jio` | **Aman** | Aman's laptop | **Night of 11 Nov**, data ready 12 Nov morning |
| College WiFi | `campus` | **Kunal** | Kunal's laptop | **16 Nov**, after reaching college; data ready 17 Nov morning |

**Machine confound.** Each network comes from a different laptop. Prior work (Siby et al.) found that classifiers do not transfer across platforms, so **every cross-network result is "network + machine"**. Label it that way in tables and text. A cheap control, strongly recommended: on **16 Nov Aman also runs the campus matrix on his laptop** at the same time as Kunal. Campus on two laptops measures the machine effect directly, and Aman's Jio vs Campus then becomes a within-machine comparison.

**Capture matrix for Jio and Campus (identical):** cloudflare, google, adguard x DoH, DoH/3 x the first 100 domains (first 50 Global + first 50 India) x 10 repeats, shuffled order. That is 6,000 captures, about 6 hours plus 20% margin (about 7.5 hours). Quad9 is left out because its DoH/3 success rate on Airtel was lowest. Quad9 therefore has Airtel data only, and the paper says so.

During any capture, nothing else runs on that laptop: no VPN, no network switching, no sleep, no heavy jobs. Do analysis on another machine.

---

## 2. Status at handover (Airtel)

- Capture finished (19,200 jobs) and a top-up pass recovered 789 of 1,062 failed or slow jobs. About 273 remain failed, mostly AdGuard and Quad9 DoH/3. These failures are persistent, so no further top-up is planned.
- `data/processed/dataset_v2.csv` has 21,723 feature rows (repeats 8-19 plus pilot repeats 0-7).
- **Shared domain sets** (domains with at least 10 successful repeats in all 8 resolver x protocol slices, repeats 8-19): **Global 99, India 79**. At k=8: Global 100, India 91. The rule is k=10 for both workloads (both exceed 60 domains).
- `results/airtel_final_20261111` is **provisional**. It is real output but has two known problems:
  1. Each slice used its own surviving domains (the `domains` column varies, for example 99, 100, 87, 85) instead of the shared set. Per-slice accuracy is usable, but resolver, protocol and workload comparisons are not valid until it is rerun on the shared set.
  2. `run_metadata.json` reports 100 and 100 for the domain counts. That is the workload size, not the shared-set size.
- It also lacks RQ3 (feature importance and ablation), pairwise bootstrap tests, anonymity sets, the Global vs Indian distribution comparison, and figures.
- The raw Airtel data (pcaps and manifest) is shared outside git in a zip with checksums. Only WP7 needs it.

---

## 3. Work packages

| WP | What it is |
|---|---|
| WP1 | Integrity reset: no hardcoded results, one significance rule, multi-seed spread (done in code) |
| WP2 | Capture upgrades: new manifest columns, health reports (done) |
| WP3 | DoH vs DoH/3 head-to-head per resolver, with bootstrap comparisons |
| WP4 | Baselines (name length, answer count, size only) and anonymity sets |
| WP5 | Resolver comparison and cross-network comparison |
| WP6 | Global vs Indian workloads |
| WP7 | Richer features: packet-size and burst n-grams, post-handshake-only features |
| WP8 | 1D-CNN and GRU on packet-size sequences |
| WP9 | Open-world: monitored vs unmonitored domains |
| WP10 | Scaling curves: accuracy vs number of domains and repeats |
| WP11 | Time stability: pilot (repeats 0-7, 50 domains) vs T0 (repeats 8-19). No new capture. Caveats: gap of days to weeks, different capture order. |
| WP12 | Page-load traces (optional) |
| WP13 | Defense what-ifs: simulate 128/468-byte padding and random delay |

### Network analyses (from the first Jio data; re-run when Campus arrives)

| # | Analysis |
|---|---|
| N1 | Within-network fingerprinting per network, resolver and protocol, on the shared domain set |
| N2 | Cross-network transfer: train on one network, test on another, both directions |
| N3 | Pooled training across networks, test per network |
| N4 | Feature shift: which feature groups change distribution across networks, plus per-network ablation |
| N5 | Resolver ranking consistency across networks |
| N6 | DoH vs DoH/3 per network |
| N7 | Global vs Indian per network |
| N8 | Network health: success rate, latency, UDP/QUIC blocking, by hour |
| N9 | With Campus data: leave-one-network-out, and the machine-effect check (Campus on two laptops) |

Rules: same domain set on every network, same k, 200 permutations, intervals everywhere, no ranking unless the bootstrap difference is significant. Quad9 is excluded from cross-network analyses.

---

## 4. Who does what

### Kunal

| ID | Task | When |
|---|---|---|
| **KU1** | **Rerun the Airtel analysis on the shared domain sets and add the missing outputs.** Full spec in section 5. Start in the evening of 11 Nov and let it run overnight on his own laptop. | **11 Nov** |
| KU2 | Review the KU1 results against `METHODOLOGY.md`; flag anything odd | 12 Nov |
| KU3 | WP7 richer features (start on `dataset_pilot_v1.csv`, rerun on `dataset_v2.csv`) while KU1 runs | 11-12 Nov |
| KU4 | WP10 scaling curves, WP11 pilot-vs-T0 stability | 12-13 Nov |
| KU5 | N4, N5, N6, N7 as soon as Jio data is merged | 12-14 Nov |
| KU6 | WP8 CNN and GRU, WP9 open-world, WP13 defense simulations | 13-15 Nov |
| KU7 | Paper text: Results and Discussion for his analyses, using only numbers from `results/` and the claims ledger | 14-15 Nov |
| KU8 | **Campus capture** with label `campus` and the same matrix; then merge and run N9 | **16 Nov**, data 17 Nov |

### Aman

| ID | Task | When |
|---|---|---|
| AM1 | Set up the laptop (Python venv, `q`, Wireshark/Npcap), run `scripts/preflight` with `--no-live`, and read `docs/LIVE_CHECKS.md` | 11 Nov, before capture |
| AM2 | **Live checks:** run the eight `q` queries in `docs/LIVE_CHECKS.md` (4 resolvers x HTTP/2 and HTTP/3, one at a time, with pauses), save the raw JSON under `docs/live_checks/`, and write the findings (answer and CNAME parity, extra record types, whether an EDNS0 padding option appears) into `docs/LIVE_CHECKS.md`. About 10 minutes. Do this **before** the Jio capture starts. | 11 Nov |
| AM3 | **Jio capture** with `scripts/run_network`, network label `jio`, the matrix in section 1 | **Start the night of 11 Nov** |
| AM4 | Merge Jio data, extract features for the Jio manifest only, then run N1, N2, N3, N8 on the shared domain set | 12 Nov |
| AM5 | **Campus capture on his own laptop too (machine control)** | 16 Nov |
| AM6 | Paper text: Introduction, Related Work, Threat Model, Method, Ethics, Limitations, Reproducibility; slide deck | 12-15 Nov |

### Shared

| ID | Task | When |
|---|---|---|
| S1 | Verification round 1: each teammate recomputes a random sample of the other's ledger values from the raw CSVs, everything except Campus | 15 Nov |
| S2 | Campus regeneration: re-run all network analyses with three networks, regenerate the claims ledger | 17 Nov morning |
| S3 | Verification round 2 for the Campus-dependent numbers, final freeze, proofread, submit | 17 Nov night |

---

## 5. KU1: rerun on the shared domain sets (step by step)

Run everything in the repository root with `.venv\Scripts\python.exe` and `PYTHONPATH=src`. This needs only `data/processed/dataset_v2.csv`, which is in the repository.

1. **Check the shared-set sizes first** (expect k10: global 99, india 79):

   `.venv\Scripts\python.exe -c "import pandas as pd; d=pd.read_csv('data/processed/dataset_v2.csv'); d=d[(d.repeat>=8)&(d.repeat<=19)]; c=d.groupby(['workload','domain','resolver','protocol']).size().unstack(['resolver','protocol']).fillna(0); print('k10', (c>=10).all(axis=1).groupby('workload').sum().to_dict()); print('k8', (c>=8).all(axis=1).groupby('workload').sum().to_dict())"`

2. **Change the analysis (`src/encdns/analysis` and the `analyze` command) so that**:
   - for each workload the shared domain set is computed as above, and **every** slice, baseline and comparison uses that same set;
   - exactly 10 repeats are sampled per domain with a fixed seed (apply the k=8 fallback to both workloads only if a workload has fewer than 60 shared domains);
   - the shared domain lists are written to `results/<run_id>/shared_domains_global.txt` and `shared_domains_india.txt`;
   - `run_metadata.json` reports the shared-set sizes and the chosen k under `domain_counts`.
3. **Add the missing outputs:**
   - RQ3: permutation importance and ANOVA F by feature group, plus grouped ablation, with repeated seeds and intervals;
   - pairwise bootstrap differences: DoH vs DoH/3 per resolver, and resolver vs resolver;
   - anonymity sets: domains grouped by name length, with the distribution of set sizes;
   - WP6: Global vs Indian comparison of name length, answer count and response size, before the fingerprinting comparison;
   - figures from the CSVs (`python -m encdns figures <run_id>`).
4. **Smoke test with 2 permutations**, then the full run. Use a **new run id** and do **not** use `--resume`, because the old checkpoints are for the wrong domain sets:

   `.venv\Scripts\python.exe -m encdns analyze --run-id airtel_final_shared_20261111 --permutations 200`

   It takes a few hours. Progress is in `results/<run_id>/progress.log`. If it stalls, rerun the same command with `--resume`.
5. `.venv\Scripts\python.exe -m encdns report airtel_final_shared_20261111` and `.venv\Scripts\python.exe -m encdns ledger airtel_final_shared_20261111`. Both take the run id as a plain argument. If `report` reports a missing package, install the packages in `requirements.txt`.
6. Add a short note in `results/airtel_final_20261111/` saying it is superseded by the shared-set run. Commit and push the new run.

Done when: every slice shows the same domain count within a workload (Global 99, India 79 unless the fallback applies), `run_metadata.json` is correct, and all outputs above exist.

---

## 6. Day-by-day

| Date | Kunal | Aman |
|---|---|---|
| **Wed 11 Nov** | **KU1 (start in the evening, overnight)**, KU3 | AM1, AM2, **start AM3 (Jio) by night** |
| **Thu 12 Nov** | KU2 review, KU4, KU5 when Jio is merged | AM4 (N1, N2, N3, N8) |
| **Fri 13 Nov** | KU5, KU6 | AM6 |
| **Sat 14 Nov** | KU6, KU7 | AM6 draft complete, slides |
| **Sun 15 Nov** | S1 verification, fix mismatches | S1 verification, fix mismatches |
| **Mon 16 Nov** | Reach campus; **KU8 Campus capture** | Reach campus; **AM5 Campus capture** |
| **Tue 17 Nov** | S2, S3 | S2, S3 |

**If behind, cut in this order:** WP12, WP8, WP13, WP9, the Aman-laptop campus control (AM5). **Never cut:** KU1, the integrity rules, the baselines, both verification rounds, the Limitations section.

If a Campus capture fails, the paper reports Airtel and Jio, states that Campus was attempted and why it is missing, and does not claim three-network results.

---

## 7. How to run things

All commands run from the repository root.

- Always use the project's virtual environment: `.venv\Scripts\python.exe` (system Python may lack packages). Set `PYTHONPATH=src` for the package commands.
- If PowerShell blocks a script: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\<script>.ps1 ...`
- Commands: `python -m encdns status`, `analyze`, `report <run_id>`, `ledger <run_id>`, `merge-runs`, `smoke-check`.
- Long jobs (capture, analysis) run in your own terminal. Check `results/<run_id>/progress.log` for analysis progress.
- **Do not re-extract Airtel features from the committed manifests.** `server_ips` is blank in them by design. Use `data/processed/dataset_v2.csv`. Extract Jio and Campus from their own raw manifests, then concatenate datasets.
- Do not commit pcaps. The Airtel raw data is shared as a zip with checksums.

---

## 8. Rules (apply to everyone)

- Never edit `data/workloads/` or existing manifest rows. Domain names inside data files are data, not text to be scrubbed.
- Never commit pcaps, IP addresses of any network, or credentials.
- No result number is typed by hand; numbers come from `results/` and the claims ledger.
- Headline analyses use repeats 8-19 (Airtel), the shared domain set, and exactly k repeats per domain. WP11 is the only analysis that may use repeats 0-7.
- Nothing else runs on a laptop while it captures.
- No tool or assistant names in the repository, commits or documents.
- Capture only our own traffic, rate-limited, on networks we have permission to use.

---

## 9. Definition of done

- Every research question has a table and a figure generated from `results/`, with intervals and a stated limitation, on the shared domain sets.
- Every number in the paper and slides is in the claims ledger, and both verification rounds show no mismatches.
- Network results cover Airtel, Jio and Campus, each labelled "network + machine" unless it is a within-machine comparison.
- CI is green, the repository contains no tool names, and the release tag is set.
- The paper states what was not measured: page loads, other clients, DoQ, ODoH, Quad9 on Jio and Campus, and any missing Campus result. It also notes that persistently failing domains were excluded, so the surviving domains skew toward faster-resolving ones.