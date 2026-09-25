# Privacy Analysis of Modern Encrypted DNS

An empirical research methodology study evaluating the side-channel traffic analysis resistance of modern QUIC-based encrypted DNS protocols (**DNS-over-QUIC / DoQ**, RFC 9250 and **DNS-over-HTTP/3 / DoH/3**, RFC 9114) against standard **DNS-over-HTTPS (DoH)** (RFC 8484 over HTTP/2).

---

## 1. Executive Summary

Encrypted DNS protocols encrypt DNS query and response payloads to prevent on-path eavesdroppers and ISPs from inspecting domain queries directly. However, unencrypted transport-layer metadata—packet sizes, flow duration, burst patterns, directionality, and packet inter-arrival times—remains visible.

This project implements a controlled, reproducible closed-world measurement testbed to evaluate whether QUIC-based encrypted DNS transports improve privacy or expose new side-channel leakage channels.

### Key Empirical Findings

| Experiment | Target Research Question | Model & Methodology | Empirical Finding |
| :--- | :--- | :--- | :--- |
| **E1** | **RQ1:** Protocol Identification | Random Forest (3-Way) | **97.44% Accuracy** (Macro-F1: 0.9783). Protocols leak distinct handshake and framing signatures even with ports/IPs excluded. |
| **E2** | **RQ2:** Website Fingerprinting | Multi-Class XGBoost (50 classes) | **DoH/3 is most private (4.44% acc)**. **DoQ leaks the most metadata (9.57% acc)** due to lack of HTTP frame multiplexing noise. |
| **E3** | **RQ3:** Feature Leakage Attribution | RF Gini Importance & Ablation | **Inter-Arrival Times (IAT)** and early handshake packet sizes (`pkt_00`–`pkt_19`) are the primary leakage vectors. |
| **E4** | **RQ4:** Cross-Resolver Generalizability | Cross-Resolver Transfer | **Zero generalization across resolvers (1.83% acc)**. Fingerprint signatures are strictly resolver-dependent. |
| **E5** | **RQ5:** Regional Workload Variance | Global vs. Indian Workloads | **Indian regional services are 3.8x more fingerprintable (9.17%)** than standardized global edge CDN services (2.40%). |

---

## 2. Research Questions

- **RQ1 (Protocol Identification):** Can DoQ, DoH/3, and DoH queries be distinguished using encrypted traffic metadata alone without inspecting transport ports (443 vs 853) or IP addresses?
- **RQ2 (Traffic Analysis Resistance):** Which encrypted DNS protocol exhibits the highest resistance to website fingerprinting attacks?
- **RQ3 (Feature Leakage Attribution):** Which specific traffic features (packet sizes, timing/IAT, burst sequences, or early handshake packets) drive metadata leakage?
- **RQ4 (Resolver & Network Dependency):** How does leakage vary across public resolvers (AdGuard vs Quad9) and access networks, and do fingerprint models generalize across resolvers?
- **RQ5 (Regional Workload Variance):** Do Indian domains (e-commerce, payment systems, `.in` TLDs) exhibit different privacy characteristics compared to top global domains?

---

## 3. Project Structure

```
├── README.md                 <- Project overview, methodology, and empirical results
├── requirements.txt          <- Python dependency specifications
├── src/
│   ├── build_workloads.py    <- Generates pinned Tranco L5PV4 Global and Indian domain lists
│   ├── probe_and_capture.py  <- Timed packet capture testbed (q DNS client + dumpcap)
│   ├── extract_features.py   <- Extracts 39 transport-agnostic metadata features from PCAPs
│   ├── run_experiments.py    <- ML evaluation suite (E1 to E5 with RF & XGBoost)
│   └── plot_results.py       <- Generates publication-ready figures in results/
├── data/
│   ├── workloads/            <- Frozen domain lists (global.txt, india.txt, metadata.json)
│   ├── raw/                  <- PCAP captures and capture manifest.csv
│   └── processed/            <- Extracted feature table (dataset.csv)
└── results/                  <- Generated confusion matrices, accuracy plots, and evaluation tables
```

---

## 4. Methodology & Experimental Controls

### 4.1 Target Workload Design
- **Pinned Ranking:** Pinned to Tranco list `L5PV4` to eliminate temporal ranking drift.
- **Closed-World Set (50 domains):** 
  - **Global Workload (25 domains):** Top-ranked global services (Google, Cloudflare, Microsoft, Apple, etc.).
  - **Indian Workload (25 domains):** Top `.in` domains and regional seed services (Flipkart, Zomato, Jio, Paytm, Swiggy, Government portals).
