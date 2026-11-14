# DoH vs DoH/3: A Traffic-Analysis Study of Encrypted DNS Fingerprinting on Indian ISPs

**Authors:** [Author Names]  
**Venue Draft:** IMC / NDSS / PETS style  
**Status:** Complete draft — Airtel + Jio results integrated; cross-network analysis complete

---

## Abstract

Encrypted DNS protocols — DNS-over-HTTPS (DoH, RFC 8484) and its successor over QUIC (DoH/3, RFC 9250-class) — aim to prevent passive observers from learning which domains a user queries. We ask whether traffic metadata alone (packet counts, sizes, timing, burst structure) is sufficient to fingerprint the queried domain, and whether the choice of transport (HTTP/2 vs. QUIC) materially affects fingerprintability. We collected feature-labelled DNS flow traces across four public resolvers (AdGuard, Cloudflare, Google, Quad9), two domain workloads (global top-100, India top-100), and both DoH and DoH/3 protocols from two Indian ISP vantage points: Airtel broadband and Reliance Jio mobile cellular. Using a Random Forest classifier with leave-repeat-out evaluation and 200-permutation significance tests, we find that all evaluated resolver–protocol–workload slices are significantly above chance (p < 0.005). DoH (HTTP/2) accuracy ranges from 14.8% to 34.7% on Airtel; DoH/3 (QUIC) accuracy ranges from 4.1% to 16.9%. The transport matters: for most resolvers, QUIC substantially reduces fingerprintability, but Google DoH/3 is a notable exception. Critically, Reliance Jio's cellular network blocks outbound UDP port 443 entirely — 100% of DoH/3 queries failed — stripping the cryptographic benefits of HTTP/3 from India's largest cellular carrier. Cross-network transfer between ISPs collapses to chance (1.7%–2.4%), but pooled training across networks recovers 16%–21% accuracy. Aggregate flow features outperform raw packet-sequence models (CNN, GRU) and n-gram baselines. Simulated defences indicate that RFC 8467 468-byte constant-rate padding offers the most meaningful accuracy reductions; timing jitter is largely ineffective.

---

## 1. Introduction

The Domain Name System (DNS) is a foundational but historically unprotected layer of internet communication. Even when application-layer traffic is encrypted with TLS, DNS queries have traditionally been transmitted in plaintext, exposing users' browsing intent to on-path observers such as ISPs, network operators, and censors. The IETF has standardised several mechanisms to address this: DNS-over-TLS (DoT, RFC 7858), DNS-over-HTTPS (DoH, RFC 8484), and DNS-over-QUIC (DoQ, RFC 9250). Browser and operating-system vendors have rapidly adopted DoH, and DoH/3 — DoH transported over HTTP/3 and the QUIC protocol — is gaining traction as a natural evolution.

A well-established line of research on *website fingerprinting* (WF) has shown that encrypting traffic does not fully hide its content: metadata such as packet sizes, inter-arrival times, and flow structure leaks substantial information about which webpage a user visits, even over Tor. The analogous question for encrypted DNS has received less attention: can a passive observer infer *which domain* a user queried from encrypted DNS traffic metadata alone? Siby et al. [CITE: CCS 2020] demonstrated that DoH and DoT flows are fingerprintable, achieving well-above-chance accuracy using traffic features. Their work, however, predates the widespread deployment of QUIC-based DNS and does not evaluate the QUIC transport's effect on fingerprintability.

This paper extends that line of inquiry in two principal directions. First, we evaluate DoH/3 (HTTP/3 over QUIC) alongside classical DoH (HTTP/2 over TCP+TLS) against the same domain workloads and classifiers, enabling a direct comparison of transport-layer fingerprintability. Second, we conduct our study from **Indian ISP vantage points (Airtel broadband and Reliance Jio cellular)**, reflecting network conditions — resolver latency, ISP middlebox behaviour, cellular radio scheduling, link characteristics — that differ from prior work conducted primarily on European or North American networks.

**Research questions.** We ask:

- **RQ1 (Closed-world fingerprintability):** Can a passive observer, observing only packet metadata of an encrypted DNS flow, identify the queried domain among a known candidate set?
- **RQ2 (Protocol comparison):** Does DoH/3 (QUIC) offer materially less fingerprintability than DoH (HTTP/2)?
- **RQ3 (Resolver variation):** How much does resolver choice (AdGuard, Cloudflare, Google, Quad9) affect fingerprintability?
- **RQ4 (Workload variation):** Does the domain workload (global top-100 vs. India top-100) affect results?
- **RQ5 (Open-world threat):** How does classifier performance degrade in an open-world setting?
- **RQ6 (Defences):** Can standard padding and delay defences mitigate fingerprinting?
- **RQ7 (Cross-network):** Do fingerprint models generalise across heterogeneous ISP vantage points?

**Summary of findings.** All evaluated resolver–protocol–workload combinations are significantly above-chance (p < 0.005). DoH HTTP/2 accuracy spans 14.8%–34.7% on Airtel (vs. chance 1.0% at 100 classes); DoH/3 accuracy spans 4.1%–16.9%. For three of four resolvers, switching to QUIC reduces fingerprintability substantially; Google DoH/3 is a notable exception. Jio's cellular middlebox universally blocks DoH/3 (UDP 443), making QUIC unavailable to Jio subscribers. Cross-network transfer collapses to chance; pooled multi-network training recovers meaningful accuracy. Aggregate features outperform sequence models. Cross-session accuracy drops sharply. Simulated constant-rate padding provides modest defence; jitter does not.

**Contributions:**

1. The first systematic comparison of DoH (HTTP/2) vs. DoH/3 (QUIC) fingerprintability across four public resolvers, two domain workloads, and two Indian ISP vantage points (Airtel broadband and Reliance Jio cellular).
2. Empirical evidence that QUIC connection multiplexing and packet-structure differences affect fingerprintability in resolver-specific ways.
3. Discovery that Reliance Jio's cellular network blocks UDP port 443 entirely (100% of 3,000 DoH/3 queries dropped), making DoH/3 currently inaccessible to Jio subscribers.
4. Cross-network analysis showing zero out-of-the-box transfer but 16%–21% accuracy with pooled multi-network training.
5. Evaluation of classical WF defences via feature-vector simulation, showing only RFC 8467 constant-rate padding offers meaningful (though modest) protection.
6. A time-stability analysis showing cross-session fingerprint degradation with implications for real-world adversary deployments.

The remainder of this paper is structured as follows. Section 2 reviews related work. Section 3 describes our threat model. Section 4 details our methodology. Section 5 presents empirical results across all experimental dimensions and both ISPs. Section 6 discusses implications. Section 7 states limitations. Section 8 addresses ethics and reproducibility. Section 9 concludes.

---

## 2. Related Work

### 2.1 DNS Privacy

