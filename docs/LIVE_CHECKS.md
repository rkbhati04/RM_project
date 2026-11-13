# Live q checks

Status: **blocked on 2026-11-10**.

The capture machine was quiet and the overnight run was complete, but the
installed `q` executable was not available on `PATH` and no `q.exe` was found
in the repository. Therefore the eight required `google.com` checks (four
resolvers x HTTP/2 and HTTP/3) were not run, and no raw JSON files were
created.

Required follow-up, one query at a time:

```powershell
q google.com A @https://dns.adguard-dns.com/dns-query --opt --http2 --format=json > docs/live_checks/adguard_http2.json
q google.com A @https://dns.adguard-dns.com/dns-query --opt --http3 --format=json > docs/live_checks/adguard_http3.json
```

Repeat the two commands for `cloudflare-dns.com`, `dns.google`, and
`dns.quad9.net`, pausing between commands. Compare answer, CNAME, query
contents, extra record types, and response OPT options. Until those files are
available, `padding_present` remains `unknown`; packet-size multiples are not
evidence of EDNS0 padding.
