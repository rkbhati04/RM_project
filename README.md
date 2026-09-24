# Privacy Analysis of Modern Encrypted DNS

This workspace supports an empirical study of privacy leakage in DNS-over-QUIC
(DoQ) and DNS-over-HTTPS/3 (DoH/3). The question is not whether DNS payloads
are encrypted; it is whether an observer can still infer queried domains from
encrypted traffic metadata such as packet size, timing, burst structure, and
flow direction.

## Research questions

- **RQ1:** Can DoQ and DoH/3 queries be distinguished using encrypted traffic metadata?
- **RQ2:** How do their traffic-analysis risks compare?
- **RQ3:** Which features contribute most to metadata leakage?
- **RQ4:** Does leakage vary by public resolver and access network?
- **RQ5:** Do Global and Indian DNS workloads differ in leakage?

The project scope and expected results are transcribed from `Project_topic.png`.
The supplied papers are background evidence, not experiment results.

## Workspace

| Path | Purpose |
| --- | --- |
| `data/raw/` | Captured PCAP/PCAPNG files; never commit these. |
| `data/processed/` | Extracted, labelled feature tables. |
| `notebooks/` | Exploratory analysis and model reports. |
| `src/` | Reusable capture, extraction, and modelling code. |
| `results/` | Figures, tables, and model outputs. |
| `docs/` | Protocol, experiment, and reporting plans. |

## Environment

The virtual environment is `.venv` (Python 3.11). Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
$env:MPLCONFIGDIR = "$PWD\.matplotlib"
```

Install reproducibly on another machine:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`MPLCONFIGDIR` keeps Matplotlib's cache within the project, avoiding Windows
profile permission issues.

## Today's target

Follow [the 50-percent action plan](docs/ACTION_PLAN.md). Do not begin broad,
unlabelled browsing captures: the first useful dataset requires one query label,
one PCAP, and a recorded protocol/resolver/network configuration for every run.

