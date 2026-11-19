"""Command line entry point: read tickets from CSV and print SLA state."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime

from .core import Assessment, Policy, assess

ORDER = {"breached": 0, "at-risk": 1, "ok": 2, "late": 3, "met": 4}


def load_assessments(path: str, now: datetime, policy: Policy) -> tuple[list[Assessment], list[str]]:
    """Assess every CSV row (ticket_id, priority, opened, closed). Bad rows become messages."""
    results: list[Assessment] = []
    errors: list[str] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            try:
                closed = row.get("closed", "").strip()
                results.append(assess(
                    row["ticket_id"].strip(), row["priority"],
                    datetime.fromisoformat(row["opened"].strip()),
                    datetime.fromisoformat(closed) if closed else None,
                    now, policy))
            except (KeyError, ValueError) as exc:
                errors.append(f"line {line}: {exc}")
    return results, errors


def render(results: list[Assessment]) -> str:
    """Table sorted with the most urgent tickets first."""
    head = f"{'ticket':<9}{'priority':<10}{'deadline':<18}{'used':>6}  state"
    rows = [head]
    for a in sorted(results, key=lambda r: (ORDER[r.state], r.deadline)):
        rows.append(f"{a.ticket_id:<9}{a.priority:<10}{a.deadline:%Y-%m-%d %H:%M}  "
                    f"{a.percent_used:>4}%  {a.state}")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    """Exit 0 normally, 1 if any open ticket is breached, 2 on unreadable input."""
    parser = argparse.ArgumentParser(prog="slatimer", description="SLA breach risk in business hours.")
    parser.add_argument("csv_file")
    parser.add_argument("--now", help="ISO time to assess at (default: current time)")
    parser.add_argument("--holiday", action="append", default=[], help="YYYY-MM-DD, repeatable")
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.now) if args.now else datetime.now()
        policy = Policy(holidays=frozenset(date.fromisoformat(h) for h in args.holiday))
        results, errors = load_assessments(args.csv_file, now, policy)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Assessed at {now:%Y-%m-%d %H:%M}")
    print(render(results))
    for message in errors:
        print(f"skipped {message}", file=sys.stderr)
    return 1 if any(r.state == "breached" for r in results) else 0
