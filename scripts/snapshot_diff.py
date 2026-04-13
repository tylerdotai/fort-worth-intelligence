#!/usr/bin/env python3
"""
Compare two TAD certified appraisal snapshots and emit a diff manifest.

Usage:
    python3 scripts/snapshot_diff.py before.json after.json
    python3 scripts/snapshot_diff.py before.json after.json --format=table
    python3 scripts/snapshot_diff.py before.json after.json --field=market_value

Output categories:
    added      — PIDN exists only in after
    removed    — PIDN exists only in before
    changed    — PIDN in both, but value of tracked field differs
    unchanged  — PIDN in both, tracked field is identical

The tracked field defaults to "total_value" (market value).
This script is the spatial-temporal diff engine for the civic twin:
it powers the /graph/{id} diff semantics when the TAD roll updates.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

OUT = sys.stderr.write


def load_snapshot(path: str) -> dict[str, dict]:
    """Load a TAD snapshot JSON (JSON or JSONL) into {pidn: record}."""
    p = Path(path)
    if not p.exists():
        return {}

    records: dict[str, dict] = {}
    raw = p.read_text().strip()

    if raw.startswith("["):
        # JSON array
        data = json.loads(raw)
    else:
        # JSONL — one dict per line
        for line in raw.splitlines():
            if line.strip():
                rec = json.loads(line)
                pidn = rec.get("account_num")
                if pidn:
                    records[pidn] = rec
        return records

    for rec in data:
        pidn = rec.get("account_num")
        if pidn:
            records[pidn] = rec
    return records


def diff_snapshots(
    before: dict[str, dict],
    after: dict[str, dict],
    field: str = "total_value",
) -> dict[str, list[dict]]:
    """
    Compute the diff between two snapshots.
    Returns a dict with keys: added, removed, changed, unchanged.
    """
    before_keys = set(before.keys())
    after_keys = set(after.keys())

    added = [
        {"pidn": k, field: after[k].get(field)}
        for k in sorted(after_keys - before_keys)
    ]
    removed = [
        {"pidn": k, field: before[k].get(field)}
        for k in sorted(before_keys - after_keys)
    ]

    common = before_keys & after_keys
    changed, unchanged = [], []

    for pidn in sorted(common):
        b_val = before[pidn].get(field)
        a_val = after[pidn].get(field)
        diff = _numeric_diff(b_val, a_val)
        entry = {
            "pidn": pidn,
            f"{field}_before": b_val,
            f"{field}_after": a_val,
        }
        if diff:
            entry["delta"] = diff
            changed.append(entry)
        else:
            unchanged.append(entry)

    return {"added": added, "removed": removed, "changed": changed, "unchanged": unchanged}


def _numeric_diff(before_val, after_val) -> Optional[int]:
    """Return integer difference if values are numeric and differ, else None."""
    try:
        b = int(before_val or 0)
        a = int(after_val or 0)
        return a - b if a != b else None
    except (ValueError, TypeError):
        # Fall back to string comparison
        return None if str(before_val) == str(after_val) else 0


def format_table(diff: dict, field: str) -> str:
    """Format diff as a plain-text table."""
    lines = []
    total_added = len(diff["added"])
    total_removed = len(diff["removed"])
    total_changed = len(diff["changed"])
    total_unchanged = len(diff["unchanged"])

    lines.append(f"{'='*60}")
    lines.append(f"TAD Snapshot Diff — field: {field}")
    lines.append(f"{'='*60}")
    lines.append(f"  added:     {total_added:>6,}")
    lines.append(f"  removed:   {total_removed:>6,}")
    lines.append(f"  changed:   {total_changed:>6,}")
    lines.append(f"  unchanged: {total_unchanged:>6,}")
    lines.append(f"{'─'*60}")

    if diff["added"]:
        lines.append(f"\n  Top 5 by {field} (added):")
        top = sorted(diff["added"], key=lambda x: _val(x.get(field)), reverse=True)[:5]
        for row in top:
            lines.append(f"    + {row['pidn']:>15}  {field}: ${row.get(field) or 0:>15,}")

    if diff["removed"]:
        lines.append(f"\n  Top 5 by {field} (removed):")
        top = sorted(diff["removed"], key=lambda x: _val(x.get(field)), reverse=True)[:5]
        for row in top:
            lines.append(f"    - {row['pidn']:>15}  {field}: ${row.get(field) or 0:>15,}")

    if diff["changed"]:
        lines.append(f"\n  Top 5 by delta (changed):")
        top = sorted(diff["changed"], key=lambda x: abs(x.get("delta") or 0), reverse=True)[:5]
        for row in top:
            d = row.get("delta", 0)
            sign = "+" if d > 0 else ""
            lines.append(
                f"    ~ {row['pidn']:>15}  {field}_before: ${row.get(f'{field}_before') or 0:>12,}  "
                f"{field}_after: ${row.get(f'{field}_after') or 0:>12,}  delta: {sign}${d:>12,}"
            )

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)


def _val(v) -> int:
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Diff two TAD certified appraisal snapshots.")
    ap.add_argument("before", help="Path to the earlier snapshot JSON/JSONL")
    ap.add_argument("after", help="Path to the later snapshot JSON/JSONL")
    ap.add_argument(
        "--field",
        default="total_value",
        help="Field to track for changes (default: total_value)",
    )
    ap.add_argument(
        "--format",
        dest="fmt",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )
    args = ap.parse_args()

    before_data = load_snapshot(args.before)
    after_data = load_snapshot(args.after)

    diff = diff_snapshots(before_data, after_data, field=args.field)

    if args.fmt == "json":
        print(json.dumps(diff, indent=2))
    else:
        print(format_table(diff, args.field))
