# Encrypted DNS Privacy: DoH vs. DoH/3
### An Empirical Study on Indian Access Networks (Airtel Broadband & Reliance Jio Cellular)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Paper Draft](https://img.shields.io/badge/Paper-Draft%20Available-green.svg)](docs/PAPER_DRAFT.md)
[![Presentation](https://img.shields.io/badge/Slides-presentation.md-blueviolet.svg)](presentation.md)

---

## 🌟 The Big Picture (In Plain English)

### What is this project about?
Whenever you type a website name like `wikipedia.org` or `bank.com` into your browser, your computer first asks a server: *"What is the numerical IP address for this website?"* This lookup process is called the **Domain Name System (DNS)**—often called the **"phonebook of the internet."**

Traditionally, these questions were sent in **plain text**. Anyone watching your network connection—your Internet Service Provider (ISP), a coffee shop Wi-Fi snooper, or a government agency—could read exactly which website you were visiting.

```
TRADITIONAL DNS (Unencrypted):
You  ----------------- "Take me to bank.com" ------------------> DNS Server
           (Anyone in the middle can read this in clear text)
```

To solve this, the networking industry created **Encrypted DNS**:
1. **DoH (DNS-over-HTTPS):** Introduced around 2018. It locks your query inside an encrypted tunnel (using HTTP/2 over TCP).
2. **DoH/3 (DNS-over-HTTP/3):** The modern upgrade introduced in 2022. It locks your query inside a cutting-edge protocol called **QUIC** (over UDP).

```
ENCRYPTED DNS (DoH / DoH/3):
You  ==== [ Locked Encrypted Envelope: ???????? ] ====> DNS Server
           (The contents inside the envelope are secret)
```

---

### The Problem: Can an eavesdropper still guess what you are doing?
Imagine sending a letter in a locked box. An observer cannot open the box to read your letter, but they **can still weigh the box, measure its exact dimensions, and see how long it takes to arrive**. 

In network security, this is called a **Side-Channel Metadata Attack (or Traffic Fingerprinting)**:
- Different websites produce slightly different response sizes and packet patterns.
- An eavesdropper watching the encrypted connection can observe:
  - How many packets were sent and received
  - How big each packet was
  - The exact timing and pauses between packets
- By feeding these patterns into Machine Learning algorithms, an attacker can frequently **guess which website you are visiting—without ever decrypting the traffic!**

---

### What Did We Discover? (The Key Takeaways)

We conducted a live, empirical study collecting over **26,800 real network queries** across two major real-world Indian networks: **Airtel Home Broadband (Wi-Fi 6)** and **Reliance Jio Mobile (4G/5G)**.

Here is what we discovered:

1. **The New Protocol (DoH/3) Significantly Improves Privacy on Most Resolvers:**
   - On providers like **Cloudflare, AdGuard, and Quad9**, the new HTTP/3 protocol reduces an attacker's ability to identify your website by **62% to 86%**.
   - *Why?* HTTP/3 enforces minimum packet padding (at least 1,200 bytes) and adds uniform control frames that act like bubble wrap, masking the unique size differences of small websites.

2. **The "Google Anomaly": Implementation Matters More Than the Protocol:**
   - On **Google's DNS server**, the new protocol did **not** improve privacy (the attacker guessed the website with ~17% accuracy on both the old and new protocols).
   - Google's server sends unpadded responses whose sizes vary directly with the number of answer records, preserving a clear "fingerprint."

3. **Broadband Attacks Fail Completely on Mobile Networks:**
   - If an attacker trains an AI snooping tool on home Wi-Fi (Airtel) and tries to use it against a mobile user (Jio), **the attack collapses completely** (accuracy drops to 1.6%–2.4%, which is no better than random guessing).
   - Cell towers constantly shuffle and delay radio packets, naturally scrambling the timing fingerprints that attackers rely on.

4. **Mobile Carriers Actively Block the Modern Privacy Protocol:**
   - On **Reliance Jio cellular**, **100% of our DoH/3 queries failed**.
   - Jio's network middleboxes actively block or drop outbound UDP traffic on port 443. When this happens, your phone silently falls back to older, less private protocols.

---

## 📊 Summary of Core Results

| Public DNS Provider | Protocol | Website Fingerprint Accuracy (Top-1) | Privacy Protection Level |
| :--- | :--- | :--- | :--- |
| **Cloudflare** | Old DoH (HTTP/2) | **23.6%** | ⚠️ Moderate Leakage |
| **Cloudflare** | **New DoH/3 (HTTP/3)** | **6.0%** | 🛡️ **Strong Privacy (75% leakage reduction)** |
| **Quad9** | Old DoH (HTTP/2) | **34.2%** | ⚠️ High Leakage |
| **Quad9** | **New DoH/3 (HTTP/3)** | **4.6%** | 🛡️ **Strongest Privacy (86% leakage reduction)** |
| **AdGuard** | Old DoH (HTTP/2) | **26.2%** | ⚠️ Moderate Leakage |
| **AdGuard** | **New DoH/3 (HTTP/3)** | **8.9%** | 🛡️ **Good Privacy (66% leakage reduction)** |
| **Google** | Old DoH (HTTP/2) | **17.5%** | ⚠️ Moderate Leakage |
| **Google** | **New DoH/3 (HTTP/3)** | **16.9%** | ⚠️ **Persistent Leakage (Unpadded responses)** |

*(Note: Random guessing among 100 websites equals 1.0% accuracy. Lower percentage means higher privacy).*

---

## 🛠️ Research Methodology & Technical Architecture

```
+-----------------------------------------------------------------------------------------+
|                                EXPERIMENTAL TESTBED ARCHITECTURE                         |
+-----------------------------------------------------------------------------------------+
                                 
     [ Workload Generator ]           [ Network Layer Capture ]          [ Upstream Resolvers ]
     100 Popular Domains:              dumpcap & tshark                   - Cloudflare (1.1.1.1)
     - 50 Top Global (Tranco)          Raw PCAP per query                 - Google (8.8.8.8)
     - 50 Top India (.in / regional)   Synchronous packet flush           - AdGuard
                                                                          - Quad9 (9.9.9.9)
                |                                      |                              |
                v                                      v                              v
      [ q DNS Client 0.19.12 ]  ===>  [ Physical Access Network ]  ===>  [ Encrypted DNS Resolver ]
      - HTTP/2 (DoH)                  - Airtel FTTH (Wi-Fi 6)            - TCP port 443
      - HTTP/3 (DoH/3)                - Jio Cellular (USB Tether)        - UDP port 443
```

### Key Technical Controls
- **Zero Label Leakage:** IP addresses, port numbers, SNI strings, and domain names are strictly excluded from feature extraction. Only traffic shape metadata is used.
- **Strict Temporal Validation:** Models are evaluated using leave-repeat-out temporal splits to prevent artificial correlation.
- **Empirical Significance:** Every finding is verified against 200 label-permutation baseline tests ($p < 0.005$) and reported with 95% Wilson score confidence intervals.
- **Machine Learning Suite:** Evaluated Random Forest, XGBoost, 1D-CNN (sequence), GRU (recurrent), open-world detection, scaling curves, and simulated defense mechanisms.

---

## 📁 Repository Directory Structure

```
├── presentation.md            <- Complete conference slide deck & word-for-word speaker notes
├── README.md                  <- This comprehensive project documentation
├── requirements.txt           <- Python dependencies
├── to-do.md                   <- Comprehensive project verification & completion checklist
├── docs/
│   ├── PAPER_DRAFT.md         <- Complete academic research paper draft
│   ├── PRESENTATION_SLIDES.md <- Slide layouts, figures, and presentation notes
│   ├── claims_ledger.csv      <- Cryptographically mapped ledger of all 24 empirical claims
│   └── CAPTURE_COMMANDS.md    <- Runbook for live data collection
├── results/
│   ├── figures/               <- Publication figures (DoH vs DoH/3, Transfer, Blocking, Shifts)
│   ├── airtel_all_20261113/   <- WP7-WP11 & WP13 analysis tables and scaling curves
│   └── jio_analysis_20261113/ <- N1-N8 cross-network transfer and distribution shift results
├── scripts/
│   ├── plot_slide_figures.py  <- Generates the 4 publication slide figures
│   ├── run_airtel_all.py      <- Master runner for all Airtel analyses (WP7-WP11, WP13)
│   ├── run_jio_analysis.py    <- Master runner for Jio & cross-network analyses (N1-N8)
│   └── run_jio_capture.sh     <- Automated 6,000-query Jio cellular capture testbed
└── src/
    ├── probe_and_capture.py   <- Synchronous DNS probe and dumpcap capture engine
    ├── extract_features.py    <- 39-feature network flow extractor
    └── encdns/                <- Analysis library (fingerprinting, baselines, ledger)
```

---

## 🚀 Quickstart & Reproduction Guide

### 1. Environment Setup

```bash
# Clone the repository and switch to branch aman
git checkout aman

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### 2. External Tools
- **Dumpcap & Tshark (Wireshark CLI):**
  - macOS: `brew install wireshark`
  - Linux: `sudo apt install tshark`
- **`q` DNS Client:** Available from [natesales/q releases](https://github.com/natesales/q/releases).

---

### 3. Reproducing the Analysis in Under 6 Minutes

All raw capture datasets have been processed into reproducible feature tables (`data/processed/`). You can re-run the entire empirical analysis suite with three commands:

```bash
# Step 1: Run all Airtel analysis modules (WP7 to WP11, and WP13)
python3 scripts/run_airtel_all.py

# Step 2: Run all Jio & Cross-Network analysis modules (N1 to N8)
python3 scripts/run_jio_analysis.py

# Step 3: Generate all publication-ready slide and paper figures
python3 scripts/plot_slide_figures.py
```

All output tables and figures will be generated deterministically under `results/airtel_all_20261113/`, `results/jio_analysis_20261113/`, and `results/figures/`.

---

### 4. Running the Test Suite

```bash
# Run automated regression tests (10/10 tests pass)
python3 -m unittest discover tests
```

---

## 📄 Key Project Deliverables

- **Academic Paper Draft:** [docs/PAPER_DRAFT.md](docs/PAPER_DRAFT.md) — Complete 9-section conference paper with 9 tables, methodology, ethics, and related work.
- **Presentation Slide Deck:** [presentation.md](presentation.md) — 12-slide Marp-compatible slide deck complete with word-for-word speaker notes.
- **Empirical Claims Ledger:** [docs/claims_ledger.csv](docs/claims_ledger.csv) — Every number cited in the paper and slides is mapped to reproducible CSV outputs.
- **Publication Figures:**
  - [Figure 1: DoH vs. DoH/3 Leakage Comparison](results/figures/fig1_headline_doh_vs_doh3.png)
  - [Figure 2: Cross-Network Transfer Collapse](results/figures/fig2_cross_network_transfer.png)
  - [Figure 3: Carrier-Level QUIC Blocking on Jio](results/figures/fig3_carrier_quic_blocking.png)
  - [Figure 4: Feature Distribution Shifts (Broadband vs. Cellular)](results/figures/fig4_feature_distribution_shift.png)

---

## 🔒 Ethical Considerations & Open Science

- **Passive Observational Study:** No payload decryption, man-in-the-middle interception, or attack against external servers was performed.
- **Privacy Compliance:** No personally identifiable information (PII), credentials, private IP addresses, or raw packet payloads are stored in Git.
- **Reproducibility:** All seeds are fixed (`17`, `42`, `101`), and all evaluation steps are fully automated via open-source scripts.

---

## 👥 Authors & Acknowledgments

- **Aman Kashyap** (`iit2024140@iiita.ac.in`)  
  Department of Information Technology, Indian Institute of Information Technology, Allahabad.  
- Research Methodology Coursework, November 2026.
