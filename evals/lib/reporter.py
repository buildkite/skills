"""Terminal output and JSON result reporting for eval runs."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ANSI colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if _supports_color() else text


def print_header(skill: str, skill_size: int, model: str, eval_count: int, filters: str):
    """Print the run header."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n{_c(BOLD, 'Quality Eval')} — {now}")
    print(f"Skill: skills/{skill}/SKILL.md ({skill_size:,} bytes)")
    print(f"Model: {model}")
    print(f"Evals: {eval_count}{f' ({filters})' if filters else ''}")
    print()


def print_result(eval_entry: dict, grade: dict):
    """Print a single eval result line."""
    eval_id = eval_entry["id"]
    total = grade["total_expected"]
    matched = len(grade["contains_matched"])
    question = eval_entry["question"]

    # Truncate question for display
    max_q = 60
    q_display = question[:max_q] + "..." if len(question) > max_q else question

    if grade["passed"]:
        status = _c(GREEN, "PASS")
        detail = f"[{matched}/{total} contains]"
    else:
        status = _c(RED, "FAIL")
        parts = []
        if grade["contains_missed"]:
            parts.append(f"missing: {', '.join(repr(t) for t in grade['contains_missed'])}")
        if grade["not_contains_violated"]:
            parts.append(f"violated: {', '.join(repr(t) for t in grade['not_contains_violated'])}")
        detail = f"[{matched}/{total} contains]  {'; '.join(parts)}"

    print(f"  {status}  {eval_id:<16s} {detail}")
    print(f"        {_c(DIM, q_display)}")


def print_summary(results: list[dict], evals: list[dict]):
    """Print the summary block."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    pass_rate = (passed / total * 100) if total else 0

    # Average contains coverage
    coverage_scores = []
    for r in results:
        t = r["total_expected"]
        if t > 0:
            coverage_scores.append(len(r["contains_matched"]) / t)
    avg_coverage = (sum(coverage_scores) / len(coverage_scores) * 100) if coverage_scores else 0

    violations = sum(len(r["not_contains_violated"]) for r in results)

    print(f"\n{_c(BOLD, 'Summary:')}")
    color = GREEN if pass_rate >= 80 else YELLOW if pass_rate >= 50 else RED
    print(f"  Pass: {_c(color, f'{passed}/{total}')} ({pass_rate:.1f}%)")
    print(f"  Contains coverage: {avg_coverage:.1f}%")
    print(f"  Boundary violations: {violations}")

    # List failures
    failures = [(r, e) for r, e in zip(results, evals) if not r["passed"]]
    if failures:
        print(f"\n  {_c(BOLD, 'Failing evals:')}")
        for r, e in failures:
            parts = []
            if r["contains_missed"]:
                parts.append(f"missing {', '.join(repr(t) for t in r['contains_missed'])}")
            if r["not_contains_violated"]:
                parts.append(f"violated {', '.join(repr(t) for t in r['not_contains_violated'])}")
            print(f"    {e['id']}: {'; '.join(parts)}")
    print()


def write_json_results(
    results: list[dict],
    evals: list[dict],
    skill: str,
    model: str,
    skill_size: int,
) -> Path:
    """Write results to a JSON file and return the path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"quality-{skill}-{timestamp}.json"
    path = RESULTS_DIR / filename

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill": skill,
        "model": model,
        "skill_size_bytes": skill_size,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "results": [
            {
                "id": e["id"],
                "question": e["question"],
                "cluster": e.get("cluster", ""),
                "difficulty": e.get("difficulty", ""),
                **r,
            }
            for r, e in zip(results, evals)
        ],
    }

    path.write_text(json.dumps(output, indent=2) + "\n")
    return path


def print_comparison(current_results: list[dict], current_evals: list[dict], compare_path: str):
    """Load a previous result file and print what changed."""
    prev = json.loads(Path(compare_path).read_text())
    prev_by_id = {r["id"]: r for r in prev["results"]}

    fixed = []
    regressed = []
    unchanged_pass = 0
    unchanged_fail = 0

    for r, e in zip(current_results, current_evals):
        eid = e["id"]
        if eid not in prev_by_id:
            continue
        prev_r = prev_by_id[eid]
        if not prev_r["passed"] and r["passed"]:
            fixed.append(eid)
        elif prev_r["passed"] and not r["passed"]:
            regressed.append(eid)
        elif r["passed"]:
            unchanged_pass += 1
        else:
            unchanged_fail += 1

    prev_rate = prev.get("pass_rate", 0) * 100
    curr_passed = sum(1 for r in current_results if r["passed"])
    curr_rate = (curr_passed / len(current_results) * 100) if current_results else 0
    delta = curr_rate - prev_rate

    print(f"\n{_c(BOLD, 'Comparison')} vs {Path(compare_path).name}:")

    if fixed:
        for eid in fixed:
            print(f"  {_c(GREEN, 'FIXED')}      {eid}")
    if regressed:
        for eid in regressed:
            print(f"  {_c(RED, 'REGRESSED')}  {eid}")

    if not fixed and not regressed:
        print(f"  No changes in pass/fail status")

    sign = "+" if delta >= 0 else ""
    color = GREEN if delta > 0 else RED if delta < 0 else DIM
    print(f"\n  Pass rate: {prev_rate:.1f}% → {curr_rate:.1f}% ({_c(color, f'{sign}{delta:.1f}%')})")
    print()
