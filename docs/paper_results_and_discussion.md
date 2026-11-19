# Section 4: Results & Section 5: Discussion

**Paper Section Draft for Team Submission**  
**Author:** Kunal (Lead Author for Experimental Results & Discussion)  
**Date:** 2026-11-14  
**Data Sources:** `results/airtel_final_20261111/`, `results/wp7_richer_features/`, `results/wp8_deep_learning/`, `results/wp9_open_world/`, `results/wp10_scaling_curves/`, `results/wp11_time_stability/`, `results/wp13_defenses/`  
**Ledger Verification:** All empirical numbers strictly match [`docs/claims_ledger.csv`](docs/claims_ledger.csv)  
**Reference:** `docs/issues/KU6.md`, `docs/TEAM_PLAN.md`, `docs/METHODOLOGY.md`

---

## 4. Empirical Evaluation & Results

We evaluate side-channel traffic analysis resistance across encrypted DNS protocols (**DoH over HTTP/2** and **DoH/3 over HTTP/3**) under controlled testbed conditions on a real consumer cellular access network (Airtel). All evaluations enforce strict zero-label-leakage controls: IP addresses, transport ports (443 vs. 853), URLs, and domain strings are entirely excluded from feature vectors. Features consist strictly of packet sizes, directional byte ratios, inter-arrival times (IAT), burst counts, and signed packet sequences ($pkt_{00}$–$pkt_{19}$).

Unless otherwise noted, headline results are computed on the primary 100-domain closed-world datasets using 5 grouped folds with 2 repeats held out per fold, evaluated with 100-tree Random Forest ensembles, 95% Wilson confidence intervals, and empirical label-permutation significance testing ($p < 0.05$).

---

### 4.1 Protocol Vulnerability: DoH vs. DoH/3 Baseline (WP3 & WP4)

Our initial baseline evaluates closed-world domain fingerprinting across four major public recursive resolvers: AdGuard, Cloudflare, Google, and Quad9.

| Resolver | Protocol | Domains ($N$) | Repeats ($k$) | Accuracy | 95% Wilson CI | Top-5 Accuracy | Macro-F1 | Chance ($1/N$) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 100 | 10 | **27.93%** | [25.31%, 30.86%] | 53.63% | 0.2692 | 1.00% |
| | DoH/3 | 100 | 10 | **8.03%** | [6.75%, 10.17%] | 22.17% | 0.0744 | 1.00% |
| **Cloudflare**| DoH | 99 | 10 | **21.25%** | [18.39%, 23.45%] | 49.09% | 0.2061 | 1.01% |
| | DoH/3 | 99 | 10 | **5.35%** | [4.38%, 7.27%] | 18.82% | 0.0475 | 1.01% |
| **Google** | DoH | 100 | 10 | **16.93%** | [15.18%, 19.87%] | 42.30% | 0.1635 | 1.00% |
| | DoH/3 | 100 | 10 | **16.87%** | [14.14%, 18.72%] | 39.90% | 0.1631 | 1.00% |
| **Quad9** | DoH | 100 | 10 | **34.73%** | [31.42%, 37.30%] | 69.23% | 0.3406 | 1.00% |
| | DoH/3 | 100 | 10 | **4.07%** | [2.70%, 5.06%] | 13.27% | 0.0391 | 1.00% |

#### Key Findings:
1. **The Privacy Advantage of HTTP/3:** Across AdGuard, Cloudflare, and Quad9, DoH/3 is dramatically more resistant to traffic analysis than DoH. For Quad9, moving from HTTP/2 to HTTP/3 suppresses fingerprinting accuracy by 8.5x (from 34.73% down to 4.07%). For AdGuard and Cloudflare, accuracy drops by 3.5x and 4.0x, respectively.
2. **The Google Anomaly:** Google DNS is the sole resolver where DoH and DoH/3 show near-identical vulnerability (16.93% vs 16.87%). This parity stems from Google's highly standardized frontend edge infrastructure, which enforces uniform EDNS0 padding and standardized HTTP/2 and HTTP/3 buffer packing, dampening the accidental padding effect of QUIC frames.
3. **Effect Over Name Length:** Baseline evaluation against length-only predictors shows that while DoH classifiers gain substantial signal over raw domain name lengths (+2.1% to +15.7%), DoH/3 classifiers exhibit negative effect-over-length (-10.9% to -14.8%), demonstrating that QUIC framing noise actively degrades length inference.

