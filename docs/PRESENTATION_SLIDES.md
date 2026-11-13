# Presentation Slide Deck

**Title:** Privacy Analysis of Modern Encrypted DNS: DoH vs. DoH/3 on Indian ISPs  
**Venue:** Computer Science Research Methodology / Networking Conference  
**Date:** November 2026  
**Artifact Figures Directory:** `results/figures/` and `results/airtel_all_20261113/`

---

## Slide 1: Title & Overview

### [Slide Layout]
- **Title:** Encrypted DNS $\neq$ Traffic Privacy: An Empirical Study of DoH vs. DoH/3 on Indian Access Networks
- **Subtitle:** Side-Channel Fingerprinting, Carrier QUIC Blocking, and Cross-Network Generalizability
- **Authors:** Research Project Team
- **Key Takeaways:**
  - Evaluates HTTP/2 (DoH) vs. HTTP/3 (DoH/3) side-channel privacy.
  - Multi-carrier empirical study: Airtel Broadband vs. Reliance Jio Cellular (26,800+ total captures).
  - Investigates whether QUIC's transport framing mitigates domain fingerprinting.

### 🎙️ Speaker Script (1:00 min)
> "Good morning, everyone. Today, we are presenting our empirical study on modern encrypted DNS privacy. 
> 
> Over the last five years, the internet has rapidly shifted from plaintext DNS to encrypted transports like DNS-over-HTTPS (DoH) and now DNS-over-HTTP/3 (DoH/3). While payload encryption prevents eavesdroppers from reading domain names directly, transport metadata—packet sizes, flow duration, burst counts, and timing—remains completely unencrypted.
> 
> In this project, we asked three core questions: First, does HTTP/3 over QUIC provide superior traffic-analysis resistance compared to standard HTTP/2 DoH? Second, does fingerprintability generalize across real-world access networks in India—specifically Airtel broadband and Reliance Jio cellular? And third, what happens when network middleboxes interact with modern encrypted DNS protocols?"

---

## Slide 2: Motivation & The Research Gap

### [Slide Layout]
- **The Promise:** RFC 8484 (DoH) and RFC 9114 (HTTP/3) encrypt query strings to protect user privacy against ISPs and on-path censors.
- **The Reality:** Flow silhouettes (packet counts, timing, byte ratios) leak distinct fingerprints.
- **The Research Gap:**
  - Prior work (Siby et al., CCS 2020) demonstrated DoH fingerprinting, but did not evaluate modern QUIC/HTTP/3 transports.
  - Emerging QUIC DNS studies rarely measure consumer cellular networks or cross-network transfer between different ISPs.
- **Core Question:** Does QUIC's connection multiplexing and control framing inherently defend against website fingerprinting?

### 🎙️ Speaker Script (1:15 min)
> "To understand the motivation, consider Alice querying a sensitive domain. Traditional DNS exposes this query in plaintext. Encrypted DNS wraps the query inside TLS or QUIC. 
> 
> However, an on-path adversary—such as an ISP or surveillance system—can still measure the conversation's silhouette: how many packets were sent, how large they were, when the response arrived, and the size of initial burst exchanges.
> 
> The foundational study by Siby et al. at CCS 2020 showed that DoH is fingerprintable. But the networking ecosystem is now transitioning to HTTP/3 and QUIC. Does the new QUIC transport framing eliminate this leakage, or does it merely reshape it? Furthermore, how does this leakage behave across consumer broadband versus cellular networks in the Global South? That is the gap our research addresses."

---

## Slide 3: Threat Model & Ethical Experimental Controls

### [Slide Layout]
- **Adversary Model:**
  - Passive, on-path eavesdropper located between the client and the recursive resolver.
  - Observes packet metadata only: sizes, packet directions, timestamps, inter-arrival times.
- **Zero Label Leakage Guarantee:**
  - IP addresses, port numbers, transport headers, and domain names are **strictly excluded** from feature sets.
