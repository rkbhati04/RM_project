"""Read-only manifest/dataset reports for an in-progress capture snapshot."""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str], key: str) -> float | None:
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def answer_comparison(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    ok = [r for r in rows if r.get("status") == "ok" and int(r.get("repeat") or -1) >= 8]
    grouped: dict[tuple[str, str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in ok:
        grouped[(row["resolver"], row["domain"], row["repeat"], row["batch"])][row["protocol"]] = row
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    pair_seen: dict[str, set[tuple[str, str]]] = defaultdict(set)
    pair_disagree: dict[str, dict[str, set[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for (resolver, domain, _repeat, _batch), pair in grouped.items():
        if "doh" not in pair or "doh3" not in pair:
            continue
        pair_key = (resolver, domain)
        pair_seen[resolver].add(pair_key)
        for field in ("answer_count", "cname_count", "ttl_min"):
            left = number(pair["doh"], field)
            right = number(pair["doh3"], field)
            if left is None or right is None:
                continue
            values[resolver][field].append(left - right)
            if left != right:
                pair_disagree[resolver][field].add(pair_key)
    output = []
    for resolver in sorted(pair_seen):
        for field in ("answer_count", "cname_count", "ttl_min"):
            diffs = values[resolver][field]
            output.append({
                "resolver": resolver,
                "metric": field,
                "paired_observations": len(diffs),
                "mean_doh_minus_doh3": round(statistics.fmean(diffs), 4) if diffs else "",
                "distribution": dict(Counter(round(x, 4) for x in diffs)),
                "domain_resolver_pairs": len(pair_seen[resolver]),
                "disagreeing_pairs": len(pair_disagree[resolver][field]),
                "disagreement_share": round(len(pair_disagree[resolver][field]) / len(pair_seen[resolver]), 4)
                if pair_seen[resolver] else "",
            })
    return output


def health(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["resolver"], row["protocol"])].append(row)
    output = []
    for (resolver, protocol), group in sorted(groups.items()):
        total = len(group)
        ok = sum(row.get("status") == "ok" for row in group)
        bad = sum(row.get("status") == "bad_metadata" for row in group)
        slow = sum((number(row, "latency_s") or 0) > 1.5 for row in group)
        output.append({
            "resolver": resolver, "protocol": protocol, "rows": total,
            "success_rate": round(ok / total, 4) if total else "",
            "bad_metadata": bad, "above_1_5s_share": round(slow / total, 4) if total else "",
        })
    hours: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        try:
            hour = datetime.fromtimestamp(int(row["timestamp"])).strftime("%H")
        except (KeyError, TypeError, ValueError, OSError):
            hour = "unknown"
        hours[(row["resolver"], row["protocol"], hour)].append(row)
    for (resolver, protocol, hour), group in sorted(hours.items()):
        output.append({
            "resolver": resolver, "protocol": protocol, "hour": hour,
            "rows": len(group),
            "success_rate": round(sum(r.get("status") == "ok" for r in group) / len(group), 4),
            "bad_metadata": sum(r.get("status") == "bad_metadata" for r in group),
        })
    return output


def padding(dataset: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    packet_fields = [f"pkt_{i:02d}" for i in range(20)]
    for row in dataset:
        for field in packet_fields:
            value = number(row, field)
            if value is not None and value:
                groups[(row.get("resolver", ""), row.get("protocol", ""))].append(abs(round(value)))
    output = []
    for (resolver, protocol), sizes in sorted(groups.items()):
        output.append({
            "resolver": resolver, "protocol": protocol, "sample_packet_sizes": len(sizes),
            "exact_multiple_128_share": round(sum(size % 128 == 0 for size in sizes) / len(sizes), 4)
            if sizes else "",
            "exact_multiple_468_share": round(sum(size % 468 == 0 for size in sizes) / len(sizes), 4)
            if sizes else "",
            "evidence_status": "not valid evidence",
            "interpretation": "network header bytes are included; packet-size multiples cannot infer EDNS0 padding",
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = load_csv(args.manifest)
    dataset = load_csv(args.dataset) if args.dataset.exists() else []
    write_csv(args.out / "answer_count_comparison.csv", answer_comparison(rows))
    write_csv(args.out / "health.csv", health(rows))
    write_csv(args.out / "padding_evidence.csv", padding(dataset))
    (args.out / "interpretation.txt").write_text(
        "TTL differences reflect resolver cache state and are not a protocol effect.\n"
        "Padding evidence is not valid evidence: network header bytes are included in sizes.\n",
        encoding="utf-8",
    )
    (args.out / "snapshot_status.txt").write_text(
        "snapshot, capture in progress\n"
        f"manifest={args.manifest}\nrows={len(rows)}\ndataset_rows={len(dataset)}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