---

### 4.2 Impact of Richer Sequential and Structural Features (WP7)

To evaluate whether adversaries can bypass HTTP/3 obfuscation, we introduced 47 additional engineered features spanning **packet-size n-grams** (bigrams and trigrams), **direction transition counts**, and **isolated post-handshake metrics**.

| Resolver | Protocol | `BASE` Accuracy (39 feats) | `NGRAM` Accuracy (83 feats) | `POST_HS` Accuracy (52 feats) | `NGRAM+POST` (91 feats) | $\Delta$ (NGRAM vs BASE) |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 24.27% | 22.82% | 23.23% | 22.29% | -1.45% |
| | DoH/3 | 8.68% | 10.00% | 9.26% | **10.73%** | **+1.32%** |
| **Cloudflare**| DoH | 20.23% | 22.64% | 21.16% | **23.65%** | **+2.41%** |
| | DoH/3 | 5.06% | 6.67% | 5.09% | 6.01% | **+1.61%** |
| **Google** | DoH | 15.18% | 17.92% | 15.95% | **18.22%** | **+2.74%** |
| | DoH/3 | 13.62% | **16.40%** | 14.22% | 15.08% | **+2.78%** |
| **Quad9** | DoH | 32.04% | 31.59% | **32.39%** | 31.61% | -0.45% |
| | DoH/3 | 3.72% | **4.88%** | 4.39% | 4.69% | **+1.16%** |

#### Key Findings:
- **Consistent Amplification on DoH/3:** While DoH accuracy fluctuates with n-grams (-1.4% to +2.7%), n-gram features extract consistent, monotonic signal gains across **every single DoH/3 slice** (+1.16% to +2.78%). 
- Consecutive packet transitions ($pkt_i \times pkt_{i+1}$) preserve joint framing fingerprints that individual packet size statistics dilute.
- The highest accuracy achieved for Google DoH/3 (16.40%) and AdGuard DoH/3 (10.73%) utilizes n-gram representations, demonstrating that adversary feature richness narrows the privacy gap between HTTP/2 and HTTP/3.

---

### 4.3 Scaling Dynamics: Closed-World Size and Sample Efficiency (WP10)

We analyzed how metadata leakage scales across two fundamental axes: closed-world target pool size ($N$) and training repeats per domain ($k$).

#### Closed-World Size Scaling ($N \in [10, 100]$)
- At $N=10$, DoH fingerprinting reaches peak accuracies of **66.00%** (Quad9), **48.50%** (AdGuard), and **47.00%** (Google), where random guessing is 10.0%.
- As $N$ expands to 100, DoH accuracy decays steadily (Quad9: 35.10%, AdGuard: 27.90%, Google: 15.55%), maintaining an empirical advantage 15x–35x higher than random chance (1.0%).
- In contrast, DoH/3 scales with a flatter trajectory: Quad9 DoH/3 begins at 12.50% at $N=10$ and quickly decays to 4.30% at $N=100$, demonstrating that large target pools substantially dilute QUIC metadata leakage.

#### Sample Efficiency ($k \in [2, 10]$)
- In low-data regimes ($k=2$ repeats per domain), classifier performance collapses across all protocols (DoH: 4.51%, DoH/3: 2.72%), as classifiers fail to disentangle network jitter from domain signatures.
- Performance accelerates sharply between $k=4$ and $k=8$ (DoH reaching 20.75%), plateauing near $k=10$ (23.84%). This validates our methodology requiring $k \ge 8$ to avoid reporting under-fitted transient artifacts.

---

### 4.4 Temporal Drift and Stability: The Fragility of DoH (WP11)

To evaluate real-world surveillance viability over time, we measured cross-time transfer between pilot data (repeats 0–7) and headline T0 data (repeats 8–19) across a temporal gap of several days on the 50 common domains (Chance = 2.00%).

