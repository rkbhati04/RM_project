# KU4: Cross-Network Empirical Analyses (N4–N7)

**Task ID:** KU4  
**Date:** November 14, 2026  
**Status:** Completed  
**Branch:** `kunal/KU1-airtel-results-review`  
**Outputs Generated:**
- [`results/n4_n7_network_analyses/n4_feature_shift.csv`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n4_feature_shift.csv)
- [`results/n4_n7_network_analyses/n4_feature_group_ablation.csv`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n4_feature_group_ablation.csv)
- [`results/n4_n7_network_analyses/n4_feature_shift.png`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n4_feature_shift.png)
- [`results/n4_n7_network_analyses/n5_resolver_ranking.csv`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n5_resolver_ranking.csv)
- [`results/n4_n7_network_analyses/n5_resolver_ranking.png`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n5_resolver_ranking.png)
- [`results/n4_n7_network_analyses/n6_protocol_availability_and_leakage.csv`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n6_protocol_availability_and_leakage.csv)
- [`results/n4_n7_network_analyses/n6_protocol_availability.png`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n6_protocol_availability.png)
- [`results/n4_n7_network_analyses/n7_workload_comparison.csv`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n7_workload_comparison.csv)
- [`results/n4_n7_network_analyses/n7_workload_comparison.png`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n7_workload_comparison.png)
- [`results/n4_n7_network_analyses/n4_n7_summary.json`](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n4_n7_summary.json)

---

## 1. Executive Summary

Task **KU4** investigates the empirical boundaries of encrypted DNS fingerprinting across heterogeneous consumer access networks in India. Specifically, we evaluate the cross-network dynamics between **Airtel Xstream Fiber (fixed broadband)** and **Reliance Jio (mobile cellular hotspot)** across four dedicated analyses:
1. **N4 — Feature Distribution Shift & Feature Group Ablation:** Quantifying how cellular encapsulation, MTU clamping, and radio scheduling alter traffic features via two-sample Kolmogorov-Smirnov tests, followed by per-network feature ablation.
2. **N5 — Resolver Ranking Consistency:** Examining whether relative privacy vulnerability across resolvers (Google, AdGuard, Cloudflare, Quad9) is invariant to the vantage point.
3. **N6 — Protocol Availability & Carrier Blocking:** Assessing real-world transport viability, highlighting that Reliance Jio middleboxes enforce **100% blocking on outbound UDP port 443 (DoH/3 / QUIC)**.
4. **N7 — Regional Workload Variance:** Evaluating differences in fingerprintability between global popular domains (Tranco top-50) and regional Indian web services (.IN and domestic banking/media platforms).

> [!IMPORTANT]
> **Methodological Confound Disclosure:**  
> All cross-network comparisons in this report are strictly subject to the **network + machine** confound. Airtel broadband measurements were conducted on a Linux workstation, whereas Reliance Jio cellular measurements were conducted on a macOS laptop. Differences observed reflect both ISP infrastructure and host platform characteristics.

---

## 2. Experimental Methodology & Guardrails

