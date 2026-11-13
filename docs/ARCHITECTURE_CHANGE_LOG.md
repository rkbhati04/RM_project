# Architecture and Code Change Log

This document records the recent architecture and implementation changes made
to the capture, validation, and analysis pipeline. Each entry states the
problem, the reason for the solution, the affected code, and the verification
performed.

## Current architecture

The project is split into four operational layers:

1. **Workload definition** — frozen domain lists under `data/workloads/`.
2. **Capture** — `src/probe_and_capture.py` invokes `q` and `dumpcap`, writes
   one manifest row and one PCAP per query, and records query metadata.
3. **Validation and status** — `src/encdns/cli.py` and
   `src/data_status.py` summarize smoke and collection health.
4. **Feature extraction and analysis** — `src/extract_features.py` converts
   successful captures into `data/processed/dataset.csv`; analysis modules
   consume the processed dataset and configured repeat windows.

The overnight collection boundary is now a fifth explicit concern: each
overnight run owns a separate directory containing its own manifest and PCAPs.
Historical capture files are not used as write targets.

## Change index

| Change | Problem addressed | Main implementation |
|---|---|---|
| Reproducible capture workflow | Collection needed stable workloads, repeat ordering, and cross-platform wrappers | `5dd4bf8` |
| Frozen workload expansion | The experiment needed the intended 100 Global and 100 India domains | `ec1a44c` |
| Manifest and capture safety | Schema drift and malformed rows could silently corrupt later runs | `c2005b1` |
| Supported q JSON output | The installed q version did not support the previously assumed JSON flag | `40929b3` |
| Smoke metadata hardening | Smoke rows could be marked successful with missing DNS metadata | `26b5d6a` |
| Windows q discovery | q installed under the standard Windows Q directory was not found through PATH | `1e2ffc1` |
| Complete smoke planning | A limited smoke command planned only one domain instead of both smoke domains | `7ae4925` |
| q response parsing | q v0.19.12 nests records and headers in `replies[].answer[].hdr` | `436e4b0`, `8934910`, `0cc613a` |
| Nonpositive TTL rejection | A zero or negative TTL could pass metadata validation | `3377125` |
| Analysis repeat policy | Pilot repeats could enter headline results and balancing collapsed to the smallest domain | `ddd4720` |
| Overnight run isolation | New collection could append to or overwrite historical data | Current worktree patch |
| Mandatory manifest migration and privacy sanitization | A legacy manifest could receive rows under the wrong schema or retain a raw public IP | Current worktree patch |

## Detailed changes

### 1. Reproducible capture workflow

**Problem:** Collection needed a repeatable protocol across Windows, macOS, and
Linux, with explicit resolver/protocol combinations and reproducible ordering.

**Solution:** The capture driver became the single query-level orchestration
point. It supports explicit interface, network, batch, workload, resolver,
protocol, repeat, shuffle, resume, and tool-path arguments. The shell and
PowerShell wrappers use the same capture driver and retry only at the wrapper
level.

**Affected code:** `src/probe_and_capture.py`,
`scripts/run_overnight.ps1`, `scripts/run_overnight.sh`, and the capture
runbook.

**Reasoning:** Keeping capture behavior in one driver prevents the two platform
wrappers from implementing different experimental behavior. Repeats remain the
outer loop, and deterministic per-repeat shuffling prevents a domain from
always occupying the same position in a pass.

**Verification:** The overnight configuration plans 19,200 jobs:
100 Global + 100 India domains × 4 resolvers × 2 protocols × 12 repeats.

### 2. Frozen workload expansion

**Problem:** The earlier workload was smaller than the intended experiment.

**Solution:** The frozen workload lists were expanded to 100 Global and 100
India domains and treated as committed experiment inputs rather than generated
at capture time.

**Affected code:** `data/workloads/global.txt`, `data/workloads/india.txt`,
workload metadata, and the project documentation.

**Reasoning:** A committed workload makes later capture and analysis runs
reproducible and prevents domain-list drift from changing the experiment.

### 3. Manifest and capture safety

**Problem:** Manifest schema changes and malformed row lengths could make
downstream CSV reads unreliable.

