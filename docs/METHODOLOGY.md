# Methodology

The adversary is passive and observes one fresh encrypted-DNS lookup at a time. The client issues A-record queries through `q`; packet captures are transformed into packet-size, direction, timing, burst, and early-packet features. IP addresses, ports, domain strings, and labels are excluded from model features.

Evaluation uses five grouped folds with two repeats held out per fold, exactly k repeats per retained domain, multiple configured seeds, Wilson intervals, and matched empirical permutation p-values. Random-forest fits use 100 trees for observed results and 50 trees for null permutations; each fit is single-threaded and fits are parallelized across tasks. A non-significant result is reported as no detectable leakage at the available sample size. Resolver rankings require a significant paired comparison.

Each manifest row records only a salted `machine_id` token derived from the
operator-supplied machine label; the hostname is never stored. Comparisons on
the same machine are reported as within-machine comparisons. Results that
cross both network and machine boundaries are labelled **network + machine**,
not as pure network effects.

The capture driver requests q JSON output and includes the response's EDNS0 OPT section when available. `padding_present` is `true` only when q exposes a padding option, `false` when an exposed OPT section contains no padding option, and `unknown` when q's JSON does not expose enough response detail. This is a measurement limitation, not an assumption that padding is absent.

Limitations: one client implementation, single-lookup traces rather than page loads, a small domain set, Airtel-only data at present, and a domain list dominated by infrastructure names.
