"""One-shot test runner with a concise report.

Usage:
    python run_tests.py           # fast suite (LLM mocked) — run after every change
    python run_tests.py --live    # also run live provider smoke tests (uses .env models)

Prints a per-area PASS/FAIL table and writes tests/last_report.txt.
"""

import re
import subprocess
import sys
from pathlib import Path

LIVE = "--live" in sys.argv

AREAS = {
    "test_memory": "Memory files (identity/memory/persona, append/edit)",
    "test_words": "Words API (add, enrich, adjust, events)",
    "test_scoring": "Scoring engine (matrix, cap, decay, spaced repetition)",
    "test_conversations": "Conversations + search (BM25/regex, windows)",
    "test_chat": "Chat flow (tool loop, history, judge, title)",
    "test_dashboard": "Dashboard & health",
    "test_settings": "Settings / data purge",
    "test_live_smoke": "LIVE provider smoke (real LLM)",
}


def main() -> int:
    args = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    if LIVE:
        args += ["-m", ""]  # override the default "not live" deselection
    proc = subprocess.run(args, capture_output=True, text=True, cwd=Path(__file__).parent)
    out = proc.stdout + proc.stderr

    results: dict[str, list[str]] = {k: [] for k in AREAS}
    for line in out.splitlines():
        m = re.match(r"tests[/\\](test_\w+)\.py::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)", line)
        if m:
            # unknown files still get counted so a missing AREAS entry can't crash the report
            results.setdefault(m.group(1), []).append(m.group(3))

    lines = ["=" * 62, "ENG BACKEND TEST REPORT", "=" * 62]
    total_pass = total_fail = 0
    for key, label in AREAS.items():
        r = results.get(key, [])
        if not r:
            if key == "test_live_smoke" and not LIVE:
                lines.append(f"[SKIP] {label}  (run with --live)")
            continue
        passed = r.count("PASSED")
        failed = len(r) - passed - r.count("SKIPPED")
        total_pass += passed
        total_fail += failed
        status = "PASS" if failed == 0 else "FAIL"
        lines.append(f"[{status}] {label}  ({passed}/{len(r)} passed)")
    lines.append("-" * 62)
    verdict = "ALL GREEN — safe to proceed" if total_fail == 0 else f"{total_fail} FAILURE(S) — current change broke something"
    lines.append(f"TOTAL: {total_pass} passed, {total_fail} failed | {verdict}")
    lines.append("=" * 62)
    if total_fail:
        lines.append("\nFailure details:")
        grab = False
        for line in out.splitlines():
            if line.startswith("=") and "FAILURES" in line:
                grab = True
            if grab:
                lines.append(line)

    report = "\n".join(lines)
    print(report)
    (Path(__file__).parent / "tests" / "last_report.txt").write_text(report, encoding="utf-8")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