**Solution:** The driver migrates the manifest header to the supported
28-column schema, including salted `machine_id`, validates that every row has the same number of columns, and
rejects an unsupported header before appending new data.

**Affected code:** `src/probe_and_capture.py`, especially manifest migration
and validation helpers.

**Reasoning:** Failing before capture is safer than appending rows to a
partially migrated or malformed file.

**Verification:** The smoke verification found a single manifest row length:
`{28}`.

### 4. q structured-output compatibility

**Problem:** The installed q client did not support the assumed `--json`
option. This caused query failures with a nonzero return code.

**Solution:** The driver runs `q --help`, detects the advertised structured
output capability, and uses q's supported `--format=json` flag automatically.

**Affected code:** `detect_q_json_flag()` and q command construction in
`src/probe_and_capture.py`.

**Reasoning:** Capability detection is safer than hard-coding a flag that
varies by q release. The installed Windows q version was identified as
0.19.12.

### 5. Public-IP privacy handling

**Problem:** A raw public IP would identify the collection network and should
not be written to the manifest.

**Solution:** The driver looks up the public IP once at run start, validates
it, and stores only a salted truncated SHA-256 token in `public_ip`. If lookup
fails, it logs a warning and stores an empty value rather than a guessed or
raw value.

**Affected code:** `fetch_public_ip()` and `anonymize_public_ip()` in
`src/probe_and_capture.py`.

**Reasoning:** One lookup avoids repeated external requests, while hashing
preserves the ability to correlate rows from the same run without retaining
the sensitive address.

### 6. q DNS metadata parsing and status classification

**Problem:** Successful q processes were initially producing incomplete
`answer_count`, `cname_count`, and `ttl_min` values. A transport success could
therefore be mistaken for a valid DNS result.

**Solution:** The parser accepts q's JSON structure, including nested
`replies[].answer[]` records and `hdr.rrtype`/`hdr.ttl` fields. It counts
answers and CNAMEs, computes the minimum positive TTL, and classifies rows
with missing or zero answers, or nonpositive TTLs, as `bad_metadata` rather
than `ok`.

**Affected code:** `parse_q_json()` and status selection in
`src/probe_and_capture.py`; fixtures and tests under `tests/fixtures/` and
`tests/test_q_metadata.py`.

**Reasoning:** Metadata validation belongs at the capture boundary so invalid
rows cannot silently enter the analysis dataset. The parser supports A
records, CNAME chains, empty answers, numeric TTLs, duration-form TTLs, and
q's nested record headers.

**Verification:** The focused q metadata test suite passed with 9 tests.

### 7. Padding observability

**Problem:** A default `false` value would falsely claim that EDNS0 response
padding was absent when q did not expose enough response-option detail.

**Solution:** Padding is reported as `true` only when the response output
contains recognizable padding evidence, `false` when an exposed OPT response
proves no padding, and `unknown` when q output is insufficient.

**Affected code:** `parse_q_json()`, `tests/test_q_metadata.py`, fixtures, and
`docs/METHODOLOGY.md`.

**Reasoning:** `unknown` distinguishes “not observable” from “not present” and
prevents a measurement limitation from becoming a false experimental result.

### 8. Smoke planning and compact smoke-check

**Problem:** The smoke command could plan only one limited domain, and repeated
smoke attempts accumulated in the shared manifest, making raw row counts
misleading.

**Solution:** Smoke mode expands a limited workload to all requested limited
domains and rejects any plan other than exactly 16 jobs. `smoke-check` selects
the latest row per PCAP path and prints status counts, answer counts, TTLs,
hash presence, padding values, median latency, cutoff drops, and a final
GO/NO-GO decision.

**Affected code:** Smoke planning in `src/probe_and_capture.py` and smoke
commands in `src/encdns/cli.py`.

**Reasoning:** The plan check catches an incorrectly scoped smoke command
before network work starts. Latest-per-PCAP reporting avoids treating stale
retries as additional effective smoke observations.

**Verification:** The latest smoke run produced 16 effective rows, all 2/2 per
resolver/protocol, with no latency over the 1.5-second cutoff and a GO result.

### 9. Analysis repeat-window and target-k policy

**Problem:** Pilot repeats 0–7 could contaminate headline analyses, and
balancing every domain to the minimum successful repeat count allowed one
flaky domain to reduce the entire analysis.