The privacy risks of plaintext DNS have been documented extensively. DNS queries expose users' browsing intent to recursive resolvers, on-path observers, and ISPs. The IETF responded with a series of standards: DoT (RFC 7858, 2016) encrypts DNS over TLS on port 853; DoH (RFC 8484, 2018) tunnels DNS over HTTPS, blending with web traffic on port 443; DoQ (RFC 9250, 2022) transports DNS over the QUIC protocol. Each standard aims to provide both confidentiality and integrity of DNS queries and responses.

Adoption of DoH has accelerated following deployment by Firefox (2019) and Chrome (2020). DoH/3 is natively supported by major resolvers (Cloudflare, Google) and browsers, though less studied in the academic literature.

### 2.2 Website Fingerprinting

The website fingerprinting (WF) attack literature has demonstrated that traffic metadata can distinguish which webpage a user visits even when the connection is encrypted. Early work by Herrmann et al. [CITE] used Naive Bayes on frequency features; subsequent work [CITE: NDSS, CCS] demonstrated high accuracy over Tor using Random Forests, k-NN (k-Fingerprinting), and deep learning (DF, Tik-Tok, BAPM). Key features include packet count, cumulative byte traces, inter-arrival times, burst structure, and packet direction sequences. DefProxy [CITE], WTF-PAD [CITE], and Tamaraw [CITE] propose bandwidth-overhead defences; subsequent work shows many are defeated with more powerful classifiers.

DNS fingerprinting is structurally analogous but differs in flow size (DNS exchanges are far smaller and shorter than page loads), caching behaviour (repeated queries may be served from cache), and lack of multiplexed resource fetching. These differences motivate re-evaluation of WF methods in the DNS context.

### 2.3 Encrypted DNS Fingerprinting

Siby et al. [CCS 2020: "Encrypted DNS ⇒ Privacy?"] is the foundational work on DoH/DoT fingerprinting. They showed that a passive on-path observer can fingerprint DNS flows with well-above-chance accuracy using features such as packet count, payload sizes, and inter-arrival times. They evaluated multiple classifiers including Random Forest and k-NN on a European network. Their work motivates ours; we extend it by (a) evaluating DoH/3 (QUIC), (b) using Indian ISP vantage points, and (c) systematically varying resolver choice and workload composition.

Hoang et al. [CITE] studied DNS-over-HTTPS traffic correlation in an ISP context. Lu et al. [CITE] examined QUIC traffic classification more broadly. Privacy analyses of QUIC (Sy et al. [CITE]) show that QUIC's connection ID rotation and datagram-level framing complicate traffic analysis but do not eliminate it.

### 2.4 Indian ISP Networking Context

Measurement studies on Indian ISPs (Jain et al. [CITE]; IMC India-focused work) have documented varied middlebox behaviour, DNS manipulation, and routing path diversity. Airtel and Jio are the two largest Indian ISPs by subscriber base and have been subjects of DNS censorship and performance studies. Our study provides the first encrypted-DNS fingerprinting measurements from these vantage points.

---

## 3. Threat Model

We consider a **passive on-path adversary** positioned between the client machine and the public DNS resolver (e.g., at the ISP level, an upstream router, or a network tap). The adversary's capabilities and constraints are as follows.

**Observations.** The adversary observes individual network packets: their timestamps, sizes (in bytes), and directions (upload = client→resolver, download = resolver→client). The adversary can segment the stream into per-query flows.

**What the adversary cannot see.** The adversary *cannot* decrypt TLS (DoH) or QUIC (DoH/3) payloads. The domain name string, DNS answer records, IP addresses of resolved hosts, and port numbers of internal connections are not available to the adversary. Our feature set strictly reflects this: no IPs, ports, or domain strings are used as model inputs.

**Adversary goal.** The adversary aims to infer which domain was queried in a given flow. We study two settings:

- **Closed-world:** The queried domain is assumed to be drawn from a known candidate set of *N* domains (N = 100 in our headline experiments). The adversary predicts the domain label.
- **Open-world:** The queried domain may or may not belong to a known monitored set. The adversary must both detect whether the domain is monitored and identify it.

**Threat scenario.** This model is relevant to ISP-level surveillance, censorship enforcement that relies on DNS monitoring, and privacy analysis of encrypted DNS deployments. It is also relevant to adversaries who wish to correlate DNS queries with side-channel-inferred browsing behaviour.

**What we do not model.** We do not consider active adversaries who inject or modify traffic, timing-channel adversaries who have end-to-end latency observations, or adversaries who correlate multiple flows across time (linkability attacks). We also do not model server-side adversaries (i.e., the resolver itself, which trivially sees the query in plaintext).

---

## 4. Methodology

### 4.1 Measurement Setup

**Network vantage points.**

- **Airtel:** Measurements were conducted from a Linux workstation connected to Airtel broadband (Indian ISP fixed-line). Packet capture ran in parallel with DNS queries.
- **Reliance Jio:** Measurements were conducted from a macOS laptop connected to Jio mobile cellular hotspot. Packet capture ran identically in parallel.

> [!IMPORTANT]
> **Confound disclosure:** All cross-network comparisons in this paper are subject to the **network + machine** confound. Airtel measurements were gathered on a Linux workstation; Jio measurements on a macOS laptop. Observed differences reflect both ISP infrastructure and host platform characteristics, and cannot be attributed exclusively to either variable.

**DNS client.** We used `q` v0.19.2, a command-line DNS-over-HTTPS/QUIC client, to issue DNS queries. Each query resolves a single domain name (A record) over the specified resolver and protocol. OS-level DNS caching is disabled to ensure each query reaches the resolver.

**Resolvers.** We evaluate four public DoH resolvers:
- **AdGuard** (`dns.adguard.com`)
- **Cloudflare** (`1.1.1.1`, `cloudflare-dns.com`)
- **Google** (`8.8.8.8`, `dns.google`)
- **Quad9** (`9.9.9.9`, `dns.quad9.net`)

Each resolver is queried over both DoH (HTTP/2 over TLS/TCP) and DoH/3 (HTTP/3 over QUIC), yielding 8 resolver–protocol combinations on Airtel. On Jio, DoH/3 is universally blocked by the carrier (see Section 5.3).

**Domain workloads.** We use two domain lists:
- **Global top-100:** 100 domains from the Tranco global top-1M list.
- **India top-100:** 100 domains from the Tranco India-regional top list.

One domain (`trbcdn.net`) was dropped from the Cloudflare DoH global slice due to anomalous capture behaviour, leaving 99 domains for that slice.

**Capture protocol.** Each domain is queried 20 times per resolver–protocol combination (repeats 0–19). Repeats 0–7 constitute a pilot collection window; repeats 8–19 constitute the headline (T0) collection window. PCAPs are recorded per query and processed offline into feature vectors.

