# Team Plan: Remaining Work (2026-11-11 to 2026-11-17)

This file supersedes every earlier network plan in `HANDOVER.md`, the runbook, the quickstart and `docs/issues/`. Two teammates carry the project from here: **Aman** and **Kunal**. The project lead's part ends once the Airtel results and this repository are pushed. Work continues until the night of **2026-11-17**.

---

## 1. Networks, machines and dates

| Network | Label | Who captures | Machine | When |
|---|---|---|---|---|
| Airtel | `airtel` | Project lead (done) | Project lead's laptop | Complete |
| Jio | `jio` | **Aman** | Aman's laptop | **Night of 11 Nov**, data ready 12 Nov morning |
| College WiFi | `campus` | **Kunal** | Kunal's laptop | **16 Nov**, after reaching college; data ready 17 Nov morning |

**Machine confound (important).** Each network comes from a different laptop. Prior work (Siby et al.) found that classifiers do not transfer across platforms, so **every cross-network result is "network + machine"**. Label it that way in tables and text. A cheap control, strongly recommended: on **16 Nov Aman also runs the campus matrix on his laptop** at the same time as Kunal. Campus on two laptops measures the machine effect directly, and Aman's Jio vs Campus then becomes a clean within-machine comparison. If only one laptop can capture on campus, Kunal's run is the primary one and the paper states the confound.

**Capture matrix for Jio and Campus (identical):** cloudflare, google, adguard x DoH, DoH/3 x the first 100 domains (first 50 Global + first 50 India) x 10 repeats, shuffled order. That is 6,000 captures, about 6 hours plus 20% margin (about 7.5 hours). Quad9 is left out because its DoH/3 success rate on Airtel was lowest (about 85%). Quad9 therefore has Airtel data only, and the paper says so.

During any capture, nothing else runs on that laptop: no VPN, no network switching, no sleep, no heavy jobs. Do analysis on another machine.

---

## 2. Status at handover (Airtel, repeats 8-19, plus pilot repeats 0-7)

