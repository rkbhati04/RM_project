"""Supported command line interface for the study."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from .config import ROOT, load_project_config, run_metadata, write_json

def _run_dir(config: dict, run_id: str) -> Path:
    directory = ROOT / config["paths"]["results"] / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def status(_: argparse.Namespace) -> int:
    import pandas as pd

    config = load_project_config(); dataset = ROOT / config["paths"]["dataset"]; manifest = ROOT / config["paths"]["manifest"]
    if manifest.exists():
        rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
        frame = pd.DataFrame(rows)
        print(frame.groupby(["network", "resolver", "protocol", "status"], dropna=False).size().to_string())
    if dataset.exists():
        frame = pd.read_csv(dataset)
        print("\nProcessed rows by network, resolver, protocol:")
        print(frame.groupby(["network", "resolver", "protocol"], dropna=False).size().to_string())
    return 0


def smoke_check(_: argparse.Namespace) -> int:
    manifest = ROOT / "data" / "raw" / "manifest.csv"
    with manifest.open(encoding="utf-8", newline="") as handle:
        header = handle.readline().rstrip("\r\n").split(",")
        raw_rows = list(csv.reader(handle))
    row_lengths = {len(row) for row in raw_rows}
    print(f"manifest_header={','.join(header)}")
    print(f"manifest_row_lengths={sorted(row_lengths)}")
    if header != [
        "timestamp", "run_id", "batch", "order_mode", "network", "machine_id", "public_ip",
        "rtt_ms", "q_version", "client", "resolver", "protocol", "workload",
        "domain", "repeat", "returncode", "latency_s", "packets", "bytes",
        "answer_count", "cname_count", "ttl_min", "padding_present",
        "udp_blocked_flag", "status", "server_ips", "pcap_path", "note",
    ] or row_lengths not in ({28}, {0}):
        print("NO-GO: manifest schema or row lengths are invalid")
        return 1
    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    smoke = [row for row in rows if row.get("batch", "").lower() == "smoke"]
    latest = {row["pcap_path"]: row for row in smoke}
    print("resolver/protocol | status | answers | ttl_min | ip_hash | padding | median_s | >1.5s")
    failures = []
    for resolver, protocol in sorted({(r["resolver"], r["protocol"]) for r in latest.values()}):
        group = [r for r in latest.values() if (r["resolver"], r["protocol"]) == (resolver, protocol)]
        counts = Counter(r.get("status", "unknown") for r in group)
        answers = ",".join(sorted({r.get("answer_count", "") or "-" for r in group}))
        ttls = ",".join(sorted({r.get("ttl_min", "") or "-" for r in group}))
        hashes = all(re.fullmatch(r"hash:[0-9a-f]{16}", r.get("public_ip", "")) for r in group)
        padding = ",".join(sorted({r.get("padding_present", "") or "-" for r in group}))
        latencies = [float(r["latency_s"]) for r in group if r.get("latency_s")]
        drops = sum(value > 1.5 for value in latencies)
        valid = all(
            r.get("status") == "ok"
            and r.get("answer_count", "").isdigit()
            and int(r["answer_count"]) >= 1
            and r.get("ttl_min", "").isdigit()
            and int(r["ttl_min"]) > 0
            and bool(re.fullmatch(r"hash:[0-9a-f]{16}", r.get("public_ip", "")))
            and r.get("padding_present") in {"true", "false", "unknown"}
            and float(r.get("latency_s") or 99) <= 1.5
            for r in group
        )
        if not valid:
            failures.append(f"{resolver}/{protocol}")
        print(f"{resolver}/{protocol} | {dict(counts)} | {answers} | {ttls} | "
              f"{'yes' if hashes else 'no'} | {padding} | "
              f"{statistics.median(latencies):.3f} | "
              f"{drops}/{len(group)}")
    print(f"rows={len(latest)} smoke_manifest_rows={len(smoke)} latency_cutoff=1.5s")
    print("GO" if len(latest) == 16 and not failures else f"NO-GO: {', '.join(failures)}")
    return 0 if len(latest) == 16 and not failures else 1


def smoke_cleanup(_: argparse.Namespace) -> int:
    manifest = ROOT / "data" / "raw" / "manifest.csv"
    backup = manifest.with_name(
        f"manifest_before_smoke_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    shutil.copy2(manifest, backup)
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    kept = [row for row in rows if row.get("batch", "").lower() != "smoke"]
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(kept)
    print(f"Backed up {len(rows) - len(kept)} smoke rows to {backup}")
    return 0

def merge_runs(args: argparse.Namespace) -> int:
    manifests = [args.pilot_manifest]
    manifests.extend(sorted(args.overnight_root.glob("*/manifest.csv")))
    rows = []
    schema = None
    for path in manifests:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            if schema is None:
                schema = fields
            elif fields != schema:
                raise ValueError(f"Schema mismatch in {path}")
            for row in reader:
                if row.get("network", "").lower() == "airtel" and 0 <= int(row.get("repeat") or -1) <= 19:
                    row["batch"] = "T0"
                rows.append(row)
    latest = {}
    for row in rows:
        latest[row["pcap_path"]] = row
    keys = [(row["pcap_path"], row["resolver"], row["protocol"], row["domain"], row["repeat"])
            for row in latest.values()]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate merge keys after newest-per-PCAP selection")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(schema or ()))
        writer.writeheader()
        writer.writerows(sorted(latest.values(), key=lambda row: row["pcap_path"]))
    print(f"Merged {len(rows)} source rows into {len(latest)} rows: {args.output}")
    return 0

def analyze(args: argparse.Namespace) -> int:
    import pandas as pd
    from .analysis.fingerprinting import evaluate

    config = load_project_config(); dataset = ROOT / config["paths"]["dataset"]; frame = pd.read_csv(dataset)
    run_id = args.run_id or f"analysis-{hashlib.sha256(dataset.read_bytes()).hexdigest()[:12]}"
    output = _run_dir(config, run_id)
    progress = output / "progress.log"
    started = time.time()
    def log(message: str) -> None:
        with progress.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.time() - started:.1f}s {message}\n")
            handle.flush()
    domain_counts = {}
    for workload, group in frame.groupby("workload"):
        counts = group[group["repeat"].between(8, 19)].groupby("domain")["repeat"].nunique()
        domain_counts[workload] = {
            "k10": int((counts >= 10).sum()), "k8": int((counts >= 8).sum())
        }
    target_k = 10 if all(values["k10"] >= 60 for values in domain_counts.values()) else 8
    metadata = run_metadata(ROOT / "config" / "project.yaml", dataset)
    metadata.update({"target_k": target_k, "domain_counts": domain_counts,
                     "headline_folds": "5 folds, 2 repeats held out",
                     "real_trees": 100, "null_trees": 50,
                     "permutations": args.permutations or config["permutations"]})
    write_json(output / "run_metadata.json", metadata)
    seeds = config["seed_list"]
    analysis_config = config["analysis"]
    permutations = config["permutations"] if args.permutations is None else args.permutations
    workers = max(1, (os.cpu_count() or 2) - 1)
    rows = []
    for (workload, resolver, protocol), subset in frame.groupby(["workload", "resolver", "protocol"]):
        checkpoint = output / f"checkpoint_{workload}_{resolver}_{protocol}.json"
        if args.resume and checkpoint.exists():
            rows.append(json.loads(checkpoint.read_text(encoding="utf-8")))
            continue
        log(f"start {workload}/{resolver}/{protocol}")
        result = evaluate(
            subset, seeds, permutations, config["rf_estimators"],
            repeat_start=analysis_config["headline_repeats"][0],
            repeat_end=analysis_config["headline_repeats"][1],
            target_k=target_k, workers=workers,
        )
        if result:
            item = {"workload": workload, "resolver": resolver, "protocol": protocol, **result}
            checkpoint.write_text(json.dumps(item), encoding="utf-8")
            rows.append(item)
        log(f"done {workload}/{resolver}/{protocol}")
    table = pd.DataFrame(rows); table.to_csv(output / "rq1_rq2_fingerprinting.csv", index=False)
    log("WP3/WP4 headline analyses complete")
    baselines = []
    for (workload, resolver, protocol), subset in frame.groupby(["workload", "resolver", "protocol"]):
        full = evaluate(
            subset, seeds, permutations, config["rf_estimators"],
            repeat_start=analysis_config["headline_repeats"][0],
            repeat_end=analysis_config["headline_repeats"][1],
            target_k=target_k, workers=workers,
        )
        length = subset.assign(domain_length=subset.domain.str.len())
        length_result = evaluate(length, seeds, permutations, 100, ["domain_length"], workers=workers)
        if full and length_result:
            baselines.append({"workload": workload, "resolver": resolver, "protocol": protocol, "full_accuracy": full["accuracy"], "length_only_accuracy": length_result["accuracy"], "effect_over_length": full["accuracy"] - length_result["accuracy"]})
    pd.DataFrame(baselines).to_csv(output / "baselines.csv", index=False)
    write_json(output / "checkpoint_baselines.json", {"status": "complete", "rows": len(baselines)})
    log("complete")
    print(output)
    return 0

def report(args: argparse.Namespace) -> int:
    import pandas as pd

    config = load_project_config(); directory = _run_dir(config, args.run_id)
    table_path = directory / "rq1_rq2_fingerprinting.csv"
    if not table_path.exists(): raise FileNotFoundError(f"Run analyze first: {table_path}")
    table = pd.read_csv(table_path)
    lines = ["# Analysis report", "", "All claims below are derived from the run CSV.", "", table.to_markdown(index=False), ""]
    lines.append("A non-significant result means no detectable leakage at this sample size.")
    (directory / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return 0

def ledger(args: argparse.Namespace) -> int:
    import pandas as pd

    config = load_project_config(); directory = _run_dir(config, args.run_id); table = pd.read_csv(directory / "rq1_rq2_fingerprinting.csv")
    ledger = pd.DataFrame({"claim_id": [f"FP-{index + 1}" for index in range(len(table))], "text": [f"Domain fingerprinting accuracy for {row.resolver}/{row.protocol}" for row in table.itertuples()], "value": table.accuracy, "ci_low": table.ci_low, "ci_high": table.ci_high, "source_file": "rq1_rq2_fingerprinting.csv", "script": "python -m encdns analyze", "commit": "unrecorded"})
    ledger.to_csv(ROOT / "docs" / "claims_ledger.csv", index=False); return 0

def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m encdns"); sub = parser.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("status"); status_parser.set_defaults(func=status)
    smoke_parser = sub.add_parser("smoke-check"); smoke_parser.set_defaults(func=smoke_check)
    cleanup_parser = sub.add_parser("smoke-cleanup"); cleanup_parser.set_defaults(func=smoke_cleanup)
    merge_parser = sub.add_parser("merge-runs")
    merge_parser.add_argument("--pilot-manifest", type=Path, required=True)
    merge_parser.add_argument("--overnight-root", type=Path, required=True)
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.set_defaults(func=merge_runs)
    analyze_parser = sub.add_parser("analyze"); analyze_parser.add_argument("--run-id"); analyze_parser.add_argument("--permutations", type=int); analyze_parser.add_argument("--resume", action="store_true"); analyze_parser.set_defaults(func=analyze)
    for name, function in (("report", report), ("ledger", ledger)):
        child = sub.add_parser(name); child.add_argument("run_id"); child.set_defaults(func=function)
    for name in ("capture", "extract", "figures"):
        child = sub.add_parser(name); child.set_defaults(func=lambda _: (_ for _ in ()).throw(NotImplementedError(f"Use the documented legacy driver for {name} until WP2 migration is complete.")))
    args = parser.parse_args(); return args.func(args)

if __name__ == "__main__": raise SystemExit(main())