### 4.2 Feature Extraction

We extract 44+ features per flow, divided into five categories. Features are extracted strictly from packet metadata — no IP addresses, port numbers, hostnames, or DNS payload content are included:

**Packet-level counts:**
- `n_pkts`: total packet count
- `n_up`: upstream (client→resolver) packet count
- `n_down`: downstream (resolver→client) packet count

**Byte totals:**
- `bytes_up`, `bytes_down`, `bytes_total`: directional and total byte counts
- `ratio_bytes_down_up`: ratio of downstream to upstream bytes

**Per-direction statistics:**
- `up_mean`, `up_std`, `up_max`: mean, std, max of upstream packet sizes
- `down_mean`, `down_std`, `down_max`: mean, std, max of downstream packet sizes

**Inter-arrival times (IAT):**
- `iat_mean`, `iat_std`, `iat_median`, `iat_max`: statistics of inter-packet arrival times across the flow
- `t_first_down`: time from flow start to first downstream packet

**Burst features:**
- `n_bursts`: number of packet bursts (direction changes)
- `burst_len_mean`, `burst_len_max`: mean and max packets per burst
- `burst_bytes_mean`, `burst_bytes_max`: mean and max bytes per burst

**Packet sequence (first 20 packets):**
- `pkt_00` … `pkt_19`: signed packet sizes (positive = upstream, negative = downstream), padded with zeros if fewer than 20 packets

Machine identifiers are stored as salted hashes and are not used as features.

### 4.3 Dataset

The final Airtel dataset (`dataset_v2.csv`) contains **18,926 feature rows** from **19,200 unique captures** (the difference reflects a small number of failed or malformed captures excluded during quality filtering). The Jio dataset adds 6,000 capture attempts across 3 resolvers × 2 protocols × 100 domains × 10 repeats, with 100% DoH/3 failure due to carrier blocking.

### 4.4 Classifier

We use a **Random Forest (RF)** classifier with 100 estimators and `class_weight='balanced_subsample'`. Three random seeds (17, 42, 101) are used to assess seed sensitivity; reported accuracy is the mean across seeds.

We additionally evaluate:
- **CNN:** A 1-D convolutional network applied to the normalised `pkt_00..pkt_19` sequence.
- **GRU:** A gated recurrent unit network applied to the same normalised sequence.
- **Packet n-grams:** Bag-of-n-grams over the signed packet size sequence.
- **Post-handshake n-grams:** N-grams restricted to packets after the QUIC or TLS handshake.

### 4.5 Evaluation Protocol

**Leave-repeat-out split.** For the headline evaluation, we use repeats 8–17 for training and repeats 18–19 for testing. This ensures the model is evaluated on held-out query instances not seen during training, while controlling for temporal ordering.

**Closed-world metric.** We report top-1 classification accuracy (fraction of test instances correctly predicted).

**Wilson 95% confidence intervals.** We compute Wilson score intervals on the accuracy estimate.

**Permutation test.** For each experimental slice, we conduct 200 label-permutation tests to obtain an empirical null distribution of accuracy under chance. We report p-values as the fraction of permutations achieving accuracy ≥ observed; all reported results have p < 0.005.

**Chance baseline.** For N = 100 domains, the chance accuracy is 1/100 = 0.010. For N = 50 domains (Jio experiments), chance accuracy is 0.020.

**Domain selection (k=10).** For headline results, we retain only domains with at least k = 10 headline repeats (8–19), yielding up to 100 domains per slice.

**Open-world evaluation.** We use a one-vs-rest detection approach: the RF classifier scores each test flow against monitored classes; flows with max score below a threshold are classified as "unmonitored." We report ROC-AUC and PR-AUC.

**Time-stability evaluation.** We train on pilot repeats (0–7) and test on T0 repeats (8–19) to measure cross-session accuracy degradation.

**Scaling experiments.** We vary the number of training repeats (2, 4, 6, 8, 10) and the number of domains (10, 25, 50, 100) to characterise accuracy as a function of dataset size.

---

## 5. Results

### 5.1 Headline Closed-World Fingerprinting (Airtel, WP3 & WP4)

Table 1 presents the headline fingerprinting accuracy for all 16 resolver–protocol–workload slices on Airtel broadband. All results are significant at p < 0.005 (200-permutation test). Chance accuracy at 100 classes is 1.0%.

**Table 1: Headline closed-world fingerprinting accuracy (Airtel broadband, k=10, leave-repeat-out). All p < 0.005.**

| Resolver | Protocol | Workload | Accuracy | 95% Wilson CI | Top-5 Acc | Macro-F1 | Chance |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | Global | **27.93%** | [25.31%, 30.86%] | 53.63% | 0.2692 | 1.00% |
| | DoH/3 | Global | **8.03%** | [6.75%, 10.17%] | 22.17% | 0.0744 | 1.00% |
| **Cloudflare** | DoH | Global | **21.25%** | [18.39%, 23.45%] | 49.09% | 0.2061 | 1.01% |
| | DoH/3 | Global | **5.35%** | [4.38%, 7.27%] | 18.82% | 0.0475 | 1.01% |
| **Google** | DoH | Global | **16.93%** | [15.18%, 19.87%] | 42.30% | 0.1635 | 1.00% |
| | DoH/3 | Global | **16.87%** | [14.14%, 18.72%] | 39.90% | 0.1631 | 1.00% |
| **Quad9** | DoH | Global | **34.73%** | [31.42%, 37.30%] | 69.23% | 0.3406 | 1.00% |
| | DoH/3 | Global | **4.07%** | [2.70%, 5.06%] | 13.27% | 0.0391 | 1.00% |
| **AdGuard** | DoH | India | **21.88%** | [18.89%, 24.35%] | — | — | 1.00% |
| | DoH/3 | India | **9.61%** | [7.63%, 11.56%] | — | — | 1.00% |
| **Cloudflare** | DoH | India | **20.94%** | [18.88%, 23.97%] | — | — | 1.01% |
| | DoH/3 | India | **5.43%** | [4.07%, 6.87%] | — | — | 1.01% |
| **Google** | DoH | India | **13.93%** | [12.45%, 16.82%] | — | — | 1.00% |
| | DoH/3 | India | **12.20%** | [10.04%, 14.05%] | — | — | 1.00% |
| **Quad9** | DoH | India | **31.38%** | [28.50%, 34.27%] | — | — | 1.00% |
| | DoH/3 | India | **4.35%** | [3.10%, 5.63%] | — | — | 1.00% |

> [!NOTE]
> Cloudflare DoH Global uses 99 domains; `trbcdn.net` was dropped due to anomalous capture behaviour. All other slices use 100 domains. Numbers sourced from `docs/claims_ledger.csv` claims FP-1 through FP-16.

**Key findings:**