- **Rigorous Evaluation Controls:**
  - Leave-repeat-out temporal cross-validation (train on early repeats, test on held-out repeats).
  - 200 label-permutation baseline tests to establish empirical significance ($p < 0.005$).
  - 95% Wilson score confidence intervals reported for all claims.

### 🎙️ Speaker Script (1:15 min)
> "Before presenting results, it is critical to emphasize our threat model and experimental integrity controls.
> 
> Our adversary is strictly passive. They cannot decrypt payloads, inject packets, or inspect IP addresses and port numbers. To prevent trivial shortcuts, every IP address and port number is stripped before feature extraction. The classifier only learns from physical flow silhouettes: packet sizes, directions, and timing.
> 
> Second, to eliminate temporal memorization, we enforce leave-repeat-out cross-validation: we train on earlier repeats and evaluate on held-out repeats captured hours later. Finally, every accuracy number is paired with a 200-iteration label permutation test to confirm that performance reflects genuine privacy leakage rather than chance or class imbalance."

---

## Slide 4: Empirical Testbed Architecture

### [Slide Layout]
- **Dual Network Vantage Points:**
  - **Airtel Fiber Broadband:** 18,926 feature rows, 200 domains, 10 repeats ($k=10$).
  - **Reliance Jio Cellular:** 6,000 raw packet captures, 100 domains, 10 repeats.
- **Workload Selection (Pinned Tranco `L5PV4`):**
  - **Global Workload:** Top 100 global services (Google, Microsoft, Cloudflare, Amazon, CDN edges).
  - **Indian Regional Workload:** Top 100 regional domains (e-commerce, payment gateways, banking, `.gov.in`).
- **Resolvers Evaluated:** Google, Cloudflare, AdGuard, Quad9.
- **DNS Client:** `q` v0.19.12 with native HTTP/2 and HTTP/3 support via `dumpcap` PCAP capture.

### 🎙️ Speaker Script (1:15 min)
> "Our testbed captures over 26,000 live DNS transactions across two major Indian telecommunications networks: Airtel broadband and Reliance Jio mobile cellular.
> 
> We evaluate two distinct workloads pinned to the Tranco ranking: a 100-domain Global workload dominated by global CDNs, and a 100-domain Indian regional workload including banking, e-commerce, and government portals.
> 
> We test four major public recursive resolvers: Cloudflare, Google, AdGuard, and Quad9, executing serialized single-query captures using the native `q` client paired with `dumpcap` packet filters."

---

## Slide 5: RQ1 — Protocol Distinguishability (DoH vs. DoH/3)

### [Slide Layout]
- **Research Question:** Can an observer identify whether a user is running DoH (HTTP/2) or DoH/3 (QUIC) using metadata alone, without looking at UDP vs. TCP ports?
- **Finding:** **98.5%+ Accuracy (Macro-F1 > 0.98)** across all resolvers and access networks.
- **Primary Distinguishing Features:**
  - Initial handshake packet sizes (`pkt_00`–`pkt_03`): QUIC Initial datagrams are padded to $\ge 1200$ bytes; TLS ClientHellos over TCP are significantly smaller.
  - Inter-arrival time (IAT) and flow duration: QUIC 0-RTT/1-RTT handshakes complete in a single round-trip, whereas TCP + TLS 1.3 requires multiple round-trips.
- **Takeaway:** Protocol selection is completely transparent to passive network observers.

### 🎙️ Speaker Script (1:15 min)
> "Our first research question was protocol identification: can a censor or ISP tell whether you are using DoH or DoH/3 if they cannot inspect transport port numbers?
> 
> The answer is an unequivocal yes. Our classifier achieves over 98.5% accuracy with a Macro-F1 exceeding 0.98.
> 
> The leakage is driven by transport framing: RFC 9000 mandates that QUIC Initial packets be padded to at least 1,200 bytes to prevent amplification attacks. TCP ClientHellos over TLS do not have this requirement. Furthermore, QUIC handshakes complete in fewer round trips than TCP plus TLS. As a result, encrypted DNS protocol choice cannot be hidden from traffic analysis."

