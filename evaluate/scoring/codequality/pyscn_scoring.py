"""
pyscn_scoring — measure code quality via pyscn for two targets.

Runs `uvx pyscn@latest analyze <path> --json` on:
  1. The code produced by tt  (translations/ghostfolio_pytx)   weight=0.80
  2. The tt translator itself  (tt/tt)                          weight=0.20

Returns a dict (and prints JSON when run directly) with per-target scores
and a weighted combined score.  No LLMs are used.

Usage (standalone):
  python evaluate/scoring/codequality/pyscn_scoring
  python evaluate/scoring/codequality/pyscn_scoring <translated_dir> <tt_dir>

Importable API:
  from evaluate.scoring.codequality.pyscn_scoring import run
  result = run(translated_path, tt_path)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

# Weights must sum to 1.0
TRANSLATED_WEIGHT = 0.80
TT_WEIGHT = 0.20

_GRADE_THRESHOLDS = [
    (90, "A"),
    (75, "B"),
    (60, "C"),
    (45, "D"),
]


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


def _run_pyscn(path: Path) -> dict:
    """Run pyscn analyze on *path* and return the parsed summary dict.

    On Windows where Smart App Control blocks the pyscn binary, set the
    env var ``PYSCN_USE_DOCKER=1`` to run pyscn inside a python:3.12-slim
    container instead.
    """
    import os
    if not path.exists():
        return {"error": f"path does not exist: {path}", "health_score": 0, "grade": "F"}

    # Auto-use Docker on Windows because Smart App Control blocks the pyscn
    # binary that uvx pulls in. Override with PYSCN_USE_DOCKER=0 to force uvx.
    use_docker = os.environ.get("PYSCN_USE_DOCKER")
    if use_docker is None:
        use_docker = "1" if sys.platform == "win32" else "0"
    if use_docker == "1":
        repo = str(REPO_ROOT).replace("\\", "/")
        # Path inside the container, relative to /repo
        rel = str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{repo}:/repo",
            "-w", "/repo",
            "-e", "MSYS_NO_PATHCONV=1",
            "python:3.12-slim",
            "bash", "-c",
            f"pip install -q pyscn && pyscn analyze /repo/{rel} --json",
        ]
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        result = subprocess.run(cmd, capture_output=True, text=True, env=env,
                                encoding="utf-8", errors="replace")
        # pyscn writes the JSON path to stdout/stderr; report ends up on host filesystem
        haystack = (result.stdout or "") + "\n" + (result.stderr or "")
        match = re.search(r"Unified JSON report generated:\s*(.+\.json)", haystack)
    else:
        result = subprocess.run(
            ["uvx", "pyscn@latest", "analyze", str(path), "--json"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        match = re.search(r"Unified JSON report generated:\s*(.+\.json)", result.stderr)

    if not match:
        return {"error": "pyscn did not emit a JSON report path", "health_score": 0, "grade": "F"}

    raw = match.group(1).strip()
    # When pyscn ran in the container the path is rooted at /repo; map it back.
    if use_docker == "1" and raw.startswith("/repo/"):
        raw = str(REPO_ROOT / raw[len("/repo/"):])
    report_path = Path(raw)
    if not report_path.exists():
        return {"error": f"report file not found: {report_path}", "health_score": 0, "grade": "F"}

    data = json.loads(report_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    return {
        "health_score":       summary.get("health_score", 0),
        "grade":              summary.get("grade", "F"),
        "complexity_score":   summary.get("complexity_score", 0),
        "dead_code_score":    summary.get("dead_code_score", 0),
        "duplication_score":  summary.get("duplication_score", 0),
        "coupling_score":     summary.get("coupling_score", 0),
        "dependency_score":   summary.get("dependency_score", 0),
        "architecture_score": summary.get("architecture_score", 0),
        "average_complexity": summary.get("average_complexity", 0),
        "code_duplication_percentage": summary.get("code_duplication_percentage", 0),
        "total_files":        summary.get("total_files", 0),
    }


def run(
    translated_path: Path | None = None,
    tt_path: Path | None = None,
) -> dict:
    """Score both targets and return a combined result dict."""
    import os
    _project = os.environ.get("PROJECT_NAME", "ghostfolio")
    translated_path = translated_path or (REPO_ROOT / "translations" / f"{_project}_pytx")
    tt_path = tt_path or (REPO_ROOT / "tt" / "tt")

    translated = _run_pyscn(translated_path)
    tt = _run_pyscn(tt_path)

    weighted = (
        translated.get("health_score", 0) * TRANSLATED_WEIGHT
        + tt.get("health_score", 0) * TT_WEIGHT
    )

    return {
        "translated_code": {
            "path": str(translated_path),
            "weight": TRANSLATED_WEIGHT,
            **translated,
        },
        "tt_code": {
            "path": str(tt_path),
            "weight": TT_WEIGHT,
            **tt,
        },
        "weighted_score": round(weighted, 2),
        "weighted_grade": _grade(weighted),
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    translated_path = Path(args[0]) if len(args) >= 1 else None
    tt_path = Path(args[1]) if len(args) >= 2 else None

    result = run(translated_path, tt_path)
    print(json.dumps(result, indent=2))