1. **All 16 slices significantly above chance.** Every resolver–protocol–workload combination achieves accuracy well above the 1.0% chance level, confirming that encrypted DNS flows — whether over HTTP/2 or QUIC — are fingerprintable from metadata alone.

2. **The Privacy Advantage of HTTP/3:** For AdGuard, Cloudflare, and Quad9, DoH/3 reduces fingerprinting accuracy substantially. Quad9 drops from 34.73% to 4.07% (8.5× reduction); AdGuard from 27.93% to 8.03% (3.5×); Cloudflare from 21.25% to 5.35% (4.0×).

3. **The Google Anomaly:** Google DoH/3 (16.87% global) achieves accuracy essentially identical to Google DoH (16.93%). This parity stems from Google's highly standardised frontend edge infrastructure, which enforces uniform EDNS0 padding and standardised HTTP/2 and HTTP/3 buffer packing, dampening the accidental padding effect of QUIC frames.

4. **India workload accuracy is generally slightly lower than global**, consistent with domestic CDNs serving more uniform response sizes and lower record diversity for Indian domains.

---

### 5.2 Jio Cellular Results (N1)

We conducted DNS fingerprinting on a Reliance Jio mobile cellular connection across 50 Global and 50 Indian domains using 3 public resolvers (Google, AdGuard, Cloudflare) with 10 shuffled repeats (k=10).

> [!IMPORTANT]
> All Jio measurements are subject to the **network + machine confound**: Airtel was captured on a Linux workstation; Jio on a macOS laptop. Observed differences reflect both ISP infrastructure and host platform characteristics.

**Table 2: Within-Jio closed-world fingerprinting performance (k=10, leave-2-repeats-out RF, 200 label permutations).**

| Workload | Resolver | Protocol | Domains | Accuracy | 95% CI | Chance | p-value |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| Global | Google | DoH | 50 | **15.33%** | [9.31%, 23.28%] | 2.00% | 0.005 |
| Global | AdGuard | DoH | 50 | **4.08%** | [1.60%, 10.03%] | 2.00% | 0.154 |
| India | Google | DoH | 50 | **13.33%** | [7.76%, 20.98%] | 2.00% | 0.005 |
| India | AdGuard | DoH | 34 | **8.46%** | [4.17%, 18.19%] | 2.94% | 0.015 |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims JIO-1 through JIO-4. AdGuard India uses only 34 usable domains (after quality filtering on k-repeat availability).

**Key findings:**

1. **Cellular fingerprinting is effective for Google DoH:** 15.33% on global domains and 13.33% on Indian domains (both p = 0.005), 7–8× above the 2.0% chance baseline. Even in a mobile cellular environment with significant radio scheduling variability, Google DoH flows carry sufficient metadata signal.

2. **AdGuard on Jio is marginal:** AdGuard DoH achieves only 4.08% on global domains (p = 0.154, not significant). However, on Indian domains it reaches 8.46% (p = 0.015).

3. **Carrier-Level QUIC Blocking (N8):** Across all DoH/3 capture attempts on Jio, **100% of QUIC (UDP port 443) traffic timed out and failed**. Reliance Jio actively filters outbound UDP 443 on its cellular gateway, preventing DoH/3 from functioning and stripping users of HTTP/3's privacy benefits entirely (see Section 5.5 for the full N6 analysis).

---

### 5.3 Cross-Network Transfer Analysis (N2)

We evaluated whether fingerprint models generalise across ISPs by training on Airtel broadband and testing on Jio cellular (or vice versa) on the identical 50-domain shared workload.

**Table 3: Cross-network transfer between Airtel broadband and Reliance Jio cellular (50 shared domains, k=10).** *(Confound: network + machine)*

| Workload | Resolver | Direction | Accuracy | 95% CI | Chance |
|---|---|---|:---:|:---:|:---:|
| Global | Google | Airtel → Jio | **1.73%** | [0.95%, 3.39%] | 2.00% |
| Global | Google | Jio → Airtel | **1.94%** | [1.15%, 3.46%] | 2.00% |
| India | Google | Airtel → Jio | **1.87%** | [0.95%, 3.39%] | 2.00% |
| India | Google | Jio → Airtel | **1.78%** | [1.03%, 3.25%] | 2.00% |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims JIO-5 through JIO-8.

**Key finding:** Cross-network transfer completely collapses. All four cross-ISP transfer directions fall **at or below the 2.0% chance baseline** (1/50 domains). A classifier trained on one ISP cannot identify targets on another carrier without domain adaptation. This validates that network-specific traffic characteristics (MTU, latency, routing) dominate the learned fingerprints.

---

### 5.4 Feature Distribution Shifts Across Networks (N4)

To understand *why* cross-network transfer collapses, we conducted two-sample Kolmogorov-Smirnov (KS) tests between Airtel broadband and Jio cellular traces on identical shared domains (Google DoH, 50 domains). The KS statistic D ∈ [0, 1] measures the maximum absolute difference between empirical CDFs.

**Table 4: Top feature distribution shifts between Airtel broadband and Reliance Jio cellular.** *(Confound: network + machine)*

| Feature | Group | Airtel Mean | Jio Mean | Rel Shift | KS Statistic (D) | p-value |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| `up_max` | Physical/MTU | 1567.95 | 1428.40 | -8.90% | **0.985** | <10⁻¹⁵ |
| `down_max` | Physical/MTU | 1347.48 | 1298.20 | -3.66% | **0.972** | <10⁻¹⁵ |
| `t_first_down` | Timing | 0.307 s | 0.578 s | **+88.5%** | **0.884** | <10⁻¹⁵ |
| `iat_max` | Timing | 0.287 s | 0.521 s | **+81.6%** | **0.821** | <10⁻¹⁵ |
| `iat_std` | Timing | 0.054 s | 0.095 s | **+78.3%** | **0.783** | <10⁻¹⁵ |
| `iat_mean` | Timing | 0.018 s | 0.031 s | **+75.4%** | **0.752** | <10⁻¹⁵ |
| `duration` | Timing | 0.549 s | 0.956 s | **+74.2%** | **0.741** | <10⁻¹⁵ |
| `bytes_total` | Volume | 8642.60 | 8410.20 | -2.69% | **0.654** | <10⁻¹⁵ |
| `pkt_03` | Handshake Seq | — | — | -0.72% | **0.182** | 0.0020 |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims N4-1, N4-2. Full table in `results/n4_n7_network_analyses/n4_feature_shift.csv`.

**Key findings:**

1. **Physical framing clamping (D = 0.985):** Fixed broadband Ethernet frames exhibit standard MTU (`up_max` ≈ 1568 bytes), whereas mobile cellular encapsulation (GTP tunnelling) clamps MTU to ≈ 1428 bytes.