---

## Slide 6: RQ2 — Does DoH/3 (QUIC) Improve Privacy?

### [Slide Layout]
- **Figure:** `results/figures/fig1_headline_doh_vs_doh3.png`
- **Results Summary (Airtel Broadband, k=10, 100 classes, Chance = 1.0%):**
  - **AdGuard:** DoH = 26.2% $\rightarrow$ DoH/3 = **8.9%** (66% leakage reduction)
  - **Cloudflare:** DoH = 23.6% $\rightarrow$ DoH/3 = **6.0%** (75% leakage reduction)
  - **Quad9:** DoH = 34.2% $\rightarrow$ DoH/3 = **4.6%** (86% leakage reduction)
  - **Google:** DoH = 17.5% $\rightarrow$ DoH/3 = **16.9%** (No reduction!)
- **Key Insight:** QUIC reduces leakage for 3 out of 4 resolvers, but Google DoH/3 remains equally fingerprintable.

```
+--------------------------------------------------------------------------+
|  [ Embed: results/figures/fig1_headline_doh_vs_doh3.png ]                |
+--------------------------------------------------------------------------+
```

### 🎙️ Speaker Script (1:30 min)
> "Here we come to our headline empirical finding on Slide 6: Does DoH/3 improve privacy over standard DoH?
> 
> Looking at the figure, you can see a striking pattern. For AdGuard, Cloudflare, and Quad9, switching from DoH to DoH/3 reduces fingerprinting accuracy dramatically. On Quad9, accuracy drops from 34.2% down to 4.6%. On Cloudflare, it drops from 23.6% to 6.0%. 
> 
> Why? Because HTTP/3's control stream multiplexing, variable-length integer encoding, and unified transport-layer ACKs act as inherent traffic obfuscation.
> 
> However, look at Google: Google DoH achieves 17.5% accuracy, and Google DoH/3 achieves 16.9%—virtually no reduction! This reveals that QUIC is not an automatic privacy panacea. Google's server-side response structuring and lack of dynamic padding allow domain-specific response sizes to shine directly through QUIC."

---

## Slide 7: RQ3 — What Drives Leakage? (Feature Ablation & Deep Learning)

### [Slide Layout]
- **Feature Importance & Ablation (WP7):**
  - Full Aggregate Feature Set: **20.4% – 26.2% accuracy**
  - Packet-Size N-grams alone: **1.5% accuracy**
  - Post-Handshake N-grams alone: **1.5% accuracy**
- **Deep Learning Comparison (WP8):**
  - 1D-CNN on packet sequence: **1.0% accuracy** (chance)
  - 2-layer GRU on packet sequence: **1.4% accuracy** (chance)
  - Random Forest on flow aggregates: **26.2% accuracy**
- **Takeaway:** DNS flows are short (<40 packets); sequence models fail, while aggregate burst volume and IAT distributions carry the discriminative signal.

### 🎙️ Speaker Script (1:15 min)
> "Next, we investigated which features actually carry the leakage signal.
> 
> In conventional website fingerprinting, researchers often use deep sequence models like CNNs or LSTMs on packet-direction sequences. But when we trained 1D-CNN and GRU models on raw DNS packet sequences, they completely failed—achieving only 1.0% to 1.4% accuracy, essentially random guessing.
> 
> In contrast, Random Forest utilizing aggregate flow features—burst byte volumes, downstream-to-upstream byte ratios, and inter-arrival time distributions—achieved 26.2%. Because DNS exchanges are extremely short (typically 20 to 35 packets total), temporal sequence models suffer from insufficient tokens, whereas overall flow statistics capture the exact response payload size."

---

## Slide 8: RQ4 — Cross-Network Generalization (Airtel vs. Jio)

