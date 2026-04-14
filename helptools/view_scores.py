#!/usr/bin/env python3
"""
view_scores.py — View the score log, sorted by overall score (best first).

Usage:
  python helptools/view_scores.py            # all entries, best first
  python helptools/view_scores.py --last 10  # last 10 entries by time
  python helptools/view_scores.py --branch Thobias-2  # filter by branch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCORES_LOG = Path("/home/o/Personal/Code/Knowit/scores.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description="View score log")
    parser.add_argument("--last", type=int, help="Show last N entries by time")
    parser.add_argument("--branch", help="Filter by branch name")
    parser.add_argument("--sort", choices=["score", "time"], default="score",
                        help="Sort by overall score or timestamp (default: score)")
    args = parser.parse_args()

    if not SCORES_LOG.exists():
        print("No scores logged yet.", file=sys.stderr)
        return 1

    entries = []
    for line in SCORES_LOG.read_text().splitlines():
        if line.strip():
            entries.append(json.loads(line))

    if args.branch:
        entries = [e for e in entries if e.get("branch") == args.branch]

    if args.sort == "score":
        entries.sort(key=lambda e: e.get("overall") or 0, reverse=True)
    else:
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    if args.last:
        # For --last, always sort by time first, take last N, then re-sort
        by_time = sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)
        entries = by_time[:args.last]

    if not entries:
        print("No matching entries.", file=sys.stderr)
        return 1

    print(f"{'#':>3}  {'Branch':<14} {'Commit':<8} {'Tests':>6} {'Qual':>6} {'Score':>6} {'Legal':>6}  Message")
    print("-" * 100)
    for i, e in enumerate(entries, 1):
        t = f"{e['tests_pct']:.1f}" if e.get("tests_pct") is not None else "?"
        q = f"{e['quality_pct']:.1f}" if e.get("quality_pct") is not None else "?"
        o = f"{e['overall']:.1f}" if e.get("overall") is not None else "?"
        legal = "yes" if e.get("legal") else "NO"
        msg = e.get("message", "")[:60]
        print(f"{i:>3}  {e.get('branch','?'):<14} {e.get('commit','?'):<8} {t:>6} {q:>6} {o:>6} {legal:>6}  {msg}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
