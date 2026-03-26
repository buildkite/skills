"""Terminal output and JSON result reporting for eval runs."""

import json
import re
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


# --- Trigger eval reporting ---


def print_trigger_header(
    model: str,
    eval_count: int,
    skill_count: int,
    filters: str,
    runs_per_query: int,
):
    """Print header for a trigger eval run."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n{_c(BOLD, 'Trigger Eval')} — {now}")
    print(f"Model: {model}")
    print(f"Skills: {skill_count} descriptions loaded")
    print(f"Evals: {eval_count}{f' ({filters})' if filters else ''}")
    if runs_per_query > 1:
        print(f"Runs per query: {runs_per_query}")
    print()


def print_trigger_result(eval_entry: dict, grade: dict):
    """Print a single trigger eval result line."""
    eval_id = eval_entry["id"]
    query = eval_entry["query"]
    expected = grade["expected_skill"] or "none"
    selected = grade["selected_skill"] or "none"

    max_q = 60
    q_display = query[:max_q] + "..." if len(query) > max_q else query

    if grade["passed"]:
        status = _c(GREEN, "PASS")
        detail = f"→ {selected}"
    else:
        status = _c(RED, "FAIL")
        detail = f"expected {_c(BOLD, expected)}, got {_c(RED, selected)}"

    print(f"  {status}  {eval_id:<20s} {detail}")
    print(f"        {_c(DIM, q_display)}")


def print_trigger_multi_result(eval_entry: dict, run_grades: list[dict]):
    """Print a trigger eval result with multi-run trigger rates."""
    eval_id = eval_entry["id"]
    query = eval_entry["query"]
    expected = eval_entry.get("expected_skill") or "none"
    total_runs = len(run_grades)
    correct_runs = sum(1 for g in run_grades if g["passed"])

    max_q = 60
    q_display = query[:max_q] + "..." if len(query) > max_q else query

    rate = correct_runs / total_runs
    if rate == 1.0:
        status = _c(GREEN, "PASS")
    elif rate >= 0.5:
        status = _c(YELLOW, "FLAKY")
    else:
        status = _c(RED, "FAIL")

    # Show which skills were selected across runs
    selections = {}
    for g in run_grades:
        s = g["selected_skill"] or "none"
        selections[s] = selections.get(s, 0) + 1
    sel_display = ", ".join(f"{s}:{n}" for s, n in sorted(selections.items(), key=lambda x: -x[1]))

    detail = f"{correct_runs}/{total_runs} correct  [{sel_display}]"
    print(f"  {status}  {eval_id:<20s} {detail}")
    print(f"        {_c(DIM, q_display)}")


def print_trigger_summary(grades: list[dict], evals: list[dict], skill_names: list[str]):
    """Print trigger eval summary with per-skill precision/recall and confusion matrix."""
    total = len(grades)
    passed = sum(1 for g in grades if g["passed"])
    pass_rate = (passed / total * 100) if total else 0

    print(f"\n{_c(BOLD, 'Summary:')}")
    color = GREEN if pass_rate >= 90 else YELLOW if pass_rate >= 70 else RED
    print(f"  Accuracy: {_c(color, f'{passed}/{total}')} ({pass_rate:.1f}%)")

    false_pos = sum(1 for g in grades if g["is_false_positive"])
    false_neg = sum(1 for g in grades if g["is_false_negative"])
    if false_pos or false_neg:
        print(f"  False positives: {false_pos}  |  False negatives: {false_neg}")

    # Per-skill precision/recall
    print(f"\n  {_c(BOLD, 'Per-skill metrics:')}")
    print(f"  {'Skill':<28s} {'Prec':>6s} {'Recall':>7s} {'F1':>6s}")
    print(f"  {'─' * 50}")

    for skill in skill_names:
        tp = sum(1 for g in grades if g["expected_skill"] == skill and g["selected_skill"] == skill)
        fp = sum(1 for g in grades if g["expected_skill"] != skill and g["selected_skill"] == skill)
        fn = sum(1 for g in grades if g["expected_skill"] == skill and g["selected_skill"] != skill)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Only show skills that appear in results
        if tp + fp + fn == 0:
            continue

        p_color = GREEN if precision >= 0.9 else YELLOW if precision >= 0.7 else RED
        r_color = GREEN if recall >= 0.9 else YELLOW if recall >= 0.7 else RED
        f_color = GREEN if f1 >= 0.9 else YELLOW if f1 >= 0.7 else RED

        print(
            f"  {skill:<28s} "
            f"{_rpad(_c(p_color, f'{precision:.0%}'), 6)} "
            f"{_rpad(_c(r_color, f'{recall:.0%}'), 7)} "
            f"{_rpad(_c(f_color, f'{f1:.0%}'), 6)}"
        )

    # Confusion matrix
    _print_confusion_matrix(grades, skill_names)

    # List failures
    failures = [(g, e) for g, e in zip(grades, evals) if not g["passed"]]
    if failures:
        print(f"\n  {_c(BOLD, 'Failures:')}")
        for g, e in failures:
            expected = g["expected_skill"] or "none"
            selected = g["selected_skill"] or "none"
            print(f"    {e['id']}: expected {expected}, got {selected}")
    print()


def _rpad(text: str, width: int) -> str:
    """Right-align text accounting for ANSI escape codes."""
    visible_len = len(re.sub(r"\033\[[0-9;]*m", "", text))
    padding = max(0, width - visible_len)
    return " " * padding + text


def _print_confusion_matrix(grades: list[dict], skill_names: list[str]):
    """Print an ASCII confusion matrix (expected rows x selected columns)."""
    # Short labels for display
    labels = []
    for s in skill_names:
        short = s.replace("buildkite-", "")
        labels.append(short)
    labels.append("none")

    all_names = skill_names + [None]

    # Build matrix
    matrix = {}
    for expected in all_names:
        matrix[expected] = {}
        for selected in all_names:
            matrix[expected][selected] = 0

    for g in grades:
        exp = g["expected_skill"]
        sel = g["selected_skill"]
        if exp in matrix and sel in matrix[exp]:
            matrix[exp][sel] += 1

    # Check if matrix has any data
    if not any(matrix[exp][sel] for exp in all_names for sel in all_names):
        return

    row_width = max(len(l) for l in labels) + 2
    col_width = max(max(len(l) for l in labels), 4) + 2

    print(f"\n  {_c(BOLD, 'Confusion matrix')} (rows=expected, cols=selected):")

    # Header row
    header = " " * (row_width + 2)
    for label in labels:
        header += _c(DIM, label.rjust(col_width))
    print(header)

    # Separator
    print(f"  {'─' * row_width}┬{'─' * (col_width * len(labels))}")

    # Data rows
    for i, exp in enumerate(all_names):
        row_label = labels[i].rjust(row_width)
        row = f"  {row_label}│"
        for j, sel in enumerate(all_names):
            count = matrix[exp][sel]
            if count == 0:
                cell = _c(DIM, "·")
            elif i == j:
                cell = _c(GREEN, str(count))
            else:
                cell = _c(RED, str(count))
            row += _rpad(cell, col_width)
        print(row)


def write_trigger_json_results(
    grades: list[dict],
    evals: list[dict],
    model: str,
    skill_names: list[str],
    runs_per_query: int,
) -> Path:
    """Write trigger eval results to a JSON file and return the path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"trigger-{timestamp}.json"
    path = RESULTS_DIR / filename

    total = len(grades)
    passed = sum(1 for g in grades if g["passed"])

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "eval_type": "trigger",
        "model": model,
        "skills": skill_names,
        "runs_per_query": runs_per_query,
        "total": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0,
        "results": [
            {
                "id": e["id"],
                "query": e["query"],
                "tags": e.get("tags", []),
                **g,
            }
            for g, e in zip(grades, evals)
        ],
    }

    path.write_text(json.dumps(output, indent=2) + "\n")
    return path


def print_trigger_comparison(
    current_grades: list[dict],
    current_evals: list[dict],
    compare_path: str,
):
    """Load a previous trigger result file and print what changed."""
    prev = json.loads(Path(compare_path).read_text())
    prev_by_id = {r["id"]: r for r in prev["results"]}

    fixed = []
    regressed = []

    for g, e in zip(current_grades, current_evals):
        eid = e["id"]
        if eid not in prev_by_id:
            continue
        prev_r = prev_by_id[eid]
        if not prev_r["passed"] and g["passed"]:
            fixed.append(eid)
        elif prev_r["passed"] and not g["passed"]:
            regressed.append(eid)

    prev_rate = prev.get("accuracy", 0) * 100
    curr_passed = sum(1 for g in current_grades if g["passed"])
    curr_rate = (curr_passed / len(current_grades) * 100) if current_grades else 0
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
    print(f"\n  Accuracy: {prev_rate:.1f}% → {curr_rate:.1f}% ({_c(color, f'{sign}{delta:.1f}%')})")
    print()