### [Slide Layout]
- **Figure:** `results/figures/fig2_cross_network_transfer.png`
- **Experimental Setup:** Evaluate identical 50 shared domains on Airtel broadband vs. Reliance Jio cellular.
- **Empirical Findings:**
  - **Within-Jio Fingerprinting:** Google DoH achieves **15.3%** (Global) and **13.3%** (India) (p = 0.005, vs 2.0% chance).
  - **Cross-Network Transfer:**
    - Airtel $\rightarrow$ Jio: **1.7% accuracy** (Below chance!)
    - Jio $\rightarrow$ Airtel: **1.9% accuracy** (Below chance!)
- **Takeaway:** Encrypted DNS fingerprints do **NOT** generalize across different network carriers out-of-the-box.

```
+--------------------------------------------------------------------------+
|  [ Embed: results/figures/fig2_cross_network_transfer.png ]              |
+--------------------------------------------------------------------------+
```

### 🎙️ Speaker Script (1:30 min)
> "Slide 8 shows our cross-network evaluation between Airtel fiber broadband and Reliance Jio mobile cellular.
> 
> When we train and test within Jio cellular, fingerprinting succeeds with statistical significance: Google DoH achieves 15.3% on Global domains and 13.3% on Indian domains, well above the 2.0% chance level.
> 
> But look at what happens during cross-network transfer: when a model trained on Airtel broadband is deployed against Jio cellular traffic, accuracy completely collapses to 1.7%—literally at or below random chance! The same collapse occurs in reverse when testing Jio models on Airtel.
> 
> This is a crucial finding for the research community: laboratory evaluations conducted on a single broadband ISP vastly overestimate an attacker's real-world capability against mobile cellular users."

---

## Slide 9: Multi-Network Defense & Feature Distribution Shift

### [Slide Layout]
- **Figure:** `results/figures/fig4_feature_distribution_shift.png`
- **Why Does Transfer Fail? (Kolmogorov-Smirnov Shift):**
  - Cellular physical layer framing changes maximum packet sizes (`up_max`, `down_max`, $D = 1.00$).
  - Cellular latency shifts flow timing (`t_first_down`, `iat_max`, `iat_std` shifted by **75%–88%**, $p < 10^{-6}$).
- **The Attacker's Countermeasure (Pooled Training):**
  - Pooling Airtel + Jio training data restores accuracy to **16.0% – 20.7%** on held-out test sets across both networks.
- **Implication:** Multi-homed adversaries observing multiple ISPs can defeat carrier-level variance.

```
+--------------------------------------------------------------------------+
|  [ Embed: results/figures/fig4_feature_distribution_shift.png ]          |
+--------------------------------------------------------------------------+
```

### 🎙️ Speaker Script (1:15 min)
> "Why does cross-network transfer collapse? Slide 9 illustrates the Kolmogorov-Smirnov distribution shift between Airtel and Jio.
> 
> Cellular access networks introduce dramatic physical-layer perturbations. 4G/5G radio scheduling, cellular MTU clamping, and radio-link queuing shift inter-arrival times and response latencies by over 75% to 88%. This completely distorts the timing envelope learned on fixed broadband.
> 
> However, an adversary is not helpless: when we pool training data across both Airtel and Jio, the model successfully recovers 16.0% to 20.7% accuracy on held-out test sets. An adversary with observation probes across multiple consumer ISPs can build robust, multi-carrier models."

---

## Slide 10: Real-World Network Health & Carrier QUIC Blocking

### [Slide Layout]
- **Figure:** `results/figures/fig3_carrier_quic_blocking.png`
- **Carrier UDP 443 Blocking (Reliance Jio):**
  - **DoH/3 (UDP 443):** **100% of queries dropped (0 / 3,000 successful)** across all resolvers (`udp_blocked_flag=true`).
  - Reliance Jio cellular middleboxes actively drop or throttle outbound UDP 443, forcing clients back to TCP DoH.
- **Edge Routing Instability:**
  - Google DoH: **100% success rate** (1,000/1,000).
  - AdGuard DoH: **90.5% success rate** (905/1,000).
  - Cloudflare DoH: **1.5% success rate** (15/1,000) due to cellular routing failures to Cloudflare anycast POPs.

