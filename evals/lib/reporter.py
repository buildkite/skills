"""Terminal output and JSON result reporting for eval runs."""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def _get_git_commit() -> str | None:
    """Return the short git commit SHA for HEAD, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None

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


def _print_cluster_table(
    clusters: dict[str, dict],
    col_a: str = "A",
    col_b: str = "B",
    delta_label: str = "Delta",
    key_a: str = "a_pass",
    key_b: str = "b_pass",
):
    """Print a per-cluster comparison table. Dims rows with no change."""
    print(f"  {'Cluster':<24s} {col_a:>6s} {col_b:>6s} {delta_label:>7s}")
    print(f"  {'─' * 46}")
    for cluster in sorted(clusters.keys()):
        c = clusters[cluster]
        a_r = c[key_a] / c["total"] * 100
        b_r = c[key_b] / c["total"] * 100
        lift = b_r - a_r
        lift_sign = "+" if lift >= 0 else ""
        if lift > 0:
            lift_color = GREEN
        elif lift < 0:
            lift_color = RED
        else:
            lift_color = DIM
        # Dim entire row when nothing changed
        if lift == 0:
            print(_c(DIM, f"  {cluster:<24s} {a_r:5.0f}% {b_r:5.0f}%  {lift_sign}{lift:.0f}%"))
        else:
            print(
                f"  {cluster:<24s} {a_r:5.0f}% {b_r:5.0f}% "
                f"{_c(lift_color, f'{lift_sign}{lift:.0f}%'):>7s}"
            )


def _format_failure_detail(result: dict) -> str:
    """Format missed/violated terms from a grade result dict."""
    parts = []
    missed = result.get("contains_missed", [])
    violated = result.get("not_contains_violated", [])
    total = result.get("total_expected", 0)
    matched = len(result.get("contains_matched", []))
    if missed:
        parts.append(f"[{matched}/{total}] missing: {', '.join(repr(t) for t in missed)}")
    if violated:
        parts.append(f"violated: {', '.join(repr(t) for t in violated)}")
    return "; ".join(parts)


def print_header(skill: str, skill_size: int, model: str, eval_count: int, filters: str, mode: str = None):
    """Print the run header."""
    now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    title = "Quality Eval"
    if mode == "baseline":
        title = "Quality Eval (BASELINE — no skill content)"
    elif mode == "skill":
        title = "Quality Eval (WITH SKILL)"
    print(f"\n{_c(BOLD, title)} — {now}")
    if mode == "baseline":
        print(f"Skill: {skill} (baseline — no content injected)")
    else:
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
    mode: str = None,
) -> Path:
    """Write results to a JSON file and return the path."""
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    prefix = f"baseline-{skill}" if mode == "baseline" else f"quality-{skill}"
    filename = f"{prefix}-{timestamp}.json"
    path = RESULTS_DIR / filename

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    output = {
        "timestamp": now.isoformat(),
        "git_commit": _get_git_commit(),
        "skill": skill,
        "model": model,
        "mode": mode or "skill",
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


def resolve_diff_files(args: list[str]) -> tuple[Path, Path]:
    """Resolve two result files for diffing.

    With 0 args: picks the two most recent quality-*.json files.
    With 2 args: uses the provided paths.
    """
    if len(args) == 2:
        a, b = Path(args[0]), Path(args[1])
        if not a.exists():
            print(f"Error: {a} not found.", file=sys.stderr)
            sys.exit(1)
        if not b.exists():
            print(f"Error: {b} not found.", file=sys.stderr)
            sys.exit(1)
        return a, b

    if len(args) == 1:
        print("Error: --diff expects 0 or 2 files. Pass two files to compare, or none to auto-select the two most recent.", file=sys.stderr)
        sys.exit(1)

    # Auto-select two most recent quality result files
    quality_files = sorted(RESULTS_DIR.glob("quality-*.json"))
    if len(quality_files) < 2:
        print(f"Error: need at least 2 quality result files in {RESULTS_DIR}, found {len(quality_files)}.", file=sys.stderr)
        sys.exit(1)
    return quality_files[-2], quality_files[-1]


def print_diff(file1_path: Path, file2_path: Path):
    """Load two result JSON files and print a side-by-side comparison."""
    a = json.loads(file1_path.read_text())
    b = json.loads(file2_path.read_text())

    a_by_id = {r["id"]: r for r in a["results"]}
    b_by_id = {r["id"]: r for r in b["results"]}
    all_ids = list(dict.fromkeys(
        [r["id"] for r in a["results"]] + [r["id"] for r in b["results"]]
    ))

    # Header
    print(f"\n{_c(BOLD, 'Diff')} — comparing two eval runs")
    print(f"{'=' * 60}")

    def _meta_line(label, data, path):
        ts = data.get("timestamp", "?")[:19]
        model = data.get("model", "?")
        commit = data.get("git_commit", "?")
        skill = data.get("skill", "?")
        rate = data.get("pass_rate", 0) * 100
        passed = data.get("passed", 0)
        total = data.get("total", 0)
        print(f"\n  {_c(BOLD, label)}: {path.name}")
        print(f"    Timestamp: {ts}  Model: {model}  Commit: {commit}")
        print(f"    Skill: {skill}  Pass rate: {passed}/{total} ({rate:.1f}%)")

    _meta_line("A (older)", a, file1_path)
    _meta_line("B (newer)", b, file2_path)

    # Classify each eval
    fixed = []
    regressed = []
    unchanged_pass = 0
    unchanged_fail = 0
    only_a = []
    only_b = []

    for eid in all_ids:
        ra = a_by_id.get(eid)
        rb = b_by_id.get(eid)
        if ra and not rb:
            only_a.append(eid)
            continue
        if rb and not ra:
            only_b.append(eid)
            continue
        if not ra["passed"] and rb["passed"]:
            fixed.append(eid)
        elif ra["passed"] and not rb["passed"]:
            regressed.append(eid)
        elif rb["passed"]:
            unchanged_pass += 1
        else:
            unchanged_fail += 1

    # Delta
    a_rate = a.get("pass_rate", 0) * 100
    b_rate = b.get("pass_rate", 0) * 100
    delta = b_rate - a_rate
    sign = "+" if delta >= 0 else ""
    delta_color = GREEN if delta > 0 else RED if delta < 0 else DIM

    print(f"\n{_c(BOLD, 'Results:')}")
    print(f"  Pass rate: {a_rate:.1f}% → {b_rate:.1f}% ({_c(delta_color, f'{sign}{delta:.1f}%')})")

    if fixed:
        print(f"\n  {_c(GREEN, 'Fixed')} ({len(fixed)}):")
        for eid in fixed:
            detail = _format_failure_detail(a_by_id[eid])
            print(f"    {eid}  (was: {detail})" if detail else f"    {eid}")

    if regressed:
        print(f"\n  {_c(RED, 'Regressed')} ({len(regressed)}):")
        for eid in regressed:
            detail = _format_failure_detail(b_by_id[eid])
            print(f"    {eid}  ({detail})" if detail else f"    {eid}")

    print(f"\n  Unchanged: {unchanged_pass} pass, {unchanged_fail} fail")

    if only_a:
        print(f"  Only in A: {', '.join(only_a)}")
    if only_b:
        print(f"  Only in B: {', '.join(only_b)}")

    # Per-cluster breakdown if both have cluster data
    clusters = {}
    for eid in all_ids:
        ra = a_by_id.get(eid)
        rb = b_by_id.get(eid)
        if not ra or not rb:
            continue
        cluster = ra.get("cluster") or rb.get("cluster") or "uncategorized"
        if cluster not in clusters:
            clusters[cluster] = {"a_pass": 0, "b_pass": 0, "total": 0}
        clusters[cluster]["total"] += 1
        if ra["passed"]:
            clusters[cluster]["a_pass"] += 1
        if rb["passed"]:
            clusters[cluster]["b_pass"] += 1

    if len(clusters) > 1:
        print(f"\n  {_c(BOLD, 'Per-cluster:')}")
        _print_cluster_table(clusters, col_a="A", col_b="B")

    print()


def print_ablation_comparison(
    skill_results: list[dict],
    baseline_results: list[dict],
    evals: list[dict],
    skill_evals: list[dict] = None,
    baseline_evals: list[dict] = None,
):
    """Print side-by-side comparison of skill vs baseline (no-skill) results.

    When run with --parallel, results may arrive out of order. If skill_evals
    and baseline_evals are provided, results are re-indexed by eval ID to
    ensure correct alignment.
    """
    # Build lookup dicts keyed by eval ID for correct alignment
    if skill_evals is not None:
        skill_by_id = {e["id"]: r for e, r in zip(skill_evals, skill_results)}
    else:
        skill_by_id = {e["id"]: r for e, r in zip(evals, skill_results)}

    if baseline_evals is not None:
        baseline_by_id = {e["id"]: r for e, r in zip(baseline_evals, baseline_results)}
    else:
        baseline_by_id = {e["id"]: r for e, r in zip(evals, baseline_results)}

    skill_pass = sum(1 for r in skill_by_id.values() if r["passed"])
    baseline_pass = sum(1 for r in baseline_by_id.values() if r["passed"])
    total = len(evals)

    skill_rate = (skill_pass / total * 100) if total else 0
    baseline_rate = (baseline_pass / total * 100) if total else 0
    delta = skill_rate - baseline_rate

    # Categorize each eval
    essential = []   # baseline fails, skill passes
    both_pass = []   # both pass
    both_fail = []   # both fail — still need work
    harmful = []     # baseline passes, skill fails

    for e in evals:
        eid = e["id"]
        sr = skill_by_id.get(eid)
        br = baseline_by_id.get(eid)
        if sr is None or br is None:
            continue
        if not br["passed"] and sr["passed"]:
            essential.append(eid)
        elif br["passed"] and not sr["passed"]:
            harmful.append(eid)
        elif sr["passed"]:
            both_pass.append(eid)
        else:
            both_fail.append(eid)

    print(f"\n{'=' * 60}")
    print(f"{_c(BOLD, 'Ablation Comparison')} — skill vs no-skill baseline")
    print(f"{'=' * 60}")

    sign = "+" if delta >= 0 else ""
    delta_color = GREEN if delta > 0 else RED if delta < 0 else DIM
    print(f"\n  With skill:    {_c(BOLD, f'{skill_pass}/{total}')} ({skill_rate:.1f}%)")
    print(f"  Without skill: {_c(BOLD, f'{baseline_pass}/{total}')} ({baseline_rate:.1f}%)")
    print(f"  Skill lift:    {_c(delta_color, f'{sign}{delta:.1f}%')}")

    print(f"\n  {_c(BOLD, 'Breakdown:')}")
    print(f"    {_c(GREEN, 'Skill-essential')} (baseline fails, skill passes): {len(essential)}")
    print(f"    {_c(DIM, 'Both pass')}        (skill not needed):              {len(both_pass)}")
    print(f"    {_c(YELLOW, 'Both fail')}       (still need work):               {len(both_fail)}")
    print(f"    {_c(RED, 'Skill-harmful')}   (baseline passes, skill fails):  {len(harmful)}")

    if essential:
        print(f"\n  {_c(GREEN, 'Skill-essential evals')} — skill adds clear value:")
        for eid in essential:
            detail = _format_failure_detail(baseline_by_id[eid])
            print(f"    {eid}  (baseline was: {detail})" if detail else f"    {eid}")

    if harmful:
        print(f"\n  {_c(RED, 'Skill-harmful evals')} — investigate skill content:")
        for eid in harmful:
            detail = _format_failure_detail(skill_by_id[eid])
            print(f"    {eid}  ({detail})" if detail else f"    {eid}")

    if both_fail:
        print(f"\n  {_c(YELLOW, 'Both-fail evals')} — neither skill nor baseline covers these:")
        for eid in both_fail:
            detail = _format_failure_detail(skill_by_id[eid])
            print(f"    {eid}  ({detail})" if detail else f"    {eid}")

    # Per-cluster breakdown if clusters exist
    clusters = {}
    for e in evals:
        eid = e["id"]
        sr = skill_by_id.get(eid)
        br = baseline_by_id.get(eid)
        if sr is None or br is None:
            continue
        cluster = e.get("cluster", "uncategorized")
        if cluster not in clusters:
            clusters[cluster] = {"a_pass": 0, "b_pass": 0, "total": 0}
        clusters[cluster]["total"] += 1
        if sr["passed"]:
            clusters[cluster]["a_pass"] += 1
        if br["passed"]:
            clusters[cluster]["b_pass"] += 1

    if len(clusters) > 1:
        print(f"\n  {_c(BOLD, 'Per-cluster lift:')}")
        _print_cluster_table(clusters, col_a="Skill", col_b="Base", delta_label="Lift")

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
    now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")
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
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    filename = f"trigger-{timestamp}.json"
    path = RESULTS_DIR / filename

    total = len(grades)
    passed = sum(1 for g in grades if g["passed"])

    output = {
        "timestamp": now.isoformat(),
        "git_commit": _get_git_commit(),
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