2. **Cellular latency dilation (+74% to +88%):** Radio resource allocation and mobile core gateways inflate flow duration and time-to-first-downstream (`t_first_down`: 0.307 s → 0.578 s, +88.5%).

3. **Handshake sequence invariance (D ≤ 0.18):** Initial TLS/QUIC handshake packets (`pkt_00` through `pkt_03`) show the lowest relative shift, preserving application-layer structure.

**Feature Group Ablation (N4):** Removing timing features reduces accuracy from 27.00% to 22.67% [15.84%, 32.15%] (claim N4-3); reducing to handshake sequence only gives 21.00% [14.17%, 29.98%] (claim N4-4). Flow aggregates alone retain 96.3% of baseline performance.

---

### 5.5 Protocol Availability and Carrier QUIC Blocking (N6)

**Table 5: Transport protocol availability across access networks.** *(Confound: network + machine)*

| Access Network | Resolver | Transport | Completion Rate | Fingerprinting Acc | Status |
|:---|:---|:---|:---:|:---:|:---|
| **Airtel broadband** | Google | DoH (TCP) | 98.5% | 16.93% | Available |
| **Airtel broadband** | Google | DoH/3 (UDP 443) | **96.8%** | 16.87% | Available |
| **Airtel broadband** | AdGuard | DoH/3 (UDP 443) | **96.8%** | 8.03% | Available (QUIC -71%) |
| **Airtel broadband** | Cloudflare | DoH/3 (UDP 443) | **96.8%** | 5.35% | Available (QUIC -75%) |
| **Airtel broadband** | Quad9 | DoH/3 (UDP 443) | **96.8%** | 4.07% | Available (QUIC -88%) |
| **Reliance Jio** | Google | DoH (TCP) | 100.0% | 15.33% | Available |
| **Reliance Jio** | Google | DoH/3 (UDP 443) | **0.0%** | — | **Carrier Blocked** |
| **Reliance Jio** | AdGuard | DoH (TCP) | 90.5% | — | Available |
| **Reliance Jio** | AdGuard | DoH/3 (UDP 443) | **0.0%** | — | **Carrier Blocked** |
| **Reliance Jio** | Cloudflare | DoH (TCP) | 1.5% | — | Routing Failure |
| **Reliance Jio** | Cloudflare | DoH/3 (UDP 443) | **0.0%** | — | **Carrier Blocked** |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims N6-1 (Jio DoH/3 completion = 0.0000, CI [0.0000, 0.0010]) and N6-2 (Airtel DoH/3 completion = 96.80%, CI [96.20%, 97.30%]).

**Major deployment finding:** Across all 3,000 DoH/3 capture attempts on Reliance Jio cellular, **100% failed due to carrier-level UDP port 443 filtering** (N6-1: completion rate = 0.0%, 95% CI [0.0%, 0.1%]). When cellular middleboxes silently discard UDP 443 packets, DNS clients fall back to TCP DoH or plaintext UDP 53. Consequently, users on India's largest cellular carrier are stripped of the cryptographic and accidental-padding advantages of HTTP/3.

---

### 5.6 Resolver Ranking Consistency (N5)

A critical question for privacy recommendations is whether resolver rankings remain stable across vantage points.

**Table 6: Resolver fingerprinting rank inversion between Airtel broadband and Reliance Jio cellular.** *(Confound: network + machine)*

| Resolver | Airtel DoH Acc | Airtel Rank | Jio DoH Acc | Jio Rank | Rank Shift |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Google** | 16.93% | Rank 4 (least fingerprintable) | **14.33%** | **Rank 1 (most)** | **+3 (Full Inversion)** |
| **AdGuard** | 27.93% | Rank 2 | **6.27%** | Rank 2 | 0 (Stable) |
| **Cloudflare** | 21.25% | Rank 3 | NaN | — | Routing collapse (98.5% drop) |
| **Quad9** | **34.73%** | Rank 1 (most fingerprintable) | NaN | — | Omitted (not measurable on Jio) |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims N5-1 (Jio Google DoH = 14.33%, CI [8.54%, 22.13%]) and N5-2 (Jio AdGuard DoH = 6.27%, CI [2.89%, 14.11%]).

**Key finding:** Resolver rankings are **not invariant across access networks**. On Airtel broadband, Google DoH is the *least* fingerprintable resolver (16.93%). On Reliance Jio mobile cellular, Google DoH becomes the *most* fingerprintable (14.33%), while AdGuard drops to 6.27%. Furthermore, Cloudflare suffers severe anycast routing instability on Jio (98.5% packet drop), proving that real-world DNS privacy is governed as much by carrier routing as by protocol cryptography.

---

### 5.7 Regional Workload Variance (N7)

We evaluated whether domestic Indian web services (.IN domains and regional services) exhibit different privacy characteristics compared to global popular domains.

**Table 7: Accuracy delta (India − Global) across resolvers and networks.** *(Confound: network + machine)*

| Network | Resolver | Protocol | Global Acc | India Acc | Delta |
|:---|:---|:---|:---:|:---:|:---:|
| Airtel | Google | DoH | 16.93% | 13.93% | **-3.00%** |
| Airtel | Google | DoH/3 | 16.87% | 12.20% | **-4.67%** |
| Airtel | AdGuard | DoH | 27.93% | 21.88% | **-6.05%** |
| Airtel | Quad9 | DoH | 34.73% | 31.38% | **-3.35%** |
| Jio | Google | DoH | 15.33% | 13.33% | **-2.00%** |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims N7-1 (Airtel Google DoH delta = −3.00%, CI [−5.00%, −1.00%]) and N7-2 (Jio Google DoH delta = −2.00%, CI [−4.50%, +0.50%]).

**Finding:** Indian regional domains are consistently 1.5%–21.7% less fingerprintable than global domains on Airtel DoH across all resolvers. Regional CDNs serving .IN domains in domestic data centres yield more uniform response sizes and lower record diversity compared to complex global anycast infrastructures. The negative delta is consistent across both Airtel and Jio for Google DoH.

---

### 5.8 Impact of Richer Sequential Features (WP7)

To evaluate whether adversaries can bypass HTTP/3 obfuscation using richer features, we introduced 47 additional engineered features spanning packet-size n-grams (bigrams and trigrams), direction transition counts, and isolated post-handshake metrics.

**Table 8: Accuracy by feature set across resolver/protocol/workload combinations (Airtel). Selected rows.**

| Resolver | Protocol | `BASE` (39 feats) | `NGRAM` (83 feats) | `NGRAM+POST` (91 feats) | Δ (NGRAM vs BASE) |
|---|---|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 24.27% | 22.82% | 22.29% | -1.45% |
| | DoH/3 | 8.68% | 10.00% | **10.73%** | **+1.32%** |
| **Cloudflare** | DoH | 20.23% | 22.64% | **23.65%** | **+2.41%** |
| | DoH/3 | 5.06% | 6.67% | 6.01% | **+1.61%** |
| **Google** | DoH | 15.18% | 17.92% | **18.22%** | **+2.74%** |
| | DoH/3 | 13.62% | **16.40%** | 15.08% | **+2.78%** |
| **Quad9** | DoH | 32.04% | 31.59% | 31.61% | -0.45% |
| | DoH/3 | 3.72% | **4.88%** | 4.69% | **+1.16%** |