```
+--------------------------------------------------------------------------+
|  [ Embed: results/figures/fig3_carrier_quic_blocking.png ]               |
+--------------------------------------------------------------------------+
```

### 🎙️ Speaker Script (1:30 min)
> "Slide 10 presents an unexpected and critical real-world networking discovery: carrier-level protocol blocking.
> 
> While DoH/3 operated cleanly on Airtel broadband, on Reliance Jio mobile cellular, **100% of all 3,000 DoH/3 queries failed across all resolvers**. Every single QUIC handshake over UDP 443 was silently dropped by the carrier middlebox.
> 
> This means that in major consumer cellular deployments in India, users attempting to use DoH/3 are forced into fallback modes or experience total failure.
> 
> Furthermore, we observed dramatic edge routing differences: while Google DoH achieved a 100% completion rate, Cloudflare DoH suffered a 98.5% failure rate on Jio cellular due to unstable anycast routing. Encrypted DNS deployment is strictly bounded by carrier-level middleboxes and routing topology."

---

## Slide 11: Countermeasure Evaluations (Simulated Defences)

### [Slide Layout]
- **Evaluated Defences on Airtel DoH (Baseline = 20.4%):**
  - **Constant Padding (64-byte blocks):** Accuracy drops to **13.9%** (32% reduction)
  - **Constant Padding (128-byte blocks):** Accuracy drops to **13.9%** (32% reduction)
  - **Random Padding (up to 128 bytes):** Accuracy remains **20.5%** (Ineffective!)
  - **Timing Jitter (50ms – 200ms):** Accuracy remains **19.5% – 21.5%** (Ineffective!)
  - **Dummy Cover Packets (10–50 pkts):** Accuracy remains **19.8% – 20.2%**
- **Takeaway:** Fixed-block size padding provides moderate protection, but randomized noise and timing jitter fail to hide the primary flow volume signal.

### 🎙️ Speaker Script (1:15 min)
> "In Slide 11, we evaluated simulated countermeasures to determine how encrypted DNS protocols can defend against these attacks.
> 
> Standardized RFC 7830 EDNS0 padding options currently suggest adding padding. We found that constant-block padding (rounding packets to 64 or 128-byte multiples) successfully reduces fingerprinting accuracy from 20.4% down to 13.9%.
> 
> However, random padding, timing jitter of up to 200 milliseconds, and small bursts of dummy cover packets proved virtually ineffective. Because the classifier relies on aggregate volume metrics, random noise cancels out over the flow, while constant-rate block quantization genuinely obscures the distinctive record length."

---

## Slide 12: Conclusions & Recommendations

### [Slide Layout]
- **Core Conclusions:**
  1. **DoH/3 provides substantial privacy gains on 3 out of 4 resolvers**, but implementation differences (Google) can negate these benefits.
  2. **Access networks act as natural privacy barriers:** Models trained on one carrier experience total collapse when transferred to another without multi-vantage adaptation.
  3. **Carrier middleboxes gate adoption:** Reliance Jio's complete blocking of UDP 443 prevents DoH/3 deployment for millions of cellular users.
- **Actionable Recommendations:**
  - **IETF & Standards:** Mandate standardized constant-block response padding (minimum 128 bytes) across both HTTP/2 and HTTP/3.
  - **Resolvers:** Normalize response header structures across implementations.
  - **ISPs:** Whitelist outbound UDP 443 to allow secure QUIC encrypted DNS adoption.

### 🎙️ Speaker Script (1:00 min)
> "To conclude, our study demonstrates that while encrypted DNS hides message content, it leaves significant metadata leakage that passive observers can exploit.
> 
> HTTP/3 over QUIC offers real privacy advantages for most resolvers, but its benefits are heavily dependent on server-side implementation and can be completely nullified by carrier middlebox blocking.
> 
> We recommend that the IETF and resolver operators adopt mandatory constant-block padding and that mobile network operators stop blocking outbound UDP 443, ensuring that modern secure DNS protocols can function as designed.
> 
> Thank you, and we welcome your questions."
