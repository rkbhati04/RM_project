# Live q checks

Status: **complete on 2026-11-13**.

The eight required `google.com` checks were run serially with q 0.19.12.
Raw outputs are stored locally under `docs/live_checks/`:

| Resolver | HTTP/2 | HTTP/3 | Answer-count parity | CNAMEs | EDNS0 padding option |
| --- | ---: | ---: | --- | --- | --- |
| AdGuard | 1 | 1 | Match | None | Not exposed |
| Cloudflare | 6 | 6 | Match | None | Not exposed |
| Google | 6 | 1 | Mismatch | None | Not exposed |
| Quad9 | 6 | 6 | Match | None | Not exposed |

All queries completed successfully. The Google answer-count mismatch is a
single live observation and is not evidence of a protocol effect: resolver
answer selection and cache state can vary. TTLs and returned IP addresses also
varied between queries. The response OPT sections exposed EDNS0 but no padding
option in any of the eight outputs, so `padding_present` is **not observed** in
this check. This does not prove that padding is absent from every query.

Required follow-up, one query at a time:

```powershell
q google.com A @https://dns.adguard-dns.com/dns-query --opt --http2 --format=json > docs/live_checks/adguard_http2.json
q google.com A @https://dns.adguard-dns.com/dns-query --opt --http3 --format=json > docs/live_checks/adguard_http3.json
```

Repeat the two commands for `cloudflare-dns.com`, `dns.google`, and
`dns.quad9.net`, pausing between commands. Compare answer, CNAME, query
contents, extra record types, and response OPT options. Packet-size multiples
are not evidence of EDNS0 padding.