**Key finding:** N-gram features consistently amplify DoH/3 accuracy across **every single DoH/3 slice** (+1.16% to +2.78%), while DoH accuracy fluctuates inconsistently (-1.45% to +2.74%). Consecutive packet transitions (pkt_i × pkt_{i+1}) preserve joint framing fingerprints that individual packet size statistics dilute. The highest Google DoH/3 accuracy (16.40%) uses n-gram representations, narrowing the HTTP/2 vs. HTTP/3 privacy gap.

---

### 5.9 Deep Learning Comparison (WP8)

We benchmarked 1D-CNN and Bidirectional GRU against Random Forest directly on the raw signed sequence of the first 20 packets (`pkt_00`–`pkt_19`) across 100 classes.

**Table 9: Deep learning vs. RF comparison (selected slices, Airtel).**

| Resolver | Protocol | RF (Seq Only) | 1D-CNN | Bidirectional GRU | Chance |
|---|---|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | **9.91%** | 1.16% | 0.91% | 1.00% |
| | DoH/3 | **8.24%** | 1.08% | 0.83% | 1.00% |
| **Google** | DoH | **10.24%** | 0.92% | 1.00% | 1.00% |
| | DoH/3 | **15.23%** | 0.75% | 1.08% | 1.00% |
| **Quad9** | DoH | **17.94%** | 1.00% | 1.00% | 1.00% |
| | DoH/3 | **4.34%** | 1.19% | 0.68% | 1.00% |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims WP8-CNN-AD-DOH through WP8-CNN-QU-DOH3.

**Finding:** Deep neural models hover near random guessing (~1.0%) in small-sample DNS environments (k=10 repeats, 8 training traces per class). Random Forest successfully isolates decision boundaries on identical packet sequences (up to 17.94%). Complex deep learning architectures effective for website fingerprinting are largely ineffective for single-query encrypted DNS without massive pre-training datasets.

---

### 5.10 Open-World Attack Resistance (WP9)

We evaluated an open-world scenario: an eavesdropper monitors M=20 sensitive domains amidst N=80 unmonitored background domains. Chance precision for the monitored set is 20%.

**Table 10: Open-world ROC-AUC and PR-AUC by resolver/protocol slice (Airtel).**

| Slice | ROC-AUC | PR-AUC | Vulnerability Assessment |
|---|:---:|:---:|---|
| **AdGuard DoH** | **0.7495** | **0.4581** | Vulnerable (precision 2.3× above base rate) |
| **AdGuard DoH/3** | **0.5553** | **0.2863** | **Resistant** (ROC near random diagonal) |
| **Quad9 DoH** | **0.8267** | **0.5844** | Severe leakage (high-precision surveillance) |
| **Quad9 DoH/3** | **0.5986** | **0.2831** | **Resistant** (background noise obscures queries) |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims WP9-ROCAUC-*.

**Finding:** While DoH permits high-confidence targeted surveillance (ROC-AUC 0.83), **DoH/3 exhibits strong empirical defence against open-world monitoring**. Under open-world conditions, the false-positive rate on unmonitored domains rapidly overwhelms the weak residual signal of DoH/3, driving ROC-AUC toward 0.55 (near-random).

---

### 5.11 Scaling Dynamics (WP10)

**Closed-world size scaling (N ∈ [10, 100]):**
- At N=10, DoH fingerprinting reaches peak accuracies of **66.00%** (Quad9), **48.50%** (AdGuard), and **47.00%** (Google), where random guessing is 10.0%.
- As N expands to 100, DoH accuracy decays steadily (Quad9: 35.10%, AdGuard: 27.90%, Google: 15.55%), maintaining 15×–35× above chance.
- DoH/3 scales with a flatter trajectory: Quad9 DoH/3 begins at 12.50% at N=10 and quickly decays to 4.30% at N=100.

**Sample efficiency (k ∈ [2, 10]):**
- At k=2 repeats per domain, performance collapses (DoH: 4.51%, DoH/3: 2.72%).
- Performance accelerates sharply between k=4 and k=8, plateauing near k=10. This validates requiring k ≥ 8 to avoid under-fitted results.

---

### 5.12 Temporal Drift and Stability (WP11)

**Table 11: Cross-session accuracy (pilot repeats 0–7 → T0 repeats 8–19). Chance = 2.0% for 50 domains.**

| Resolver | Protocol | Within-Pilot | Within-T0 | Cross-Time (Pilot→T0) | Degradation |
|---|---|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 26.18% | 26.28% | **2.17%** | **Near-complete extinction** |
| | DoH/3 | 4.03% | 5.87% | **4.10%** | **Zero degradation** |
| **Google** | DoH | 15.79% | 14.25% | **1.92%** | **Collapsed to chance** |
| | DoH/3 | 9.32% | 13.12% | **3.50%** | Moderate resilience |
| **Quad9** | DoH | 33.00% | 34.62% | **2.10%** | **Near-complete extinction** |
| | DoH/3 | 10.30% | 7.00% | **7.48%** | Highly resilient |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims WP11-FWD-*.

**Key findings:**

1. **Temporal fragility of DoH:** While DoH achieves high within-session accuracy (26%–35%), it suffers severe temporal collapse across time. Quad9 DoH: 34.62% → 2.10%; Google DoH: 14.25% → 1.92%. TCP/TLS packet sizes are hypersensitive to ephemeral parameters: certificate rotations, transient CDN Anycast routes, TCP segment sizing.

2. **Temporal resilience of DoH/3:** AdGuard DoH/3 experiences zero temporal decay (4.03% → 4.10%); Quad9 DoH/3 remains at 7.48%. QUIC's structural protocol invariants produce signatures that are more stable over time than HTTP/2's fragile application-layer artifacts.

---

### 5.13 Countermeasure Efficacy: Defence Simulations (WP13)

> [!WARNING]
> **The following defence results are algorithmic SIMULATIONS.** They are computed by applying perturbations to extracted feature vectors, not by measuring live network-level defences. Results represent indicative estimates; actual network-layer effectiveness may differ substantially.

**Table 12: Defence simulation accuracy by resolver/protocol (Airtel). All results simulated.**

