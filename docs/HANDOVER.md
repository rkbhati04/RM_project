# Network plan and task split: see docs/TEAM_PLAN.md (supersedes this file)
# Project Handover: Encrypted DNS Privacy Analysis (DoH vs DoH/3)

Version: updated 2026-11-10 from the completed Airtel capture state.

---

## 1. What this project is

**Title:** Privacy Analysis of Modern Encrypted DNS: Is DNS-over-HTTP/3 Really More Private?

**Course link:** 2-credit Research Methodology subject (5th semester, IIIT Allahabad). The proposal defines five research questions. A faculty supervisor oversees the project.

**One-paragraph summary.** A passive observer on the path between a client and a public DNS resolver cannot read encrypted DNS, but still sees packet sizes, directions, and timing. We capture one DNS lookup per fresh connection (one pcap per lookup), extract metadata features, and measure how well a classifier can tell which domain was looked up. We compare DoH (HTTP/2) with DoH/3 (HTTP/3) across four public resolvers, on a Global and an Indian domain workload, over the Airtel network. We add baselines, such as domain-name length alone, so we can say how much of any "leakage" is trivial.

**Research questions (current scope):**

| RQ | Question |
|---|---|
| RQ1 | Can the queried domain be identified from encrypted DoH/3 metadata, and how much is explained by trivial signals like name length? |
| RQ2 | How does resistance compare across resolvers and between DoH and DoH/3? |
| RQ3 | Which feature groups carry signal and which are noise? |
| RQ4 | How does leakage vary across access networks, including cross-network generalization? |
| RQ5 | Does leakage differ between Global and Indian workloads? |

**Scope decisions already made (do not reopen without the supervisor):**

- DoQ is out of core scope (another group has it). It appears only as related work.
- ODoH is literature-only unless a working public relay is verified.
- NextDNS was dropped (decision by the project lead).
- Additional data should use an approved home network labelled `jio` or `campus`.
- Workloads are 100 Global + 100 Indian domains from Tranco list `L5PV4`. The first 25 of each list are the original pilot domains and must never change.
- The classifier label is **domain identity**. Protocol identification is only a sanity check, because TCP vs UDP makes it trivial.

---

## 2. Why the methodology looks the way it does (decisions and reasons)

| Decision | Reason |
|---|---|
| One lookup per fresh connection | Avoids flows mixing several queries |
| Features exclude ports, IPs, and domain names | No shortcut features; only sizes, directions, timing, bursts |
| Repeat is the outer loop, and new repeats use shuffled order | Spreads captures over time of day; order control |
| Headline analysis uses repeats 8-19 only | Repeats 0-7 were captured earlier in fixed order and are pilot data |
| Target k=10 successful repeats per domain, same domain set in all slices | Prevents one flaky domain from shrinking everything, and keeps slices comparable |
| 200 permutations, RF null, one seed reused | A significance rule that is the same everywhere |
| Length-only baseline | Single-lookup traces mostly leak domain-name length and response size |
| No "resistance score" | It was only a rescaling of accuracy and misleading |
| Never call a non-significant result "private" | Say "no detectable leakage at this sample size" |
| Call the Global list "domains", not "websites" | It is dominated by CDN and infrastructure names |
| Timing treated as likely noise | Prior work (Siby et al.) found timing unreliable, and our ablation agrees |
| TTL is not a protocol feature | TTL differences reflect resolver cache state |

---

## 3. Current status snapshot **[FILL on 15 Nov]**

| Item | Status |
|---|---|
| Airtel T0 capture (4 resolvers x DoH/DoH3 x 200 domains x repeats 8-19) | Complete: 19,200/19,200 rows |
| Top-up pass(es) for failed or slow captures | Imported T0 run includes 1,062 retry rows across 19,200 unique capture keys; 789 retries recovered to `ok`, with 273 still non-`ok` |
| Consolidated manifest and `dataset_v2.csv` | Consolidated manifest: 22,400 rows; dataset: 20,934 rows; 10 dropped for too few packets |
| Final domain set after the k policy | Global 84 and India 40 at k=10; k=8 would keep Global 98 and India 64; India is below 60% at k=10 |
| WP1 integrity reset | Complete in code; final verification pending |
| WP2 capture upgrades | Done |
| WP3 DoH vs DoH/3 head-to-head | Airtel outputs generated in `results/airtel_topup_20261113/` |
| WP4 baselines and anonymity sets | Airtel headline fingerprinting and baseline outputs generated |
| WP5 resolver and network comparison | Airtel resolver outputs generated; additional networks not collected |
| WP6 Global vs Indian | Airtel Global/India outputs generated |
| Raw data backup location and checksums | `data/snapshots/overnight_20261110_2209_20261109_230331_22448/SHA256SUMS.csv` (0.202 GiB, 19,201 source files) |
| Live check results (answer counts, EDNS0 padding) | Blocked: q unavailable; see `docs/LIVE_CHECKS.md` |

