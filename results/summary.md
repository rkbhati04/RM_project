# Pilot results

## Dataset
| resolver | protocol | rows | domains | max_repeat |
| --- | --- | --- | --- | --- |
| adguard | doh | 135 | 50 | 2 |
| adguard | doh3 | 97 | 48 | 2 |
| adguard | doq | 92 | 46 | 2 |
| cloudflare | doh | 31 | 25 | 2 |
| cloudflare | doh3 | 148 | 50 | 2 |
| google | doh | 148 | 50 | 2 |
| google | doh3 | 150 | 50 | 2 |
| quad9 | doh | 397 | 50 | 7 |
| quad9 | doh3 | 398 | 50 | 7 |
| quad9 | doq | 398 | 50 | 7 |

## E1 Protocol identification
| task | model | n | majority_baseline | accuracy | acc_sd_over_seeds | macro_f1 |
| --- | --- | --- | --- | --- | --- | --- |
| 3-way DoH/DoH3/DoQ | rf | 1517 | 0.3507 | 0.9736 | 0.0023 | 0.973 |
| 3-way DoH/DoH3/DoQ | xgb | 1517 | 0.3507 | 0.9807 | 0.0011 | 0.9802 |
| DoH3 vs DoQ | rf | 985 | 0.5025 | 0.9601 | 0.0063 | 0.9601 |
| DoH3 vs DoQ | xgb | 985 | 0.5025 | 0.9665 | 0.0017 | 0.9665 |
| 3-way, Quad9 only | rf | 1193 | 0.3336 | 0.9955 | 0.0008 | 0.9955 |
| 3-way, Quad9 only | xgb | 1193 | 0.3336 | 0.9941 | 0.0014 | 0.9941 |
| 3-way, AdGuard only | rf | 324 | 0.4167 | 0.9064 | 0.0095 | 0.8928 |
| 3-way, AdGuard only | xgb | 324 | 0.4167 | 0.9043 | 0.0101 | 0.8908 |

## E2 Domain fingerprinting (one resolver at a time)
| resolver | protocol | n | n_domains | repeats_per_domain | chance_1_over_K | accuracy | ci95_lo | ci95_hi | top5 | macro_f1 | perm_mean | perm_p95 | p_value |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quad9 | doh | 397 | 50 | 7.9 | 0.02 | 0.3401 | 0.2952 | 0.388 | 0.6927 | 0.3363 | 0.0204 | 0.0354 | 0.0476 |
| quad9 | doh3 | 398 | 50 | 8.0 | 0.02 | 0.103 | 0.0768 | 0.1368 | 0.2714 | 0.0956 | 0.0167 | 0.0329 | 0.0476 |
| quad9 | doq | 398 | 50 | 8.0 | 0.02 | 0.2864 | 0.2442 | 0.3327 | 0.6131 | 0.2739 | 0.0158 | 0.0304 | 0.0476 |
| google | doh | 148 | 50 | 3.0 | 0.02 | 0.0676 | 0.0371 | 0.1199 | 0.2027 | 0.0568 | 0.0155 | 0.0405 | 0.0476 |
| google | doh3 | 150 | 50 | 3.0 | 0.02 | 0.0133 | 0.0037 | 0.0473 | 0.1333 | 0.0133 | 0.0187 | 0.0407 | 0.7143 |

## E2b Order / time control (is the fingerprint an artifact?)
| resolver | protocol | test | n | accuracy | ci95_lo | ci95_hi | chance | p_value |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quad9 | doh | (b) LORO within randomized repeats >= 4 | 198 | 0.2323 | 0.1789 | 0.2959 | 0.0134 | 0.0476 |
| quad9 | doh | (c) train repeats < 4, test randomized repeats >= 4 | 198 | 0.2525 | 0.1971 | 0.3174 | 0.02 |  |
| quad9 | doh3 | (b) LORO within randomized repeats >= 4 | 198 | 0.0758 | 0.0464 | 0.1212 | 0.0177 | 0.0476 |
| quad9 | doh3 | (c) train repeats < 4, test randomized repeats >= 4 | 198 | 0.0758 | 0.0464 | 0.1212 | 0.02 |  |
| quad9 | doq | (b) LORO within randomized repeats >= 4 | 198 | 0.1768 | 0.1299 | 0.2359 | 0.0146 | 0.0476 |
| quad9 | doq | (c) train repeats < 4, test randomized repeats >= 4 | 198 | 0.1869 | 0.1387 | 0.2469 | 0.02 |  |