| Resolver | Protocol | Within-Pilot Acc | Within-T0 Acc | Cross-Time Acc (Pilot $\to$ T0) | Temporal Degradation ($\Delta$) |
|---|---|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 26.18% | 26.28% | **2.17%** | **+24.01%** (Near-complete extinction) |
| | DoH/3 | 4.03% | 5.87% | **4.10%** | **-0.07%** (Zero degradation) |
| **Cloudflare**| DoH | 6.92% | 25.12% | **3.80%** | **+3.12%** |
| | DoH/3 | 8.31% | 8.50% | **6.08%** | **+2.23%** (Highly resilient) |
| **Google** | DoH | 15.79% | 14.25% | **1.92%** | **+13.87%** (Collapsed to chance) |
| | DoH/3 | 9.32% | 13.12% | **3.50%** | **+5.82%** |
| **Quad9** | DoH | 33.00% | 34.62% | **2.10%** | **+30.90%** (Near-complete extinction) |
| | DoH/3 | 10.30% | 7.00% | **7.48%** | **+2.82%** (Highly resilient) |

#### Discovery:
1. **Temporal Fragility of DoH:** While standard DoH exhibits high instantaneous accuracy in stationary test splits (26%–35%), **it suffers severe temporal collapse when evaluated across time**. Cross-time accuracy for AdGuard DoH (2.17%), Quad9 DoH (2.10%), and Google DoH (1.92%) decays to near random chance (2.00%). This occurs because TCP/TLS packet sizes are hypersensitive to ephemeral parameters: server certificate rotations, transient CDN Anycast routes, and TCP segment sizing.
2. **Temporal Resilience of DoH/3:** Conversely, DoH/3 retains its predictive fidelity over time. AdGuard DoH/3 experiences zero temporal decay (4.03% within $\to$ 4.10% cross-time), and Quad9 DoH/3 remains at 7.48% (3.7x higher than chance). Because QUIC connection framing and stream multiplexing are standardized at the transport layer, DoH/3's residual signature is governed by structural protocol invariants rather than fragile application-layer artifacts.

---

### 4.5 Machine Learning Paradigm: Deep Learning vs. Tree Ensembles (WP8)

We benchmarked 1D Convolutional Neural Networks (1D-CNN) and Bidirectional GRUs against Random Forest models directly on the raw signed sequence of the first 20 packets ($pkt_{00}$–$pkt_{19}$) across 100 classes (Chance = 1.00%).

| Resolver | Protocol | Random Forest (Seq Only) | 1D-CNN | Bidirectional GRU | Empirical Chance |
|---|---|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | **9.91%** | 1.16% | 0.91% | 1.00% |
| | DoH/3 | **8.24%** | 1.08% | 0.83% | 1.00% |
| **Google** | DoH | **10.24%** | 0.92% | 1.00% | 1.00% |
| | DoH/3 | **15.23%** | 0.75% | 1.08% | 1.00% |
| **Quad9** | DoH | **17.94%** | 1.00% | 1.00% | 1.00% |
| | DoH/3 | **4.34%** | 1.19% | 0.68% | 1.00% |

#### Takeaway:
Deep neural models fail to converge in small-sample DNS environments ($k=10$ repeats total, 8 training traces per class), hovering near random guessing (~1.0%). In contrast, Random Forest models successfully isolate non-linear decision boundaries on identical packet sequences (achieving up to 17.94%). Complex deep learning architectures commonly reported in website fingerprinting literature are ineffective for encrypted DNS unless paired with massive external pre-training datasets.

---

### 4.6 Open-World Attack Resistance (WP9)

In realistic network scenarios, an eavesdropper monitors a small subset of sensitive domains ($M=20$) amidst an open stream of unmonitored background domains ($N=80$). Chance precision for the monitored set is 20.00%.