Observed during capture (snapshot at 14,119 of 19,200 jobs): success rates ranged from about 88% (Quad9 DoH/3, worst at night) to 99.9% (Google). AdGuard was about 91%. Answer and CNAME counts matched between DoH and DoH/3 in about 94-99% of pairs. TTL differences were common and are cache effects.

---

## 4. Repository map

| Path | Purpose |
|---|---|
| `config/project.yaml` | Single source of truth for seeds, counts, resolvers, protocols, repeats, permutation count, paths |
| `data/workloads/` | Frozen domain lists + `metadata.json` (Tranco ID, SHA-256). **Never edit.** |
| `data/raw/manifest_pilot_v1.csv` | Archived pilot manifest |
| `data/raw/overnight_runs/<run>/` | Live capture folders (manifest + pcaps); not committed |
| `data/processed/dataset_v2.csv` | Final feature table; `dataset_pilot_v1.csv` is the old one |
| `src/probe_and_capture.py` | Capture driver (needs `q`, `dumpcap`, `tshark`) |
| `src/extract_features.py` | pcaps to feature rows, with timeouts, caching, drop reasons |
| `src/encdns/` | Package and CLI: `status`, `analyze`, `report`, `ledger`, `merge-runs`, `smoke-check` |
| `scripts/` | `run_overnight`, `run_network`, `run_drift_T1`, `preflight` |
| `docs/` | `METHODOLOGY`, `RUNBOOK_CAPTURE`, `TEAMMATE_QUICKSTART`, `POST_CAPTURE_CHECKLIST`, `ETHICS`, `LIVE_CHECKS`, `OPEN_ITEMS`, claims ledger |
| `results/<run_id>/` | Generated outputs only, each with run metadata |

---

## 5. How to run things

All commands run from the repository root with the virtual environment active.

1. **Health check:** `python -m encdns status`
2. **Preflight on a capture machine:** `scripts/preflight` (use `--no-live` if a capture is running)
3. **Capture on a new network:** `scripts/run_network` with the network label as a parameter. About 13 hours including margin.
4. **Drift batch T1:** `scripts/run_drift_T1`. Same laptop and network as T0, planned for 2026-11-15.
5. **Analysis:** `python -m encdns analyze`, then `report`, then `ledger`.

**Hard rules while any capture runs:** no other live DNS queries, no writes under `data/raw/`, no edits to files the capture imports, no heavy CPU jobs on that machine, no VPN, no network switching, no sleep. Work from copied snapshots.

---

## 6. Remaining work

Owners are placeholders. Create one GitHub issue per work package.

### A. Data work

| ID | Task | Acceptance |
|---|---|---|
| D1 | **Network 2 home capture.** Obtain permission, then run `scripts/run_network` with an approved home-network label and the documented matrix | Manifest merged, success rates reported, network label set |
| D2 | **T1 drift batch** on 2026-11-15 (adguard, quad9 x 2 protocols x 200 x 3 repeats) | Rows in manifest with batch T1 |
| D3 | Optional: third network if any teammate has one | Same as D1 |

### B. Analysis work

| ID | Task | Acceptance |
|---|---|---|
| WP7 | Richer features: packet-size n-grams, burst n-grams, post-handshake-only features | Comparison table vs current features |
| WP8 | 1D-CNN and GRU on signed packet-size sequences, same evaluation protocol | Honest comparison with tree models |
| WP9 | Open-world: monitored vs unmonitored domains, precision-recall curves | Curves with intervals |
| WP10 | Scaling curves: accuracy vs number of domains and vs repeats | Figure with intervals |
| WP11 | Time stability: train T0, test T1 | Table with intervals |
| WP5b | Cross-network train/test once D1 data exists | Matrix + heatmap |
| WP13 | Defense what-ifs: simulate 128/468-byte padding and random delay on extracted traces | Labelled as simulation |
| WP12 | Optional: browser-driven page-load traces through a local DoH/3 stub | Documented setup, small dataset |