## E3 Ablation
| task | setting | score | delta_vs_all |
| --- | --- | --- | --- |
| E1 protocol id (macro-F1) | all features | 0.9716 | 0.0 |
| E1 protocol id (macro-F1) | without volume | 0.9716 | -0.0 |
| E1 protocol id (macro-F1) | only volume | 0.9601 | -0.0115 |
| E1 protocol id (macro-F1) | without size_stats | 0.9642 | -0.0074 |
| E1 protocol id (macro-F1) | only size_stats | 0.9723 | 0.0006 |
| E1 protocol id (macro-F1) | without timing | 0.9736 | 0.002 |
| E1 protocol id (macro-F1) | only timing | 0.8655 | -0.1062 |
| E1 protocol id (macro-F1) | without bursts | 0.9689 | -0.0027 |
| E1 protocol id (macro-F1) | only bursts | 0.9446 | -0.027 |
| E1 protocol id (macro-F1) | without first20 | 0.9648 | -0.0068 |
| E1 protocol id (macro-F1) | only first20 | 0.9743 | 0.0027 |
| E2 fingerprinting quad9/doh (accuracy) | all features | 0.3401 | 0.0 |
| E2 fingerprinting quad9/doh (accuracy) | without volume | 0.2494 | -0.0907 |
| E2 fingerprinting quad9/doh (accuracy) | only volume | 0.3602 | 0.0201 |
| E2 fingerprinting quad9/doh (accuracy) | without size_stats | 0.267 | -0.0731 |
| E2 fingerprinting quad9/doh (accuracy) | only size_stats | 0.3804 | 0.0403 |
| E2 fingerprinting quad9/doh (accuracy) | without timing | 0.3401 | 0.0 |
| E2 fingerprinting quad9/doh (accuracy) | only timing | 0.0126 | -0.3275 |
| E2 fingerprinting quad9/doh (accuracy) | without bursts | 0.3678 | 0.0277 |
| E2 fingerprinting quad9/doh (accuracy) | only bursts | 0.1108 | -0.2293 |
| E2 fingerprinting quad9/doh (accuracy) | without first20 | 0.3526 | 0.0125 |
| E2 fingerprinting quad9/doh (accuracy) | only first20 | 0.2393 | -0.1008 |
| E2 fingerprinting quad9/doh3 (accuracy) | all features | 0.103 | 0.0 |
| E2 fingerprinting quad9/doh3 (accuracy) | without volume | 0.093 | -0.01 |
| E2 fingerprinting quad9/doh3 (accuracy) | only volume | 0.0955 | -0.0075 |
| E2 fingerprinting quad9/doh3 (accuracy) | without size_stats | 0.1005 | -0.0025 |
| E2 fingerprinting quad9/doh3 (accuracy) | only size_stats | 0.1131 | 0.0101 |
| E2 fingerprinting quad9/doh3 (accuracy) | without timing | 0.1131 | 0.0101 |
| E2 fingerprinting quad9/doh3 (accuracy) | only timing | 0.0477 | -0.0553 |
| E2 fingerprinting quad9/doh3 (accuracy) | without bursts | 0.1231 | 0.0201 |
| E2 fingerprinting quad9/doh3 (accuracy) | only bursts | 0.0452 | -0.0578 |
| E2 fingerprinting quad9/doh3 (accuracy) | without first20 | 0.108 | 0.005 |
| E2 fingerprinting quad9/doh3 (accuracy) | only first20 | 0.0879 | -0.0151 |
| E2 fingerprinting quad9/doq (accuracy) | all features | 0.2864 | 0.0 |
| E2 fingerprinting quad9/doq (accuracy) | without volume | 0.294 | 0.0076 |
| E2 fingerprinting quad9/doq (accuracy) | only volume | 0.191 | -0.0954 |
| E2 fingerprinting quad9/doq (accuracy) | without size_stats | 0.2563 | -0.0301 |
| E2 fingerprinting quad9/doq (accuracy) | only size_stats | 0.3216 | 0.0352 |
| E2 fingerprinting quad9/doq (accuracy) | without timing | 0.3015 | 0.0151 |
| E2 fingerprinting quad9/doq (accuracy) | only timing | 0.0402 | -0.2462 |
| E2 fingerprinting quad9/doq (accuracy) | without bursts | 0.2814 | -0.005 |
| E2 fingerprinting quad9/doq (accuracy) | only bursts | 0.0653 | -0.2211 |
| E2 fingerprinting quad9/doq (accuracy) | without first20 | 0.2462 | -0.0402 |
| E2 fingerprinting quad9/doq (accuracy) | only first20 | 0.2638 | -0.0226 |
| E2 fingerprinting google/doh (accuracy) | all features | 0.0676 | 0.0 |
| E2 fingerprinting google/doh (accuracy) | without volume | 0.0608 | -0.0068 |
| E2 fingerprinting google/doh (accuracy) | only volume | 0.0405 | -0.0271 |
| E2 fingerprinting google/doh (accuracy) | without size_stats | 0.0541 | -0.0135 |
| E2 fingerprinting google/doh (accuracy) | only size_stats | 0.027 | -0.0406 |
| E2 fingerprinting google/doh (accuracy) | without timing | 0.0608 | -0.0068 |
| E2 fingerprinting google/doh (accuracy) | only timing | 0.0338 | -0.0338 |
| E2 fingerprinting google/doh (accuracy) | without bursts | 0.0608 | -0.0068 |
| E2 fingerprinting google/doh (accuracy) | only bursts | 0.0541 | -0.0135 |
| E2 fingerprinting google/doh (accuracy) | without first20 | 0.0473 | -0.0203 |
| E2 fingerprinting google/doh (accuracy) | only first20 | 0.0405 | -0.0271 |