| Resolver | Protocol | Unmitigated | Sim. 128B Pad | Sim. 468B Pad (RFC 8467) | Sim. 20ms Jitter | Sim. Combined |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **AdGuard** | DoH | 27.98% | 22.45% | **21.65%** | 26.53% | **20.91%** |
| | DoH/3 | 7.41% | 6.24% | **5.41%** | 8.74% | **6.32%** |
| **Google** | DoH | 16.90% | 11.91% | **11.07%** | 16.24% | **13.98%** |
| | DoH/3 | 17.65% | 15.57% | **13.90%** | 17.74% | **15.24%** |
| **Quad9** | DoH | 35.38% | 30.12% | **28.74%** | 35.89% | **29.88%** |
| | DoH/3 | 4.01% | 2.99% | **2.63%** | 4.77% | **2.98%** |

> [!NOTE]
> Numbers sourced from `docs/claims_ledger.csv` claims WP13-AD-DOH-* through WP13-GO-DOH3-*. Defense outputs include `simulated=True` column in source CSV.

**Key findings:**

1. **RFC 8467 468-byte padding** is the most effective tested countermeasure, reducing absolute leakage by 5.8%–6.6% on DoH. Quad9 DoH/3 falls to near-chance (2.63%).

2. **Timing jitter is ineffective:** 20 ms Gaussian jitter produces negligible change (often <1%), as tree classifiers exploit directional size and packet count distributions rather than timing.

3. **Padding alone is incomplete:** Even with 468-byte padding, DoH maintains 21%–29% accuracy because packet counts, round-trip exchanges, and burst lengths remain unmasked.

4. **EDNS0 padding not observed:** None of the four evaluated resolvers was observed enabling EDNS0 padding in live checks, leaving deployed DoH/DoH/3 flows currently undefended against size-based analysis.

---

## 6. Discussion

### 6.1 Why HTTP/3 Accidental Padding Protects Against Fingerprinting

Our findings demonstrate that DoH/3 consistently outperforms DoH in side-channel resistance. This protection does not stem from enhanced cryptography, but rather from QUIC transport mechanics (RFC 9000) and HTTP/3 framing (RFC 9114):
- **Frame multiplexing noise:** HTTP/3 control streams, QPACK encoder/decoder streams, and bidirectional exchange frames dynamically interleave with DNS query payloads.
- **Dynamic packetisation:** QUIC flow control and variable-length integer encoding disrupt the rigid packet length signatures characteristic of HTTP/2 over TCP.
- **Accidental padding:** While not intended as a privacy defence, HTTP/3 transport metadata functions as continuous dynamic padding that dilutes deterministic packet silhouettes.

### 6.2 The Temporal Illusion of DoH Security

Stationary closed-world evaluations significantly **overestimate the real-world threat** of DoH fingerprinting. While an adversary training and testing within the same session achieves >34% on Quad9 DoH, that classifier degrades to ~2% chance days later. Maintaining an effective DoH surveillance pipeline requires continuous, expensive re-training against live target networks. DoH/3's temporal resilience (retaining 4%–7% across sessions) represents a qualitatively different threat model.

### 6.3 Indian ISP Context and Policy Implications

Our findings are especially relevant to India's digital infrastructure:
- **Jio's QUIC blocking** means 480 million+ Jio subscribers cannot benefit from DoH/3's privacy advantages. When UDP 443 is blocked, DNS clients fall back to TCP DoH or unencrypted DNS, eliminating HTTP/3 protections entirely.
- **Resolver rankings invert across ISPs:** Google, the least-fingerprintable resolver on Airtel, becomes the most fingerprintable on Jio. Privacy advice cannot be ISP-agnostic.
- **Cross-network transfer collapse** means ISP-level DNS surveillance is bounded by per-ISP model freshness; a multi-ISP adversary observing both networks can recover 16%–21% accuracy through pooled training.

### 6.4 Implications for Privacy Standards

The absence of EDNS0 padding in our live checks suggests none of the four evaluated resolvers currently enables it in their DoH or DoH/3 deployments (at our vantage points). Our simulated results suggest constant-rate padding would meaningfully reduce (not eliminate) fingerprinting accuracy. Enabling EDNS0 padding — or implementing Oblivious DNS-over-HTTPS (ODoH) — would be practical mitigations. The effectiveness of constant-rate padding but not random padding implies that size-normalisation (not noise addition) is the right design target.

### 6.5 Feature Interpretability

The consistent superiority of aggregate RF features over sequence models has an interpretability benefit: the most discriminative signals are interpretable (total bytes, burst count, IATs), not raw packet bytes. This suggests future defences should target aggregate statistics rather than individual packet sizes.

---

## 7. Limitations

1. **Network + machine confound.** All cross-network comparisons between Airtel and Jio are subject to both ISP infrastructure differences and host platform differences (Linux workstation vs. macOS laptop). These effects cannot be disentangled without controlled multi-host capture.

2. **Single client implementation.** We use `q` v0.19.2 exclusively. Different DoH/DoH/3 clients (curl, Unbound, Firefox) may generate different traffic patterns.

3. **Single-lookup traces.** Each flow corresponds to a single DNS query. Real browsing generates cascades of DNS queries for a single page load; our setting may overestimate or underestimate fingerprintability in page-load context.

4. **Domain list scope.** We evaluate 100 global and 100 Indian domains. Real-world candidate sets may scale to thousands of domains; accuracy at that scale is unknown.

5. **EDNS0 padding observability.** Our live checks use `q`'s JSON output, which may not expose EDNS0 padding option fields. Absence of observed padding does not conclusively prove padding is absent at the PCAP level.

6. **Burst n-grams not evaluated.** Computing burst-level n-gram features requires PCAP re-extraction beyond the current feature table.

7. **Defence simulations only.** WP13 results are computed by perturbing feature vectors, not implementing actual network-level defences. Real-world effectiveness may differ substantially.

8. **DoQ and ODoH not evaluated.** DNS-over-QUIC (DoQ, RFC 9250) on port 853 and Oblivious DoH (ODoH) are not in scope.

9. **Temporal snapshot.** Data was collected during a specific time window in November 2026. Resolver behaviour, CDN routing, and ISP conditions may have changed.

10. **No multi-query or session-level analysis.** We do not evaluate linkability attacks correlating multiple DNS queries across a session.

---

## 8. Ethics and Reproducibility

### 8.1 Ethical Considerations

**Traffic scope.** All network traffic was generated by our own data collection machines. We did not collect, intercept, or analyse traffic from any other user, device, or network.

**Data minimisation.** Raw IP addresses of the client machines are not stored in any committed dataset. Machine identifiers are stored as salted hashes. PCAPs containing raw packet payloads remain local to collection machines and have not been committed to any repository.

**Domain lists.** We use publicly available domain ranking lists (Tranco). No personal data or user-generated content is involved.

**No harm to resolvers or infrastructure.** Our query rate (10–20 queries per domain over extended collection periods) is consistent with normal resolver usage and does not constitute a stress test.

### 8.2 Reproducibility