- Capture finished: 19,200 jobs. Successful per slice (of 2,400): adguard 2166 DoH / 2177 DoH/3, cloudflare 2304 / 2366, google 2394 / 2394, quad9 2296 / 2041.
- Raw data backup with checksums exists (about 0.2 GB, 19,201 files). It is shared separately from git.
- Consolidated manifest: 23,043 source rows became 22,400 unique rows (643 pilot re-capture duplicates). `dataset_v2.csv` has about 20,934 feature rows.
- Domain-set policy before the top-up pass: k=10 keeps 84 Global and 40 India domains; k=8 keeps 98 and 64. The policy is recomputed after the top-up (see the note below).
- Not yet done: the eight live `q` checks (see Aman's first task), final WP3-WP6 outputs if they are not yet pushed.

**Top-up note.** A top-up pass re-captures the failed and slow Airtel jobs. After it, the domain sets, `dataset_v2.csv` and results change. The numbers in `docs/` always follow the latest run under `results/`.

**Policy rule (applies to both workloads):** use k=10 repeats per domain if at least 60 domains survive in each workload; otherwise use k=8 for **both** workloads. Use the same k for Global and India, because RQ5 compares them. Sample exactly k repeats per domain with a fixed seed.

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

### Aman

| ID | Task | When |
|---|---|---|
| AM1 | Set up the laptop (Python venv, `q`, Wireshark/Npcap), run `scripts/preflight` with `--no-live`, and read `docs/LIVE_CHECKS.md` | 11 Nov, before capture |
| AM2 | **Live checks:** run the eight `q` queries in `docs/LIVE_CHECKS.md` (4 resolvers x HTTP/2 and HTTP/3, one at a time, with pauses), save the raw JSON under `docs/live_checks/`, and write the findings (answer and CNAME parity, extra record types, whether an EDNS0 padding option appears) into `docs/LIVE_CHECKS.md`. Takes about 10 minutes. Do this **before** the Jio capture starts. | 11 Nov |
| AM3 | **Jio capture** with `scripts/run_network`, network label `jio`, the matrix in section 1 | **Start the night of 11 Nov** |
| AM4 | Merge Jio data, extract features for the Jio manifest only, then run N1, N2, N3, N8 | 12 Nov |
| AM5 | **Campus capture on his own laptop too (machine control)** | 16 Nov |
| AM6 | Paper text: Introduction, Related Work, Threat Model, Method, Ethics, Limitations, Reproducibility; slide deck | 12-15 Nov |

### Kunal

| ID | Task | When |
|---|---|---|
| KU1 | Review the Airtel WP3-WP6 results against `METHODOLOGY.md`; flag anything odd | As soon as results are pushed |
| KU2 | WP7 richer features (start on `dataset_pilot_v1.csv`, rerun on `dataset_v2.csv`) | 11-12 Nov |
| KU3 | WP10 scaling curves, WP11 pilot-vs-T0 stability | 12-13 Nov |
| KU4 | N4, N5, N6, N7 as soon as Jio data is merged | 12-14 Nov |
| KU5 | WP8 CNN and GRU, WP9 open-world, WP13 defense simulations | 13-15 Nov |
| KU6 | Paper text: Results and Discussion for his analyses, using only numbers from `results/` and the claims ledger | 14-15 Nov |
| KU7 | **Campus capture** with label `campus` and the same matrix; then merge and run N9 | **16 Nov**, data 17 Nov |

### Shared

| ID | Task | When |
|---|---|---|
| S1 | Verification round 1: each teammate recomputes a random sample of the other's ledger values from the raw CSVs, everything except Campus | 15 Nov |
| S2 | Campus regeneration: re-run all network analyses with three networks, regenerate the claims ledger | 17 Nov morning |
| S3 | Verification round 2 for the Campus-dependent numbers, final freeze, proofread, submit | 17 Nov night |

---

## 5. Day-by-day

| Date | Aman | Kunal |
|---|---|---|
| **Wed 11 Nov** | AM1, AM2, **start AM3 (Jio) by night** | KU1 when results land; KU2 |
| **Thu 12 Nov** | AM4 (N1, N2, N3, N8) | KU3, KU4 (when Jio is merged) |
| **Fri 13 Nov** | AM6 | KU4, KU5 |
| **Sat 14 Nov** | AM6 draft complete, slides | KU5, KU6 |
| **Sun 15 Nov** | S1 verification, fix mismatches | S1 verification, fix mismatches |
| **Mon 16 Nov** | Reach campus; **AM5 Campus capture** | Reach campus; **KU7 Campus capture** |
| **Tue 17 Nov** | S2, S3 | S2, S3 |

**If behind, cut in this order:** WP12, WP8, WP13, WP9, the Aman-laptop campus control (AM5). **Never cut:** the integrity rules, the baselines, both verification rounds, the Limitations section.

If a Campus capture fails, the paper reports Airtel and Jio, states that Campus was attempted and why it is missing, and does not claim three-network results.

---

## 6. How to run things

All commands run from the repository root.

- Always use the project's virtual environment: `.venv\Scripts\python.exe` (system Python may lack pandas). Set `PYTHONPATH=src` for the package commands.
- If PowerShell blocks a script: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\<script>.ps1 ...`
- Commands: `python -m encdns status`, `analyze`, `report`, `ledger`, `merge-runs`, `smoke-check`.
- Long jobs (capture, analysis) run in your own terminal. Check `results/<run_id>/progress.log` for analysis progress.
- **Do not re-extract Airtel features from the committed manifests.** `server_ips` is blank in them by design. Use `data/processed/dataset_v2.csv`. Extract Jio and Campus from their own raw manifests, then concatenate datasets.
- The Airtel raw data (pcaps and manifest) is shared outside git in a zip with checksums. Do not commit pcaps.

---

## 7. Rules (apply to everyone)

- Never edit `data/workloads/` or existing manifest rows.
- Never commit pcaps, IP addresses of any network, or credentials.
- No result number is typed by hand; numbers come from `results/` and the claims ledger.
- Headline analyses use repeats 8-19 (Airtel) and the agreed k and domain set. WP11 is the only analysis that may use repeats 0-7.
- Nothing else runs on a laptop while it captures.
- No tool or assistant names in the repository, commits or documents.
- Capture only our own traffic, rate-limited, on networks we have permission to use.

---

## 8. Definition of done

- Every research question has a table and a figure generated from `results/`, with intervals and a stated limitation.
- Every number in the paper and slides is in the claims ledger, and both verification rounds show no mismatches.
- Network results cover Airtel, Jio and Campus, each labelled "network + machine" unless it is a within-machine comparison.
- CI is green, the repository contains no tool names, and the release tag is set.
- The paper states what was not measured: page loads, other clients, DoQ, ODoH, Quad9 on Jio and Campus, and any missing Campus result.