Top RF importances (E1):

| feature | importance |
| --- | --- |
| up_mean | 0.0976 |
| up_std | 0.0923 |
| bytes_up | 0.0842 |
| up_max | 0.0698 |
| down_max | 0.0611 |
| down_std | 0.0585 |
| n_pkts | 0.0568 |
| down_mean | 0.0536 |
| n_down | 0.0463 |
| bytes_total | 0.038 |

Importance by feature group: {'volume': 0.2925, 'size_stats': 0.4329, 'timing': 0.0193, 'bursts': 0.0594, 'first20': 0.196}

## E4 Cross-resolver
| train | test | task | model | n_test | accuracy | ci95 | macro_f1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adguard | quad9 | 3-way protocol id | rf | 1193 | 0.7904 | 0.766-0.813 | 0.7763 |
| adguard | quad9 | 3-way protocol id | xgb | 1193 | 0.7234 | 0.697-0.748 | 0.7125 |
| quad9 | adguard | 3-way protocol id | rf | 324 | 0.7068 | 0.655-0.754 | 0.5824 |
| quad9 | adguard | 3-way protocol id | xgb | 324 | 0.7068 | 0.655-0.754 | 0.5666 |
| adguard+quad9 | google | DoH vs DoH3 (unseen resolver) | rf | 298 | 0.9933 | 0.976-0.998 | 0.9933 |
| adguard+quad9 | google | DoH vs DoH3 (unseen resolver) | xgb | 298 | 1.0 | 0.987-1.000 | 1.0 |
| adguard+quad9 | cloudflare | DoH vs DoH3 (unseen resolver) | rf | 179 | 1.0 | 0.979-1.000 | 1.0 |
| adguard+quad9 | cloudflare | DoH vs DoH3 (unseen resolver) | xgb | 179 | 0.9609 | 0.921-0.981 | 0.9248 |

## E5 Workloads
| analysis | resolver | protocol | slice | n | accuracy | ci95_lo | ci95_hi | chance | p_value |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| workload classification (unseen domains) | quad9 | doh | global vs india | 397 | 0.4761 | 0.4274 | 0.5252 | 0.5013 |  |
| workload classification (unseen domains) | quad9 | doh3 | global vs india | 398 | 0.5226 | 0.4736 | 0.5712 | 0.5025 |  |
| workload classification (unseen domains) | quad9 | doq | global vs india | 398 | 0.4849 | 0.4362 | 0.5339 | 0.5025 |  |
| domain fingerprinting | quad9 | doh | global | 199 | 0.5075 | 0.4386 | 0.5762 | 0.0367 | 0.0909 |
| domain fingerprinting | quad9 | doh3 | global | 200 | 0.125 | 0.0861 | 0.178 | 0.038 | 0.0909 |
| domain fingerprinting | quad9 | doq | global | 200 | 0.385 | 0.3203 | 0.454 | 0.0395 | 0.0909 |
| domain fingerprinting | quad9 | doh | india | 198 | 0.4293 | 0.3623 | 0.4989 | 0.0444 | 0.0909 |
| domain fingerprinting | quad9 | doh3 | india | 198 | 0.1667 | 0.1212 | 0.2248 | 0.0434 | 0.0909 |
| domain fingerprinting | quad9 | doq | india | 198 | 0.3636 | 0.2998 | 0.4326 | 0.0298 | 0.0909 |

## How to read these tables
- **E1/E4/E5a** use unseen-domain or unseen-resolver test data. `majority_baseline`/`chance` is what a trivial classifier gets.
- **E2/E5b** accuracy is compared with `perm_mean` (accuracy when labels are shuffled) and `perm_p95`; a result counts as real leakage only if it clearly exceeds `perm_p95` (small `p_value`) and its 95% interval excludes the chance level.
- Accuracy *below* 1/K is noise, not evidence of extra privacy.
- Ablation deltas of about 1-2 points are within run-to-run noise; only large drops are meaningful.
