# Encrypted DNS Privacy: DoH vs. DoH/3
### An Empirical Study on Indian Access Networks (Airtel Broadband & Reliance Jio Cellular)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Paper Draft](https://img.shields.io/badge/Paper-Draft%20Available-green.svg)](docs/PAPER_DRAFT.md)
[![Presentation](https://img.shields.io/badge/Slides-presentation.md-blueviolet.svg)](presentation.md)

---

## 1. Conceptual Overview

### Background
When a user accesses a website (such as `wikipedia.org` or `bank.com`), the client device first queries a recursive resolver to translate the human-readable domain name into a routable numerical IP address. This lookup mechanism is governed by the **Domain Name System (DNS)**.

Historically, standard DNS queries (RFC 1035) were transmitted unencrypted over UDP port 53. Under this model, any intermediate observer on the network path—including Internet Service Providers (ISPs), local network administrators, and surveillance entities—could inspect query names in cleartext.

```
Traditional DNS (Unencrypted):
Client ----------------- "query: bank.com" ------------------> Recursive Resolver
         (Intermediate network observers can read queries in cleartext)
```

To prevent eavesdropping and query tampering, encrypted DNS protocols were standardized:
1. **DNS-over-HTTPS (DoH, RFC 8484):** Encapsulates DNS queries within TLS-secured HTTP/2 tunnels over TCP port 443.
2. **DNS-over-HTTP/3 (DoH/3, RFC 9114):** Encapsulates DNS queries within QUIC-secured HTTP/3 tunnels over UDP port 443.

```
Encrypted DNS (DoH / DoH/3):
Client ==== [ Encrypted Transport Tunnel: Ciphertext Payload ] ====> Recursive Resolver
         (Query payloads are cryptographically protected against inspection)
```

---

### The Security Challenge: Side-Channel Traffic Analysis
While payload encryption conceals raw query strings, transport-layer communication metadata remains visible on the wire.

An on-path adversary observing the encrypted channel can record side-channel transmission artifacts:
- Aggregate byte volumes and directional packet counts
- Packet size distributions and early handshake sequences
- Inter-arrival times (IAT) and flow duration

By applying supervised machine learning classifiers to these traffic signatures, an adversary can attempt to infer the queried domain name without breaking the underlying cryptographic primitives. This vulnerability is formally defined as **Website / Domain Traffic Fingerprinting**.

---

### Primary Empirical Findings

This study evaluates encrypted DNS traffic across **26,838 live queries** collected over two production Indian telecommunications networks: **Airtel Fiber FTTH (Wi-Fi 6)** and **Reliance Jio Cellular (4G/5G)**.

1. **Protocol Resistance Divergence:**
   - On Cloudflare, Quad9, and AdGuard, HTTP/3 (DoH/3) significantly suppresses metadata leakage compared to HTTP/2 (DoH), reducing top-1 classifier accuracy by **62% to 86%**.
   - This reduction is driven by QUIC transport constraints, notably the mandatory Initial packet padding to $\ge 1200$ bytes and uniform frame multiplexing, which obscure small domain-length differentials.

2. **Resolver Implementation Dependency (The Google Anomaly):**
   - On Google's public resolver, DoH/3 fails to improve privacy resistance (classifier accuracy remains at 16.9% on DoH/3 versus 17.5% on DoH).
   - Packet inspections reveal that Google's implementation transmits unpadded response payloads that scale directly with answer record counts, preserving distinguishable packet-size signatures.

3. **Cross-Network Transfer Failure:**
   - Classifiers trained on broadband optical fiber (Airtel) fail completely when evaluated against cellular traces (Jio), with accuracy falling to **1.6%–2.4%** (statistically equivalent to the 2.0% random baseline).
   - Two-sample Kolmogorov-Smirnov tests confirm substantial distribution shifts ($p < 10^{-6}$) caused by cellular radio scheduling delays, jitter, and MTU variations.

4. **Middlebox Deployment Impediments:**
   - On Reliance Jio cellular networks, 100% of outbound DoH/3 queries ($3,000 / 3,000$) failed due to packet drops.
   - Core cellular middleboxes actively filter outbound UDP traffic on port 443, silently forcing client applications to fall back to older, higher-leakage transport protocols.

---

## 2. Quantitative Results Summary

The table below presents closed-world domain identification performance across 100 target domains (50 Global Tranco, 50 Indian regional services). Chance baseline accuracy for a 100-class random guess is 1.0%.

| Upstream Resolver | Transport Protocol | Top-1 Accuracy | 95% Wilson Confidence Interval | Leakage Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **Cloudflare** | DoH (HTTP/2) | **23.6%** | [21.5%, 25.8%] | Moderate Leakage |
| **Cloudflare** | **DoH/3 (HTTP/3)** | **6.0%** | [4.7%, 7.6%] | **Low Leakage (75% Reduction)** |
| **Quad9** | DoH (HTTP/2) | **34.2%** | [31.8%, 36.6%] | High Leakage |
| **Quad9** | **DoH/3 (HTTP/3)** | **4.6%** | [3.5%, 6.0%] | **Low Leakage (86% Reduction)** |
| **AdGuard** | DoH (HTTP/2) | **26.2%** | [24.1%, 28.5%] | Moderate Leakage |
| **AdGuard** | **DoH/3 (HTTP/3)** | **8.9%** | [7.4%, 10.7%] | **Moderate-Low Leakage (66% Reduction)** |
| **Google** | DoH (HTTP/2) | **17.5%** | [15.6%, 19.5%] | Moderate Leakage |
| **Google** | **DoH/3 (HTTP/3)** | **16.9%** | [15.1%, 18.9%] | **Persistent Leakage (Unpadded Responses)** |

*All evaluations utilize leave-repeat-out temporal cross-validation with 200 label-permutation baseline tests ($p < 0.005$).*

---

## 3. Experimental Architecture & Methodology

```
+-----------------------------------------------------------------------------------------+
|                                EXPERIMENTAL TESTBED ARCHITECTURE                         |
+-----------------------------------------------------------------------------------------+
                                 
     [ Workload Generator ]           [ Network Layer Capture ]          [ Upstream Resolvers ]
     100 Pinned Domains:               dumpcap / tshark                   - Cloudflare (1.1.1.1)
     - 50 Global (Tranco L5PV4)        Per-query PCAP generation          - Google (8.8.8.8)
     - 50 Indian (.in / regional)      Synchronous packet flush           - AdGuard
                                                                          - Quad9 (9.9.9.9)
                |                                      |                              |
                v                                      v                              v
      [ q DNS Client 0.19.12 ]  ===>  [ Physical Access Network ]  ===>  [ Encrypted DNS Resolver ]
      - HTTP/2 (DoH)                  - Airtel FTTH (Wi-Fi 6)            - TCP port 443
      - HTTP/3 (DoH/3)                - Jio Cellular (USB Tether)        - UDP port 443
```

### Methodological Controls
- **Zero Label Leakage:** IP addresses, port numbers, SNI strings, and protocol headers are excluded from feature vectors. Models learn exclusively from physical traffic dynamics.
- **Temporal Integrity:** Training and evaluation partitions are divided strictly across query repeats to prevent autocorrelation across burst intervals.
- **Statistical Baselines:** Empirical significance is established against 200 permutation shuffles, confirming that measured predictive power exceeds random chance.
- **Model Suite:** Evaluates Random Forest, XGBoost, 1D-CNN (packet sequence), GRU (recurrent sequence), open-world evaluation, domain scaling curves, and simulated defense perturbations.

---

## 4. Repository Structure

```
├── presentation.md            <- 12-slide Marp-compatible conference presentation and scripts
├── README.md                  <- Project documentation, methodology, and execution instructions
├── requirements.txt           <- Python environment dependencies
├── to-do.md                   <- Comprehensive project verification checklist
├── docs/
│   ├── PAPER_DRAFT.md         <- Full academic research paper draft (9 sections, 9 tables)
│   ├── PRESENTATION_SLIDES.md <- Slide deck content, layouts, and speaker documentation
│   ├── claims_ledger.csv      <- Cryptographic verification ledger mapping all 24 claims
│   └── CAPTURE_COMMANDS.md    <- Measurement runbook and execution parameters
├── results/
│   ├── figures/               <- Publication figures (Vector PNGs for paper and slides)
│   ├── airtel_all_20261113/   <- WP7-WP11 & WP13 analysis tables and scaling curves
│   └── jio_analysis_20261113/ <- N1-N8 cross-network transfer and distribution shift tables
├── scripts/
│   ├── plot_slide_figures.py  <- Generates the 4 publication slide figures
│   ├── run_airtel_all.py      <- Execution runner for Airtel analyses (WP7-WP11, WP13)
│   ├── run_jio_analysis.py    <- Execution runner for Jio and cross-network analyses (N1-N8)
│   └── run_jio_capture.sh     <- Automated 6,000-query Jio cellular testbed harness
└── src/
    ├── probe_and_capture.py   <- Synchronous probe and dumpcap capture orchestrator
    ├── extract_features.py    <- 39-feature network flow extraction module
    └── encdns/                <- Analysis package (fingerprinting, baselines, ledger)
```

---

## 5. Setup & Reproduction Instructions

### 5.1 Environment Configuration

```bash
# Clone the repository and switch to branch aman
git checkout aman

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements.txt
```

### 5.2 Required System Utilities
- **Packet Capture CLI:** `dumpcap` and `tshark` (Wireshark suite)
  - macOS: `brew install wireshark`
  - Linux: `sudo apt install tshark`
- **DNS Client:** `q` DNS client (version 0.19.12+) available from [natesales/q](https://github.com/natesales/q/releases).

---

### 5.3 Automated Analysis Execution

Preprocessed, zero-leakage feature tables are maintained in `data/processed/`. The entire analytical pipeline can be executed deterministically in under 6 minutes:

```bash
# Step 1: Run Airtel analysis modules (WP7 to WP11, and WP13)
python3 scripts/run_airtel_all.py

# Step 2: Run Jio and Cross-Network analysis modules (N1 to N8)
python3 scripts/run_jio_analysis.py

# Step 3: Generate publication-ready figures
python3 scripts/plot_slide_figures.py
```

All analytical outputs, summary tables, and visualizations will be written to `results/airtel_all_20261113/`, `results/jio_analysis_20261113/`, and `results/figures/`.

---

### 5.4 Test Suite Verification

```bash
# Run automated regression test suite (10/10 tests pass)
python3 -m unittest discover tests
```

---

## 6. Project Deliverables

- **Academic Paper Draft:** [docs/PAPER_DRAFT.md](docs/PAPER_DRAFT.md) — Comprehensive academic research paper complete with Related Work, Threat Model, Methodology, Empirical Evaluation, Limitations, and Ethics.
- **Conference Presentation Deck:** [presentation.md](presentation.md) — 12-slide Marp-compatible presentation deck containing layout specifications, embedded figures, and word-for-word speaker notes.
- **Empirical Claims Ledger:** [docs/claims_ledger.csv](docs/claims_ledger.csv) — Auditable ledger mapping every statistical claim directly to pipeline execution outputs.
- **Publication Figures:**
  - [Figure 1: DoH vs. DoH/3 Leakage Comparison](results/figures/fig1_headline_doh_vs_doh3.png)
  - [Figure 2: Cross-Network Transfer Collapse](results/figures/fig2_cross_network_transfer.png)
  - [Figure 3: Carrier-Level QUIC Blocking on Jio Cellular](results/figures/fig3_carrier_quic_blocking.png)
  - [Figure 4: Feature Distribution Shifts Across Network Tiers](results/figures/fig4_feature_distribution_shift.png)

---

## 7. Ethics & Research Integrity

- **Passive Observational Framework:** All traffic captures were conducted passively against client-initiated queries. No payload modification, injection, or decryption was performed.
- **Data Privacy:** Raw PCAP files, proprietary network identifiers, credentials, and local IP addresses are excluded from version control per `.gitignore`.
- **Reproducibility:** Seed configurations (`17`, `42`, `101`) and data pipelines are fully deterministic and automated.

---

## 8. Authors & Institutional Affiliation

- **Aman Kashyap** (`iit2024140@iiita.ac.in`)  
  Department of Information Technology, Indian Institute of Information Technology, Allahabad.  
- Coursework in Research Methodology, November 2026.