### C. Writing and delivery

| ID | Task | Acceptance |
|---|---|---|
| W1 | Paper: Introduction, Related Work (use the gap table in `docs/paper/`), Threat Model, Method, Results RQ1-RQ5, Discussion, Limitations, Ethics, Reproducibility | Every number appears in the claims ledger |
| W2 | Slide deck | Figures generated from `results/` only |
| W3 | README cleanup and final repository tag | CI green, no tool names anywhere |
| W4 | Independent verification: recompute a sample of ledger values from raw CSVs | Zero mismatches |

---

## 7. Suggested schedule after handover **[adjust to deadlines]**

| Day | Work |
|---|---|
| H+0 | Walkthrough meeting; teammates run `status` and read this file; claim issues |
| H+1 | D1 (Network 2 capture starts overnight); WP7, WP10 |
| H+2 | WP8, WP9; paper Introduction, Related Work, Method |
| H+3 | D1 results in; WP5b; WP11 (after T1) |
| H+4 | WP13; paper Results |
| H+5 | Discussion, Limitations; slides |
| H+6 | W4 verification; fix mismatches |
| H+7 | Freeze, proofread, submit |

Cut list if time runs out (cut in this order): WP12, D3, WP8, WP13, WP9. **Never cut:** the integrity rules, the baselines, W4 verification.

---

## 8. Rules that protect the project

- Never edit `data/workloads/` or existing manifest rows.
- Never commit pcaps, raw IP addresses of any teammate's network, or credentials. Public IPs are stored only as salted hashes.
- No result number may be typed into code or text by hand. Numbers come from `results/` and the claims ledger.
- All headline results use repeats 8-19, target k=10, the agreed domain set, 200 permutations.
- Do not mention tools, assistants, or automation in the repository, commits, or documents.
- Capture only our own traffic, rate-limited, and only on networks we have permission to use. See `docs/ETHICS.md`.

---

## 9. Known limitations to state in the paper

- One client implementation (`q`), not a browser. Prior work shows classifiers do not transfer across clients.
- Single-lookup traces rather than page loads. All four reference papers fingerprint page loads, so our results are per-lookup leakage.
- A small closed set of domains, dominated by infrastructure names in the Global list.
- Airtel is the main network. Cross-network claims need the second network.
- Success rates differ by resolver and hour (Quad9 DoH/3 lowest, worst at night). Dropped slow captures can bias toward cached lookups.
- EDNS0 padding behaviour is established only by the live checks, not by packet-size inference.

---

## 10. Related work (for the paper)

| Paper | Protocol | Setup | Key result |
|---|---|---|---|
| Houser et al., CoNEXT 2019 | DoT | Firefox + Stubby on EC2; Google, Cloudflare, Surfnet; 98 sensitive sites | Unpadded single-site FNR under 17%; padding helps but does not stop it |
| Siby et al., NDSS 2020 | DoH | Cloudflare and Google; 3 locations; 1,500 sites | F1 about 0.9; accuracy drops across locations, resolvers, platforms, and clients; padding insufficient |
| Hu and Fukuda, ICAIIC 2024 | DoQ | Tokyo; NextDNS and local Bind; binary sensitive vs non-sensitive | F1 about 0.9; delay and padding reduce it; combined about 25% |
| Salari et al., DSN 2025 | ODoH | GENI, 10 US clients, 100 sites, 60k traces | 94% accuracy; resolver irrelevant; location matters |

**Gap:** no prior work measures DoH/3 leakage per resolver, on Indian access networks and Indian domains, with a controlled DoH vs DoH/3 comparison.

---

## 11. Contacts and logistics

- Supervisor: unknown
- Project lead (handing over): unknown
- Teammates and owners: unknown
- Shared data location (checksummed backup of the T0 run): `data/snapshots/overnight_20261110_2209_20261109_230331_22448`
- GitHub repository and branch policy: `rkbhati04/RM_project`; do not push from this handover

## 12. Open items **[FILL from docs/OPEN_ITEMS.md]**

- Approval and an operator for Network 2.
- Teammate with access to a second network.
- Results of the live checks: answer-count parity and EDNS0 padding.
- Final domain set after the k policy.