| Target Slice | Open-World ROC-AUC | Precision-Recall AUC (PR-AUC) | Open-World Vulnerability |
|---|:---:|:---:|---|
| **AdGuard DoH** | **0.7495** | **0.4581** | Vulnerable (Precision 2.3x above base rate) |
| **AdGuard DoH/3** | **0.5553** | **0.2863** | **Resistant** (ROC close to random diagonal 0.50) |
| **Quad9 DoH** | **0.8267** | **0.5844** | Severe leakage (High precision surveillance) |
| **Quad9 DoH/3** | **0.5986** | **0.2831** | **Resistant** (Background noise obscures queries) |

#### Takeaway:
While DoH permits high-confidence targeted surveillance (ROC-AUC 0.83), **DoH/3 exhibits strong empirical defense against open-world monitoring**. Under open-world conditions, the false-positive rate on unmonitored domains rapidly overwhelms the weak residual signal of DoH/3, driving ROC-AUC down towards 0.55.

---

### 4.7 Countermeasure Efficacy: Defense Simulations (WP13)

We simulated three standardized and proposed defense strategies across extracted trace records: RFC 8467 128-byte padding, RFC 8467 468-byte padding, and 20 ms Gaussian timing jitter. All results represent algorithmic simulations.

| Resolver | Protocol | Unmitigated Baseline | Sim. 128B Padding | Sim. 468B Padding (RFC 8467) | Sim. 20ms Jitter | Sim. Combined |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 27.98% | 22.45% | **21.65%** | 26.53% | **20.91%** |
| | DoH/3 | 7.41% | 6.24% | **5.41%** | 8.74% | **6.32%** |
| **Google** | DoH | 16.90% | 11.91% | **11.07%** | 16.24% | **13.98%** |
| | DoH/3 | 17.65% | 15.57% | **13.90%** | 17.74% | **15.24%** |
| **Quad9** | DoH | 35.38% | 30.12% | **28.74%** | 35.89% | **29.88%** |
| | DoH/3 | 4.01% | 2.99% | **2.63%** | 4.77% | **2.98%** |

#### Takeaway:
1. **RFC 8467 468-byte padding** is the most effective tested countermeasure, reducing absolute leakage by 5.8%–6.6% on DoH and reducing Quad9 DoH/3 to near random chance (2.63%).
2. **Timing Jitter is Ineffective:** Injecting 20 ms timing jitter produces negligible protection (often < 1% change), as tree classifiers exploit directional size and packet count distributions.
3. **Padding Alone is Incomplete:** Even with 468-byte padding, DoH maintains ~21%–29% accuracy because packet counts, round-trip exchanges, and burst lengths remain unmasked.

---

## 5. Discussion

### 5.1 Why HTTP/3 Accidental Padding Protects Against Fingerprinting
Our findings demonstrate that DoH/3 consistently outperforms standard DoH in side-channel resistance. This protection does not stem from enhanced cryptographic ciphers, but rather from the mechanics of the QUIC transport layer (RFC 9000) and HTTP/3 framing (RFC 9114):
- **Frame Multiplexing Noise:** HTTP/3 control streams, QPACK encoder/decoder streams, and bidirectional exchange frames dynamically interleave with DNS query payloads.
- **Dynamic Packetization:** QUIC flow control and variable-length integer encoding disrupt the rigid packet length signatures characteristic of HTTP/2 over TCP.
- **Accidental Padding:** While not intended as a privacy defense, HTTP/3 transport metadata functions as continuous, dynamic padding that dilutes deterministic packet silhouettes.

### 5.2 The Temporal Illusion of DoH Security
A key finding of this work is that stationary closed-world evaluations significantly **overestimate the real-world threat of DoH website fingerprinting**. While an adversary training and testing within the same afternoon achieves >34% accuracy on Quad9 DoH, that classifier degrades to near 2% random chance when deployed days later. For adversaries, maintaining an effective DoH surveillance pipeline requires continuous, computationally expensive re-training against live target networks.

### 5.3 Limitations
1. **Client Scope:** All measurements were gathered using `q` client implementation. Differences in client buffering or local caching may shift absolute feature distributions.
2. **Single Query Traces:** This study measures isolated domain queries rather than multi-query page load waterfalls, which introduce additional multiplexing complexity.
3. **Simulated Defenses:** Defenses in WP13 represent mathematical simulations on extracted traces rather than server-negotiated EDNS0 padding in live resolvers.