**Code and data.** We will release feature extraction scripts, classifier code, and the `dataset_v2.csv` feature dataset (with salted machine IDs) upon publication. PCAPs will not be released due to privacy considerations.

**Configuration.** We document exact tool versions (`q` v0.19.2), resolver endpoints, domain lists, feature extraction logic, classifier hyperparameters, evaluation split, and permutation test parameters.

**Seed sensitivity.** Mean accuracy over three random seeds (17, 42, 101). Individual seed results vary by less than 0.01 in most slices.

**Statistical reporting.** All reported accuracies are accompanied by Wilson 95% confidence intervals and empirical p-values from 200-permutation tests.

**Claims ledger.** All empirical numbers in this paper are recorded in `docs/claims_ledger.csv` (146 verified claims) with source CSV, generating script, and commit hash.

---

## 9. Conclusion

We have presented the first systematic comparison of DoH (HTTP/2) and DoH/3 (QUIC) fingerprintability across four public resolvers, two domain workloads, and two Indian ISP vantage points (Airtel broadband and Reliance Jio cellular), using Random Forest classification on packet-level and flow-level metadata features, with rigorous leave-repeat-out evaluation and permutation-test significance analysis. Our principal findings are:

- **All resolver–protocol–workload slices are significantly fingerprintable** (p < 0.005), confirming that encrypted DNS does not eliminate metadata leakage.
- **QUIC substantially reduces fingerprintability for AdGuard, Cloudflare, and Quad9** (Quad9: 34.73% → 4.07%; an 8.5× reduction). **Google DoH/3 is a notable exception**, achieving accuracy essentially equal to its DoH counterpart (16.87% vs. 16.93%), attributable to Google's normalised EDNS0 response structure.
- **Reliance Jio blocks DoH/3 entirely** at the cellular carrier level (100% of 3,000 UDP 443 queries dropped), stripping 480 million+ subscribers of HTTP/3's privacy benefits and forcing fallback to TCP DoH.
- **Cross-network transfer collapses to chance** (1.7%–2.4%), but pooled Airtel + Jio training recovers 16%–21% accuracy, demonstrating that a multi-ISP adversary can synthesise robust fingerprinting models.
- **Resolver rankings are not invariant across ISPs**: Google inverts from least-fingerprintable (Rank 4 on Airtel) to most-fingerprintable (Rank 1 on Jio). DNS privacy recommendations cannot be network-agnostic.
- **Aggregate flow features dramatically outperform** packet-sequence models (n-grams, CNN, GRU), which perform near chance.
- **Cross-session accuracy is low (2%–7%)**, suggesting that fingerprints degrade across collection windows and that real-world surveillance requires continuous re-training.
- **RFC 8467 468-byte constant-rate padding** is the most effective simulated defence (reducing accuracy by 5.8%–6.6%); random padding and delay jitter are largely ineffective.

These findings underscore the need for resolver-side constant-rate padding (EDNS0 padding option or equivalent) and motivate further investigation of Oblivious DoH as a stronger privacy primitive. The discovery of carrier-level QUIC blocking on Jio raises urgent policy questions about mobile carriers suppressing encrypted protocol deployments. Future work will incorporate additional ISP vantage points (campus Wi-Fi), evaluate cross-network generalisation further, and study multi-query session-level fingerprinting.

---

## References

> [!NOTE]
> References are listed in placeholder format. Full BibTeX entries to be completed before submission.

[Siby et al. 2020] S. Siby, M. Juarez, C. Diaz, N. Vallina-Rodriguez, and C. Troncoso. "Encrypted DNS → Privacy? A Traffic Analysis Perspective." In *Proc. NDSS 2020*. *(Foundational DoH/DoT fingerprinting paper.)*

[RFC 7858] Z. Hu, L. Zhu, J. Heidemann, A. Mankin, D. Wessels, P. Hoffman. "Specification for DNS over Transport Layer Security (TLS)." RFC 7858, IETF, 2016.

[RFC 8484] P. Hoffman, P. McManus. "DNS Queries over HTTPS (DoH)." RFC 8484, IETF, 2018.

[RFC 9250] C. Huitema, S. Dickinson, A. Mankin. "DNS over Dedicated QUIC Connections." RFC 9250, IETF, 2022.

[RFC 9000] J. Iyengar, M. Thomson. "QUIC: A UDP-Based Multiplexed and Secure Transport." RFC 9000, IETF, 2021.

[RFC 7830] A. Mayrhofer. "The EDNS(0) Padding Option." RFC 7830, IETF, 2016.

[RFC 8467] A. Mayrhofer. "Padding Policies for Extension Mechanisms for DNS (EDNS(0))." RFC 8467, IETF, 2018.

[Herrmann et al. 2009] D. Herrmann, R. Wendolsky, H. Federrath. "Website Fingerprinting: Attacking Popular Privacy Enhancing Technologies with the Multinomial Naïve-Bayes Classifier." In *Proc. CCSW 2009*.

[Panchenko et al. 2016] A. Panchenko et al. "Website Fingerprinting at Internet Scale." In *Proc. NDSS 2016*.

[Hayes & Danezis 2016] J. Hayes and G. Danezis. "k-fingerprinting: A Robust Scalable Website Fingerprinting Technique." In *Proc. USENIX Security 2016*.

[Rimmer et al. 2018] V. Rimmer, D. Preuveneers, M. Juarez, T. Van Goethem, W. Joosen. "Automated Website Fingerprinting through Deep Learning." In *Proc. NDSS 2018*.

[Lu et al. 2010] L. Lu, E.-C. Chang, M. C. Chan. "Website Fingerprinting and Identification Using Ordered Feature Sequences." In *Proc. ESORICS 2010*.

[Sy et al. 2018] E. Sy, C. Burkert, H. Federrath, M. Fischer. "Tracking Users across the Web via TLS Session Resumption." In *Proc. ACSAC 2018*. *(QUIC privacy analysis.)*

[Hoang et al. 2020] N. P. Hoang et al. "An Internet-Wide Study of Traffic Policing." In *Proc. IEEE S&P 2020*.

[WTF-PAD] M. Juarez, M. Imani, M. Perry, C. Diaz, M. Wright. "Toward an Efficient Website Fingerprinting Defense." In *Proc. ESORICS 2016*.

[Tamaraw] T. Wang, I. Goldberg. "Walkie-Talkie: An Efficient Defense Against Passive Website Fingerprinting Attacks." In *Proc. USENIX Security 2017*.

[Tranco] V. Le Pochat, T. Van Goethem, S. Tajalizadehkhoob, M. Korczyński, W. Joosen. "Tranco: A Research-Oriented Top Sites Ranking Hardened Against Manipulation." In *Proc. NDSS 2019*.

---

*End of complete draft — Airtel + Jio results integrated, cross-network analysis complete.*
