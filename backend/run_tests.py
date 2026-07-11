"""One-shot test runner with a concise per-area report.

WHY THIS EXISTS
    The suite is split into independent AREAS (one test file each: words, scoring, chat, …).
    For a change that only touches ONE area there's no value in running the others, so this
    runner lets you run just the area(s) you touched — much faster — or the whole suite when a
    change is cross-cutting.

USAGE
    python run_tests.py                     # ALL areas (default) — use when a change is
                                            #   cross-cutting or you're unsure what it touched
    python run_tests.py words               # just the Words area
    python run_tests.py words scoring       # several areas (space-separated)
    python run_tests.py words,scoring       # commas work too
    python run_tests.py --list              # print the area keys + their files, then exit
    python run_tests.py --live              # ADD the live real-LLM smoke tests (uses .env
                                            #   models, costs quota). Combine with areas or alone.
    python run_tests.py chat --live         # a specific area + live smoke

RULE OF THUMB (mirrors CLAUDE.md's "use judgment" testing note)
    - Change confined to one area's code path        → run that area.
    - Change to shared plumbing (repo, mongo, deps,   → run ALL (pass nothing).
      config, prompt_builder, models, schemas)          When unsure, run ALL.

Prints a per-area PASS/FAIL table and writes tests/last_report.txt. Exit code 1 on any failure.
Unknown area keys are rejected with the valid list (so a typo never silently runs nothing).

ADDING A NEW AREA
    Add one `"key": ("test_file", "Human label")` row to AREAS below, in the same change that
    adds the test file. The key is what you type on the command line; the file is what pytest
    runs; the label is what the report prints.
"""

import re
import subprocess
import sys
from pathlib import Path

# key -> (test module name, human-readable report label)
AREAS = {
    "auth": ("test_auth", "Auth (Google OAuth flow, sessions, data isolation)"),
    "memory": ("test_memory", "Memory files (identity/memory/persona, append/edit)"),
    "words": ("test_words", "Words API (add, enrich, adjust, events)"),
    "scoring": ("test_scoring", "Scoring engine (matrix, cap, decay, spaced repetition)"),
    "conversations": ("test_conversations", "Conversations + search (BM25/regex, windows)"),
    "chat": ("test_chat", "Chat flow (tool loop, history, judge, title)"),
    "model": ("test_model", "Model config (BYO key, tiers, verify/encrypt, gate)"),
    "dashboard": ("test_dashboard", "Dashboard & health"),
    "settings": ("test_settings", "Settings / data purge"),
    "live": ("test_live_smoke", "LIVE provider smoke (real LLM)"),
}

# Areas run by default (everything except the live smoke, which is opt-in via --live).
DEFAULT_KEYS = [k for k in AREAS if k != "live"]


def _parse_args(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Returns (selected_area_keys, live, list_only)."""
    live = "--live" in argv
    list_only = "--list" in argv
    tokens: list[str] = []
    for a in argv:
        if a in ("--live", "--list"):
            continue
        # allow comma-separated groups too: "words,scoring"
        tokens += [t for t in a.split(",") if t]

    if not tokens:
        keys = list(DEFAULT_KEYS)
    else:
        unknown = [t for t in tokens if t not in AREAS]
        if unknown:
            valid = ", ".join(AREAS)
            print(f"Unknown area(s): {', '.join(unknown)}\nValid areas: {valid}")
            sys.exit(2)
        keys = tokens

    # --live means "also include the live smoke area" (unless the user named areas without it,
    # in which case we still add it — the flag is an explicit opt-in signal).
    if live and "live" not in keys:
        keys.append("live")
    return keys, live, list_only


def main() -> int:
    keys, live, list_only = _parse_args(sys.argv[1:])

    if list_only:
        print("Available areas (key -> test file):")
        for k, (mod, label) in AREAS.items():
            print(f"  {k:<14} {mod:<20} {label}")
        print('\nRun all: `python run_tests.py`   |   subset: `python run_tests.py words scoring`')
        return 0

    files = [f"tests/{AREAS[k][0]}.py" for k in keys]

    args = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    if live:
        args += ["-m", ""]  # override the default "not live" deselection in pytest.ini
    args += files
    proc = subprocess.run(args, capture_output=True, text=True, cwd=Path(__file__).parent)
    out = proc.stdout + proc.stderr

    results: dict[str, list[str]] = {}
    for line in out.splitlines():
        m = re.match(r"tests[/\\](test_\w+)\.py::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)", line)
        if m:
            results.setdefault(m.group(1), []).append(m.group(3))

    # module name -> area key, so we report in AREAS order regardless of pytest ordering
    mod_to_key = {mod: k for k, (mod, _) in AREAS.items()}

    lines = ["=" * 62, "ENG BACKEND TEST REPORT", "=" * 62]
    scope = "ALL areas" if set(keys) >= set(DEFAULT_KEYS) else ", ".join(keys)
    lines.append(f"Scope: {scope}")
    lines.append("-" * 62)

    total_pass = total_fail = 0
    for k in keys:
        mod, label = AREAS[k]
        r = results.get(mod, [])
        if not r:
            if k == "live" and not live:
                lines.append(f"[SKIP] {label}  (run with --live)")
            else:
                lines.append(f"[----] {label}  (no tests collected)")
            continue
        passed = r.count("PASSED")
        failed = len(r) - passed - r.count("SKIPPED")
        total_pass += passed
        total_fail += failed
        status = "PASS" if failed == 0 else "FAIL"
        lines.append(f"[{status}] {label}  ({passed}/{len(r)} passed)")

    lines.append("-" * 62)
    verdict = "ALL GREEN - safe to proceed" if total_fail == 0 else f"{total_fail} FAILURE(S) - current change broke something"
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
