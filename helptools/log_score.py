#!/usr/bin/env python3
"""
log_score.py — Log evaluation scores with a description of what changed.

MANDATORY: Every agent MUST run this after every `make evaluate_tt_ghostfolio`.
The --message flag is REQUIRED and must describe what was changed and whether
it helped or hurt scores (and why, if known).

Usage:
  python helptools/log_score.py --message "Added getSymbolMetrics translation — tests up from 48 to 72"
  python helptools/log_score.py --message "Refactored arrow fn handling — broke destructuring, tests dropped to 45"

The log is written to /home/o/Personal/Code/Knowit/scores.jsonl (outside any
worktree so all agents share the same file without merge conflicts).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
SCORES_LOG = Path("/home/o/Personal/Code/Knowit/scores.jsonl")
RESULTS_DIR = REPO_ROOT / "evaluate" / "scoring" / "results"
CHECKS_DIR = REPO_ROOT / "evaluate" / "checks" / "results"


def _git(cmd: str) -> str:
    result = subprocess.run(
        ["git"] + cmd.split(),
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Log evaluation scores with a change description",
    )
    parser.add_argument(
        "-m", "--message",
        required=True,
        help="REQUIRED: Describe what changed and whether it helped or hurt",
    )
    args = parser.parse_args()

    if not args.message or len(args.message.strip()) < 10:
        print("ERROR: --message must be at least 10 characters", file=sys.stderr)
        return 1

    # Read latest scores
    scores_path = RESULTS_DIR / "publish_latest.json"
    tests_path = RESULTS_DIR / "tests_latest.json"
    checks_path = CHECKS_DIR / "latest.json"

    scores = {}
    if scores_path.exists():
        scores = json.loads(scores_path.read_text())
    if not scores and tests_path.exists():
        tests = json.loads(tests_path.read_text())
        scores["tests_pct"] = tests.get("percentage", 0.0)

    if not scores:
        print("WARNING: No evaluation results found. Run `make evaluate_tt_ghostfolio` first.", file=sys.stderr)
        print(f"  Looked for: {scores_path}", file=sys.stderr)
        return 1

    checks = {}
    if checks_path.exists():
        checks = json.loads(checks_path.read_text())

    # Git info
    branch = _git("branch --show-current")
    commit = _git("rev-parse --short HEAD")
    commit_full = _git("rev-parse HEAD")
    commit_msg = _git("log -1 --format=%s")
    worktree = str(REPO_ROOT)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "worktree": worktree,
        "commit": commit,
        "commit_full": commit_full,
        "commit_msg": commit_msg,
        "tests_pct": scores.get("tests_pct", None),
        "quality_pct": scores.get("quality_pct", None),
        "overall": scores.get("overall", None),
        "legal": scores.get("legal", None),
        "valid_checks": scores.get("valid_checks", None),
        "checks": checks.get("checks", {}),
        "message": args.message.strip(),
    }

    # Append to shared log
    SCORES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Print summary
    t = entry["tests_pct"]
    q = entry["quality_pct"]
    o = entry["overall"]
    legal = "legal" if entry.get("legal") else "ILLEGAL"
    print()
    print(f"  Logged: {branch}@{commit}  tests={t}  quality={q}  overall={o}  [{legal}]")
    print(f"  Message: {args.message.strip()}")
    print(f"  Log: {SCORES_LOG}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