**Solution:** Configuration now defines headline repeats 8–19, pilot repeats
0–7, and a target of 10 successful repeats per domain. Headline analyses use
the configured window, retain domains with at least target k successful
repeats, drop domains below k, and report dropped domains with reasons.

**Affected code:** `config/project.yaml`,
`src/encdns/analysis/fingerprinting.py`, `src/analysis_v2.py`, and
`src/doh3_rq123_analysis.py`.

**Reasoning:** The policy separates exploratory pilot data from headline
results and makes domain eligibility independent instead of allowing the
worst domain to determine the sample size for every domain.

### 10. Strict overnight run isolation

**Problem:** The overnight wrappers previously wrote into shared
`data/raw/manifest.csv` and `data/raw/pcaps`. Deterministic PCAP names and
`--resume` could mix new data with historical data or overwrite prior
captures.

**Solution:** The capture driver now accepts `--run-dir`, `--manifest`, and
`--pcap-dir`. When `--run-dir` is supplied, it creates and uses only that
directory's `manifest.csv` and `pcaps/`. The overnight wrappers generate a
unique UTC timestamp plus process identifier, derive a unique batch/run ID,
refuse to reuse an existing run directory, and pass the isolated directory to
the driver.

**Affected code:** `src/probe_and_capture.py`,
`scripts/run_overnight.ps1`, `scripts/run_overnight.sh`,
`docs/RUNBOOK_CAPTURE.md`, and `docs/EXPERIMENT_PROTOCOL.md`.

**Reasoning:** Isolation is enforced at the output-path boundary rather than
by relying on batch labels. This protects against accidental collisions even
if a later tool filters batches incorrectly.

**Compatibility:** Direct driver invocations without `--run-dir` retain the
existing default paths. The overnight wrappers no longer use the shared
defaults.

**Verification:** Python and PowerShell syntax checks passed; no overnight
capture was started; no `data/raw/overnight_runs/` directory was created
during validation; the full plan remains 19,200 jobs.

### 11. Mandatory manifest migration and privacy sanitization

**Problem:** The live manifest may have a legacy 15-column header or legacy-width
rows. Appending a new 28-column row directly would produce a mixed-width CSV
that downstream tools cannot interpret reliably. A legacy `public_ip` column
could also contain a literal address.

**Solution:** Before opening the manifest for append, the capture driver checks
the header and row widths. If migration is needed, it first copies the file to
`data/raw/manifest_pre_migration.csv` (or the equivalent manifest directory),
rewrites the file with the 28-column header, preserves old values, leaves new
fields blank, and replaces any literal IP with a salted hash. Unsupported
mixed-width rows cause a hard failure instead of silent truncation.

**Affected code:** `upgrade_manifest()` and `validate_manifest()` in
`src/probe_and_capture.py`, manifest tests in `tests/test_manifest.py`, the
smoke schema output in `src/encdns/cli.py`, and `docs/ETHICS.md`.

**Reasoning:** Backup-before-rewrite gives a recovery point; hard validation
prevents data corruption; hashing legacy values enforces the privacy boundary
before the file can receive new data.

**Verification:** Manifest and q metadata tests passed (10 tests total).
`smoke-check` now prints the complete header and the set of row lengths, and
returns NO-GO if the header is not the 28-column schema or the row-length set
is not `{28}`.

## Operational rules after these changes

- Treat each directory under `data/raw/overnight_runs/` as an independent
  collection run.
- Do not append overnight data to `data/raw/manifest.csv`.
- Do not point an overnight run at the historical `data/raw/pcaps/`.
- Pass the selected run's manifest explicitly to validation and extraction
  tools; do not regenerate the global processed dataset merely to validate
  capture health.
- Keep `padding_present=unknown` documented as an observability limitation,
  not as proof that padding is absent.
- Preserve failed rows and investigate them by batch/run ID rather than
  deleting them from an active run.

## Worktree and commit status

The entries through `0cc613a` are committed on `setup-restructure`. The
overnight isolation change and this document are currently uncommitted. The
existing `data/processed/dataset.csv` worktree marker is not part of the
intentional architecture change; its content matches the committed blob.
