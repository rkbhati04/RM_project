# Action Plan: Privacy Analysis of DNS-over-HTTP/3 (DoH/3)

## Research Problem
Modern encrypted DNS protocols like **DNS-over-HTTP/3 (DoH/3)** protect query content from on-path observers using QUIC encryption and multiplexing. However, encryption does not eliminate observable packet metadata such as packet sizes, timing, directionality, and burst structures.

This project systematically investigates the privacy guarantees and metadata leakage of **DoH/3**, determining whether an eavesdropper can identify queried domains and which traffic characteristics are responsible for leakage.

---

## Reframed Research Questions (DoH/3 Focused)

- **RQ1: Can DNS queries over DoH/3 be distinguished using encrypted traffic metadata?**  
  *Investigation:* Evaluate domain fingerprinting / query identification on DoH/3 traffic using supervised machine learning models (Random Forest and XGBoost) evaluated on held-out capture repeats across 50 domains (25 Global, 25 Indian).

- **RQ2: How strong is the traffic-analysis resistance of DoH/3 across different public resolvers?**  
  *Investigation:* Compare DoH/3 implementation privacy across major resolvers (**Cloudflare, Google, Quad9, AdGuard**). Quantify resistance using Top-1 and Top-5 accuracy, Wilson 95% confidence intervals, and empirical label-permutation chance baselines.

- **RQ3: Which traffic characteristics (packet sizes, timing, burst patterns, directionality, flow statistics) contribute most to metadata leakage in DoH/3?**  
  *Investigation:* Rank individual feature importance (RF MDI), group-level importance (volume, packet size stats, timing/IAT, bursts, first-20 signed packet sequence), and perform systematic group ablation and ANOVA F-tests.

- **RQ4: How does DoH/3 metadata leakage vary across different public resolvers and access networks?**  
  *Investigation (Future / Extended):* Cross-resolver transferability and access-network variability (Airtel and approved home networks).

- **RQ5: How do the diversity and characteristics of DNS workloads affect DoH/3 metadata leakage (Global vs. Indian domains)?**  
  *Investigation (Future / Extended):* Compare query fingerprintability between Tranco Global top domains and Indian public services/e-commerce domains.

---

## 1-Day Execution Scope: RQ1, RQ2, and RQ3

Because time is limited to **1 day**, we focus on executing **RQ1, RQ2, and RQ3**:

| Phase | Script | Input | Output | Status |
|-------|--------|-------|--------|--------|
| **1. Workload Construction** | `src/build_workloads.py` | Tranco Top 1M list | `data/workloads/global.txt`, `india.txt` | ✅ Complete (50 domains) |
| **2. Traffic Capture** | `src/probe_and_capture.py` | Network interface + q | `data/raw/pcaps/*.pcap`, `manifest.csv` | ✅ Complete (4002 pcaps) |
| **3. Feature Extraction** | `src/extract_features.py` | pcaps + manifest | `data/processed/dataset.csv` | ✅ Complete (3550 rows, 1554 DoH/3) |
| **4. DoH/3 Analysis (RQ1-3)** | `src/doh3_rq123_analysis.py` | `dataset.csv` | `results/doh3/*.csv`, `*.png`, `report.md` | ⭐ Ready to Run |
| **5. Quick Validation** | `src/run_experiments.py` | `dataset.csv` | Terminal output summary | ⭐ Ready to Run |

---

## Execution Order

1. Check current status:
   ```powershell
   python src\data_status.py
   ```
2. Run rapid DoH/3 experiments:
   ```powershell
   python src\run_experiments.py
   ```
3. Run comprehensive DoH/3 analysis with publication-ready charts and statistical baselines:
   ```powershell
   python src\doh3_rq123_analysis.py --quick
   # Or for full 20-permutation statistical rigor:
   python src\doh3_rq123_analysis.py
   ```
4. View generated figures and report in `results/doh3/`.