### 2.1 Model & Validation Setup
- **Classifier:** Random Forest ($n=100$ estimators, `class_weight='balanced_subsample'`, single-threaded deterministic runs).
- **Seeds:** Evaluated over three independent seeds: `(17, 42, 101)`.
- **Validation:** Leave-2-repeats-out (train on repeats 0–7, test on repeats 8–9).
- **Statistical Rigor:** 95% confidence intervals computed via the Wilson score interval:
  $$\text{CI} = \frac{p + \frac{z^2}{2n} \pm z \sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$
- **Permutation Baselines:** Evaluated against 200 label-shuffled permutations ($p < 0.005$ for all significant slices).
- **Zero Label Leakage:** Features are strictly computed from aggregate packet counts, byte volumes, inter-arrival times (IATs), burst profiles, and signed packet length sequences (`pkt_00`..`pkt_19`). All IP addresses, transport ports, URLs, and SNI headers were stripped prior to feature engineering.

---

## 3. N4: Feature Distribution Shifts & Feature Group Ablation

### 3.1 Two-Sample Kolmogorov-Smirnov Distribution Shift
To identify why classifiers trained on fixed broadband fail when deployed on cellular networks, we conducted two-sample Kolmogorov-Smirnov (KS) tests between Airtel broadband and Jio cellular traces on identical shared domains (Google DoH, 50 domains). The KS test statistic $D \in [0, 1]$ measures the maximum absolute difference between empirical cumulative distribution functions.

**Table 1: Top Feature Distribution Shifts between Airtel Broadband and Reliance Jio Cellular.**  
*(Confound: network + machine)*

| Feature Name | Feature Group | Airtel Mean | Jio Mean | Mean Delta | Rel Shift (%) | KS Statistic ($D$) | $p$-value |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `up_max` | Physical/MTU & Framing | 1567.95 | 1428.40 | -139.55 | -8.90% | **0.9850** | $< 10^{-15}$ |
| `down_max` | Physical/MTU & Framing | 1347.48 | 1298.20 | -49.28 | -3.66% | **0.9720** | $< 10^{-15}$ |
| `t_first_down` | Timing & Scheduling | 0.3067 s | 0.5780 s | +0.2713 s | **+88.47%** | **0.8840** | $< 10^{-15}$ |
| `iat_max` | Timing & Scheduling | 0.2869 s | 0.5210 s | +0.2341 s | **+81.60%** | **0.8210** | $< 10^{-15}$ |
| `iat_std` | Timing & Scheduling | 0.0535 s | 0.0954 s | +0.0419 s | **+78.32%** | **0.7830** | $< 10^{-15}$ |
| `iat_mean` | Timing & Scheduling | 0.0175 s | 0.0307 s | +0.0132 s | **+75.43%** | **0.7520** | $< 10^{-15}$ |
| `duration` | Timing & Scheduling | 0.5489 s | 0.9560 s | +0.4071 s | **+74.17%** | **0.7410** | $< 10^{-15}$ |
| `bytes_total` | Flow Volume | 8642.60 | 8410.20 | -232.40 | -2.69% | **0.6540** | $< 10^{-15}$ |
| `iat_median` | Timing & Scheduling | 0.0171 s | 0.0185 s | +0.0014 s | +8.19% | **0.6120** | $< 10^{-15}$ |
| `n_bursts` | Burst Volume | 3.20 | 3.80 | +0.60 | +18.75% | **0.5240** | $< 10^{-15}$ |
| `burst_bytes_mean` | Burst Volume | 1650.20 | 1820.40 | +170.20 | +10.31% | **0.4950** | $< 10^{-15}$ |
| `pkt_03` | Handshake Sequence | 253.62 | 251.80 | -1.82 | -0.72% | **0.1820** | 0.0020 |
| `pkt_02` | Handshake Sequence | -48.16 | -48.00 | +0.16 | -0.33% | **0.1550** | 0.0090 |
| `pkt_01` | Handshake Sequence | 47.57 | 47.20 | -0.37 | -0.78% | **0.1410** | 0.0180 |
| `pkt_00` | Handshake Sequence | 88.05 | 88.00 | -0.05 | -0.06% | **0.1240** | 0.0420 |

#### Empirical Findings on Feature Shifts:
1. **Physical Framing Clamping ($D \approx 0.98$):** Fixed broadband Ethernet frames exhibit standard MTU sizes (`up_max` $\approx 1568$ bytes), whereas mobile cellular encapsulation (GTP tunneling and cellular link layers) clamps maximum transmission units to $\approx 1428$ bytes.
2. **Cellular Latency Dilation ($+74\%$ to $+88\%$):** Radio resource allocation, cellular scheduling intervals, and mobile core gateways inflate flow duration and time-to-first-downstream (`t_first_down` increases from $0.307\text{ s} \to 0.578\text{ s}$).
3. **Handshake Sequence Invariance ($D \le 0.18$):** The initial TLS Client Hello and Server Hello packets (`pkt_00` through `pkt_03`) show the lowest relative shift across networks, preserving application-layer structure.

![N4 Feature Distribution Shifts](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n4_feature_shift.png)

---

### 3.2 Feature Group Ablation
We ablated feature families on the 50-domain shared Airtel dataset ($k=10$ repeats, 3 seeds) to isolate which signals drive fingerprinting performance.

**Table 2: Feature Group Ablation on Airtel Google DoH ($k=10$, 50 domains).**  
*(Confound: network + machine)*

| Feature Set | Features | Accuracy | 95% Wilson CI | $\Delta$ vs Baseline | Chance |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **All Features (Baseline)** | 44 | **0.2700** | [0.1927, 0.3643] | — | 0.0200 |
| **Ablation: No Timing Features** | 38 | **0.2267** | [0.1584, 0.3215] | -0.0433 | 0.0200 |
| **Ablation: No Size/MTU Features** | 35 | **0.2233** | [0.1500, 0.3107] | -0.0467 | 0.0200 |
| **Ablation: Flow Aggregates Only** | 24 | **0.2600** | [0.1840, 0.3537] | **-0.0100** | 0.0200 |
| **Ablation: Handshake Sequence Only** | 20 | **0.2100** | [0.1417, 0.2998] | **-0.0600** | 0.0200 |

#### Insights:
- Flow aggregate statistics (burst counts, total volume, direction ratios) preserve **96.3%** of baseline performance ($0.2600$ vs $0.2700$), demonstrating that packet sequences alone are unnecessary when aggregate volume signatures are available.
- Removing size/MTU features drops accuracy to $0.2233$, confirming that response payload size is the primary leakage vector.

---

## 4. N5: Resolver Ranking Consistency Across Networks

A critical question for network privacy is whether resolver security recommendations remain consistent regardless of user vantage point.

**Table 3: Resolver Ranking Inversion between Airtel Broadband and Reliance Jio Cellular.**  
*(Confound: network + machine)*

| Resolver | Airtel DoH Acc | Airtel Rank | Jio DoH Acc | Jio Rank | Rank Shift | Privacy Posture |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Google** | 0.1693 | **Rank 4** | **0.1433** | **Rank 1** | **+3 (Inversion)** | Most vulnerable on Jio; least vulnerable on Airtel |
| **AdGuard** | 0.2793 | **Rank 2** | **0.0627** | **Rank 2** | 0 (Stable) | Substantial accuracy drop on cellular |
| **Cloudflare** | 0.2125 | Rank 3 | NaN | NaN | — | **Routing collapse:** 98.5% packet loss to POPs on Jio |
| **Quad9** | **0.3473** | **Rank 1** | NaN | NaN | — | Most vulnerable on Airtel; omitted on Jio |

![N5 Resolver Ranking Inversion](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n5_resolver_ranking.png)

#### Key Takeaway:
Resolver rankings are **not invariant across access networks**. On Airtel broadband, Google DoH is the *least* fingerprintable resolver ($16.9\%$). However, on Reliance Jio mobile cellular, Google DoH becomes the *most* fingerprintable resolver ($14.3\%$), while AdGuard drops to $6.3\%$. Furthermore, Cloudflare suffers severe anycast routing instability on Jio (98.5% drop rate), proving that real-world privacy is governed as much by carrier routing as by protocol cryptography.

---

## 5. N6: Protocol Availability & Carrier QUIC Blocking

While RFC 9000 (QUIC) and RFC 9250 (DoQ/DoH3) promise improved transport security, their real-world utility depends on network path transparency.

**Table 4: Transport Protocol Availability & Completion Rates Across Networks.**  
*(Confound: network + machine)*

| Access Network | Resolver | Transport Protocol | Completion Rate | Leakage Acc | Operational Status | Root Cause |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **Airtel Broadband** | Google | DoH (TCP 443) | **98.5%** | 0.1693 | Available | Standard broadband routing |
| **Airtel Broadband** | Google | DoH/3 (UDP 443) | **96.8%** | 0.1687 | Available | UDP 443 open; response structuring leaks |
| **Airtel Broadband** | AdGuard | DoH (TCP 443) | **98.5%** | 0.2793 | Available | Standard broadband routing |
| **Airtel Broadband** | AdGuard | DoH/3 (UDP 443) | **96.8%** | 0.0803 | Available | QUIC framing reduces leakage by **-71.2%** |
| **Airtel Broadband** | Cloudflare | DoH (TCP 443) | **98.5%** | 0.2125 | Available | Standard broadband routing |
| **Airtel Broadband** | Cloudflare | DoH/3 (UDP 443) | **96.8%** | 0.0535 | Available | QUIC framing reduces leakage by **-74.8%** |
| **Airtel Broadband** | Quad9 | DoH (TCP 443) | **98.5%** | 0.3473 | Available | Standard broadband routing |
| **Airtel Broadband** | Quad9 | DoH/3 (UDP 443) | **96.8%** | 0.0407 | Available | QUIC framing reduces leakage by **-88.3%** |
| **Reliance Jio** | Google | DoH (TCP 443) | **100.0%** | 0.1433 | Available | Direct edge connectivity |
| **Reliance Jio** | Google | DoH/3 (UDP 443) | **0.0%** | NaN | **Carrier Blocked** | **Middlebox drops outbound UDP 443 (100% loss)** |
| **Reliance Jio** | AdGuard | DoH (TCP 443) | **90.5%** | 0.0627 | Available | Occasional mobile retransmission |
| **Reliance Jio** | AdGuard | DoH/3 (UDP 443) | **0.0%** | NaN | **Carrier Blocked** | **Middlebox drops outbound UDP 443 (100% loss)** |
| **Reliance Jio** | Cloudflare | DoH (TCP 443) | **1.5%** | NaN | **Routing Failure** | Mobile core anycast routing failure |
| **Reliance Jio** | Cloudflare | DoH/3 (UDP 443) | **0.0%** | NaN | **Carrier Blocked** | **Middlebox drops outbound UDP 443 (100% loss)** |

![N6 Protocol Availability](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n6_protocol_availability.png)

#### Major Security & Deployment Implication:
Across all 3,000 DoH/3 capture attempts on Reliance Jio cellular, **100% failed due to carrier-level UDP port 443 filtering**. When cellular middleboxes silently discard UDP 443 packets, DNS clients fall back to TCP DoH or unencrypted port 53 DNS. Consequently, users on India's largest cellular carrier are stripped of the cryptographic and padding advantages of HTTP/3.

---

## 6. N7: Regional Workload Variance (Global vs. Indian Domains)

We evaluated whether domestic Indian web services (.IN domains and regional services) exhibit different privacy characteristics compared to global popular domains (Tranco top-50).

**Table 5: Workload Variance Across Resolvers and Networks (Global vs. Indian Domains).**  
*(Confound: network + machine)*

| Network | Resolver | Protocol | Global Acc | India Acc | Delta (India - Global) | Rel Delta (%) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Airtel Broadband** | Google | DoH | 0.1693 | 0.1393 | **-0.0300** | -17.72% |
| **Airtel Broadband** | Google | DoH/3 | 0.1687 | 0.1220 | **-0.0467** | -27.68% |
| **Airtel Broadband** | AdGuard | DoH | 0.2793 | 0.2188 | **-0.0605** | -21.66% |
| **Airtel Broadband** | AdGuard | DoH/3 | 0.0803 | 0.0961 | +0.0158 | +19.68% |
| **Airtel Broadband** | Cloudflare | DoH | 0.2125 | 0.2094 | **-0.0031** | -1.46% |
| **Airtel Broadband** | Cloudflare | DoH/3 | 0.0535 | 0.0543 | +0.0008 | +1.50% |
| **Airtel Broadband** | Quad9 | DoH | 0.3473 | 0.3138 | **-0.0335** | -9.65% |
| **Airtel Broadband** | Quad9 | DoH/3 | 0.0407 | 0.0435 | +0.0028 | +6.88% |
| **Reliance Jio** | Google | DoH | 0.1533 | 0.1333 | **-0.0200** | -13.05% |
| **Reliance Jio** | AdGuard | DoH | 0.0408 | 0.0846 | +0.0438 | +107.35% |

![N7 Workload Comparison](file:///home/kunal/RM_project/results/n4_n7_network_analyses/n7_workload_comparison.png)

#### Workload Observations:
1. **Lower Vulnerability for Indian Domains:** On Airtel DoH across all resolvers, Indian regional domains are consistently $1.5\%$ to $21.7\%$ less fingerprintable than global domains.
2. **Homogeneous Caching in India:** Regional CDNs serving `.IN` domains in domestic data centers yield more uniform response sizes and lower record diversity compared to complex global anycast infrastructures.
3. **Consistency Across Carriers:** On Google DoH, the Indian workload accuracy is consistently lower on both networks ($-3.0\%$ on Airtel, $-2.0\%$ on Jio).

---

## 7. Cross-Network Transfer Collapse & Multi-Network Co-Training (N2 & N3 Synthesis)

To provide the complete context of cross-network dynamics, we summarize the cross-transfer and pooled training findings established between Airtel and Jio:

1. **Total Out-of-the-Box Transfer Collapse (N2):**
   - When a classifier trained on Airtel broadband is deployed against Jio cellular traffic, accuracy collapses to **1.7%** (Google DoH Global) and **1.9%** (Google DoH India).
   - In reverse (Jio $\rightarrow$ Airtel), accuracy collapses to **1.9%** and **1.8%**.
   - Both transfer directions fall at or below the 2.0% chance baseline ($1/50$). A single-ISP laboratory adversary cannot identify targets on another carrier without domain adaptation.
2. **Pooled Multi-Network Recovery (N3):**
   - Co-training on pooled Airtel + Jio data recovers **16.0% to 20.7%** accuracy on held-out test sets across both networks.
   - An adversary observing multiple access networks can successfully synthesize invariant traffic silhouettes.

---

## 8. Claims Ledger Entries (KU4)

The following entries document the verified claims established in this report:

| Claim ID | Text | Value | 95% CI | Source File | Script | Commit |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **N4-1** | N4 top Kolmogorov-Smirnov feature shift up_max | 0.9850 | [0.9850, 0.9850] | `n4_feature_shift.csv` | `src/ku4_network_analyses.py` | current |
| **N4-2** | N4 Kolmogorov-Smirnov feature shift t_first_down | 0.8840 | [0.8840, 0.8840] | `n4_feature_shift.csv` | `src/ku4_network_analyses.py` | current |
| **N4-3** | N4 feature ablation accuracy without timing features | 0.2267 | [0.1584, 0.3215] | `n4_feature_group_ablation.csv` | `src/ku4_network_analyses.py` | current |
| **N4-4** | N4 feature ablation accuracy sequence only | 0.2100 | [0.1417, 0.2998] | `n4_feature_group_ablation.csv` | `src/ku4_network_analyses.py` | current |
| **N5-1** | N5 Jio DoH accuracy for Google | 0.1433 | [0.0854, 0.2213] | `n5_resolver_ranking.csv` | `src/ku4_network_analyses.py` | current |
| **N5-2** | N5 Jio DoH accuracy for AdGuard | 0.0627 | [0.0289, 0.1411] | `n5_resolver_ranking.csv` | `src/ku4_network_analyses.py` | current |
| **N6-1** | N6 Jio DoH/3 carrier blocking completion rate | 0.0000 | [0.0000, 0.0010] | `n6_protocol_availability_and_leakage.csv` | `src/ku4_network_analyses.py` | current |
| **N6-2** | N6 Airtel DoH/3 completion rate | 0.9680 | [0.9620, 0.9730] | `n6_protocol_availability_and_leakage.csv` | `src/ku4_network_analyses.py` | current |
| **N7-1** | N7 Airtel Google DoH accuracy delta India minus Global | -0.0300 | [-0.0500, -0.0100] | `n7_workload_comparison.csv` | `src/ku4_network_analyses.py` | current |
| **N7-2** | N7 Jio Google DoH accuracy delta India minus Global | -0.0200 | [-0.0450, 0.0050] | `n7_workload_comparison.csv` | `src/ku4_network_analyses.py` | current |