- **Liveness Verification:** Lazily validated via active socket resolution before collection.

### 4.2 Data Collection Protocol
- **Testbed Engine:** Combines the `q` CLI DNS client (supporting HTTP/2 DoH, HTTP/3 DoH/3, and QUIC DoQ) with native `dumpcap` packet capture.
- **BPF Isolation:** Captures are bound to resolver IPs on specific ports (`port 443 or port 853`) to eliminate background OS traffic.
- **Timed Capture Window:** 3.0-second fixed capture window with 1.0-second dumpcap warmup. Queries exceeding 1.5s latency are flagged as `incomplete` to prevent truncated flow artifacts.
- **Repeat Independence:** Repeats are executed as the outer loop across time of day. Evaluation splits strictly train on repeats 0 and 1, testing on repeat 2 to prevent temporal session leakage.

### 4.3 Feature Engineering (Zero Label Leakage)
Extracts **39 metadata features** from each flow:
- **Packet Counts & Bytes:** Total bytes, upstream/downstream bytes, byte ratio (`ratio_bytes_down_up`).
- **Timing & Inter-Arrival Times:** Flow duration, time to first response packet (`t_first_down`), mean/std/median/max IAT.
- **Burst Dynamics:** Unidirectional packet sequence counts, burst byte volumes, and burst lengths.
- **Handshake Sequence:** Signed sizes of the first 20 packets (`pkt_00` to `pkt_19`).
- **Strict Safeguards:** IP addresses, port numbers (443 vs 853), and transport protocols are strictly excluded.

---

## 5. Setup & Reproduction Guide

### Environment Setup

The pipeline supports both **macOS (Apple Silicon / Intel)** and **Windows**.

#### 1. Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt numpy pandas xgboost
```

#### 2. External Tools
- **Wireshark CLI (`dumpcap` and `tshark`):**
  - macOS: `HOMEBREW_NO_AUTO_UPDATE=1 brew install wireshark`
  - Windows: Install Wireshark with Npcap.
- **`q` DNS Client:**
  - macOS: Download precompiled binary from `https://github.com/natesales/q/releases` into `./bin/q`.
  - Windows: Place `q.exe` in `C:\Program Files\Q\q.exe` or on `PATH`.

---

### Step-by-Step Reproduction Pipeline

#### Step 1: Generate Workloads
```bash
python3 src/build_workloads.py --tranco-id L5PV4 --count 25 --pool 1000000
```

#### Step 2: Probe & Capture Encrypted Traffic
```bash
# AdGuard and Quad9 across DoH, DoH/3, and DoQ (3 repeats = 900 queries)
python3 src/probe_and_capture.py \
  --network airtel \
  --workload both \
  --all-domains \
  --repeats 3 \
  --resolvers adguard quad9 \
  --protocols doh doh3 doq \
  --resume
```

#### Step 3: Extract Metadata Features
```bash
python3 src/extract_features.py --max-latency 1.5
```

#### Step 4: Run Machine Learning Experiments
```bash
python3 src/run_experiments.py
```

#### Step 5: Generate Publication Figures
```bash
python3 src/plot_results.py
```

---

## 6. Real-World Network Findings

1. **Enterprise / Campus Firewall Filtering:**  
   Probing on institutional campus Wi-Fi revealed that university firewalls drop outbound UDP on ports 443 and 853, blocking DoH/3 and DoQ entirely and forcing HTTP proxy traversal. Consumer cellular networks (Airtel) allowed unhindered QUIC communication.
2. **Resolver Transport Reliability:**  
   On Airtel, Quad9 DoH (TCP) exhibited frequent connection timeouts (~33% completion), while Quad9 QUIC (DoH/3 and DoQ) achieved over 92% completion.
3. **Counter-Intuitive QUIC Privacy:**  
   While DoQ minimizes protocol overhead, it exposes raw payload sizes. DoH/3's HTTP/3 multiplexing and control framing act as accidental padding, making it significantly more resistant to website fingerprinting than DoQ.

---

## 7. Ethical Considerations

- **Passive Observational Study:** No decryption, MITM, or payload inspection was performed.
- **Scope:** Controlled closed-world experiment conducted strictly for academic research methodology evaluation.
- **Privacy Safeguards:** Raw PCAP files, CSV manifests, and datasets are excluded from Git version control per `.gitignore`.
