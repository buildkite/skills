#!/usr/bin/env python3
"""
Evaluate a GHA-to-Buildkite conversion attempt against the rubric.

Loads rubric.yaml, checks each category, computes a weighted total score,
and writes a detailed JSON result file.

Uses the `bk` CLI for live Buildkite verification (clusters, pipelines, builds).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


# --- bk CLI helper ---


def _bk(args: list[str], timeout: int = 15) -> dict | list | None:
    """Run a bk CLI command with --json output. Returns parsed JSON or None on failure."""
    bk_path = shutil.which("bk")
    if not bk_path:
        return None
    cmd = [bk_path] + args + ["-o", "json", "--no-input"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def _bk_text(args: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Run a bk CLI command and return (returncode, stdout, stderr)."""
    bk_path = shutil.which("bk")
    if not bk_path:
        return (1, "", "bk not found")
    cmd = [bk_path] + args + ["--no-input"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (result.returncode, result.stdout, result.stderr)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return (1, "", str(e))


# --- File helpers ---


def load_rubric(rubric_path: Path) -> dict:
    """Load the evaluation rubric from YAML."""
    with open(rubric_path, "r") as f:
        return yaml.safe_load(f)


def collect_pipeline_files(express_dir: Path) -> list[Path]:
    """Find all YAML files under .buildkite/ in the express directory."""
    buildkite_dir = express_dir / ".buildkite"
    files = []
    for pattern in ("*.yml", "*.yaml"):
        files.extend(buildkite_dir.glob(pattern))
    return sorted(files)


def read_pipeline_content(files: list[Path]) -> str:
    """Read and concatenate all pipeline file contents."""
    parts = []
    for f in files:
        try:
            parts.append(f.read_text())
        except OSError:
            pass
    return "\n".join(parts)


# --- Category evaluators (file-based) ---


def evaluate_file_existence(express_dir: Path, rubric_cat: dict) -> dict:
    """Check if expected pipeline files exist."""
    expected = rubric_cat["expected_files"]
    found = []
    missing = []
    for rel in expected:
        path = express_dir / rel
        if path.exists():
            found.append(rel)
        else:
            missing.append(rel)

    all_files = collect_pipeline_files(express_dir)
    extra = []
    expected_set = {str(express_dir / e) for e in expected}
    for f in all_files:
        if str(f) not in expected_set:
            extra.append(str(f.relative_to(express_dir)))

    total = len(expected)
    score = (len(found) / total * 100) if total > 0 else 0

    return {
        "score": round(score, 1),
        "details": {
            "expected": expected,
            "found": found,
            "missing": missing,
            "extra_files": extra,
        },
    }


def evaluate_yaml_validity(express_dir: Path, _rubric_cat: dict) -> dict:
    """Check pipeline YAML validity using bk pipeline validate (local, no API needed)."""
    files = collect_pipeline_files(express_dir)
    if not files:
        return {
            "score": 0,
            "details": {"message": "No pipeline files found", "results": []},
        }

    results = []
    valid_count = 0

    for f in files:
        entry = {
            "file": str(f.relative_to(express_dir)),
            "valid_yaml": False,
            "has_steps": False,
            "bk_validate": None,
        }

        # First: check basic YAML structure
        try:
            content = yaml.safe_load(f.read_text())
            entry["valid_yaml"] = True
            if isinstance(content, dict) and "steps" in content:
                entry["has_steps"] = True
            else:
                entry["error"] = "Missing top-level 'steps' key"
        except yaml.YAMLError as e:
            entry["error"] = str(e)
            results.append(entry)
            continue

        # Second: run bk pipeline validate for deeper schema check
        rc, stdout, stderr = _bk_text(["pipeline", "validate", "--file", str(f)])
        if rc == 0:
            entry["bk_validate"] = "passed"
            if entry["has_steps"]:
                valid_count += 1
        else:
            entry["bk_validate"] = "failed"
            entry["bk_validate_error"] = stderr.strip() or stdout.strip()
            # Still count as valid if YAML parses and has steps (bk validate is stricter)
            if entry["has_steps"]:
                valid_count += 1

        results.append(entry)

    score = (valid_count / len(files) * 100) if files else 0
    return {
        "score": round(score, 1),
        "details": {"total_files": len(files), "valid_with_steps": valid_count, "results": results},
    }


def evaluate_workflow_coverage(express_dir: Path, rubric_cat: dict) -> dict:
    """Check that expected workflow features appear in pipeline content."""
    files = collect_pipeline_files(express_dir)
    combined = read_pipeline_content(files).lower()

    expected_features = rubric_cat["expected_features"]
    total_features = 0
    found_features = 0
    per_workflow = {}

    for workflow, features in expected_features.items():
        workflow_found = []
        workflow_missing = []
        for feat in features:
            total_features += 1
            if feat.lower() in combined:
                found_features += 1
                workflow_found.append(feat)
            else:
                workflow_missing.append(feat)
        per_workflow[workflow] = {"found": workflow_found, "missing": workflow_missing}

    score = (found_features / total_features * 100) if total_features > 0 else 0
    return {
        "score": round(score, 1),
        "details": {
            "total_features": total_features,
            "found_features": found_features,
            "per_workflow": per_workflow,
        },
    }


def evaluate_matrix_builds(express_dir: Path, _rubric_cat: dict) -> dict:
    """Check for Buildkite matrix syntax in pipeline files."""
    files = collect_pipeline_files(express_dir)
    combined = read_pipeline_content(files).lower()

    has_matrix = "matrix:" in combined
    has_adjustments = "adjustments:" in combined or "setup:" in combined

    if has_matrix:
        score = 100
        detail = "Found matrix: syntax"
        if has_adjustments:
            detail += " with adjustments/setup"
    else:
        node_version_count = combined.count("node") + combined.count("node_version")
        if node_version_count >= 2:
            score = 50
            detail = "Multiple node version references found but no matrix: syntax"
        else:
            score = 0
            detail = "No matrix syntax or multiple version references found"

    return {
        "score": score,
        "details": {
            "has_matrix": has_matrix,
            "has_adjustments": has_adjustments,
            "detail": detail,
        },
    }


def evaluate_buildkite_idioms(express_dir: Path, rubric_cat: dict) -> dict:
    """Check how many expected Buildkite patterns appear in pipeline content."""
    files = collect_pipeline_files(express_dir)
    combined = read_pipeline_content(files).lower()

    expected = rubric_cat["expected_patterns"]
    found = []
    missing = []
    for pattern in expected:
        if pattern.lower() in combined:
            found.append(pattern)
        else:
            missing.append(pattern)

    total = len(expected)
    score = (len(found) / total * 100) if total > 0 else 0
    return {
        "score": round(score, 1),
        "details": {"expected": expected, "found": found, "missing": missing},
    }


def evaluate_conversion_notes(express_dir: Path, rubric_cat: dict) -> dict:
    """Check if CONVERSION_NOTES.md exists with meaningful content."""
    min_length = rubric_cat.get("min_length", 200)

    candidates = [
        express_dir / "CONVERSION_NOTES.md",
        express_dir / ".buildkite" / "CONVERSION_NOTES.md",
    ]

    for path in candidates:
        if path.exists():
            content = path.read_text()
            length = len(content)
            if length >= min_length:
                return {
                    "score": 100,
                    "details": {
                        "path": str(path.relative_to(express_dir)),
                        "length": length,
                        "min_length": min_length,
                    },
                }
            else:
                return {
                    "score": 50,
                    "details": {
                        "path": str(path.relative_to(express_dir)),
                        "length": length,
                        "min_length": min_length,
                        "message": f"File exists but only {length} chars (minimum {min_length})",
                    },
                }

    return {
        "score": 0,
        "details": {
            "message": "CONVERSION_NOTES.md not found",
            "searched": [str(p.relative_to(express_dir)) for p in candidates],
        },
    }


def evaluate_no_anti_patterns(express_dir: Path, rubric_cat: dict) -> dict:
    """Check pipeline files for forbidden GHA syntax remnants."""
    files = collect_pipeline_files(express_dir)
    combined = read_pipeline_content(files)

    forbidden = rubric_cat["forbidden_patterns"]
    violations = []
    clean = []

    for pattern in forbidden:
        if pattern in combined:
            violations.append(pattern)
        else:
            clean.append(pattern)

    total = len(forbidden)
    violation_count = len(violations)
    score = max(0, 100 - (violation_count / total * 100)) if total > 0 else 100

    return {
        "score": round(score, 1),
        "details": {
            "violations": violations,
            "clean": clean,
            "violation_count": violation_count,
            "total_patterns": total,
        },
    }


# --- Category evaluators (bk CLI-based, live verification) ---


def evaluate_infrastructure_live(cluster_name: str, _rubric_cat: dict) -> dict:
    """Verify Buildkite resources actually exist using `bk` CLI."""
    if not shutil.which("bk"):
        return {"score": 0, "details": {"message": "bk CLI not found on PATH"}}

    checks_passed = 0
    total_checks = 3  # cluster, queues, pipelines
    details = {}

    # Check 1: Cluster exists (bk cluster list -o json, then search)
    clusters = _bk(["cluster", "list"]) or []
    matching_cluster = None
    for c in clusters:
        name = c.get("name", "") or c.get("key", "")
        if cluster_name in name.lower() or name.lower() in cluster_name.lower():
            matching_cluster = c
            break

    if matching_cluster:
        checks_passed += 1
        details["cluster"] = {
            "found": True,
            "name": matching_cluster.get("name"),
            "id": matching_cluster.get("id", ""),
            "description": matching_cluster.get("description", ""),
        }

        # Check 2: Queues exist -- use bk cluster view to see queue info
        cluster_id = matching_cluster.get("id", "")
        cluster_detail = _bk(["cluster", "view", cluster_id]) if cluster_id else None
        queues = []
        if isinstance(cluster_detail, dict):
            queues = cluster_detail.get("queues", [])
        details["queues"] = {"count": len(queues), "found": [q.get("key", "") for q in queues]}
        if len(queues) >= 1:
            checks_passed += 1
    else:
        details["cluster"] = {"found": False, "searched_for": cluster_name}
        details["queues"] = {"found": [], "count": 0}

    # Check 3: Pipelines exist with "ralph" or "express" in the name
    pipelines = _bk(["pipeline", "list", "--name", "ralph"]) or []
    if not pipelines:
        pipelines = _bk(["pipeline", "list", "--name", "express"]) or []
    ralph_slugs = [p.get("slug", "") for p in pipelines]
    details["pipelines"] = {"found": ralph_slugs, "count": len(ralph_slugs)}
    if len(ralph_slugs) >= 1:
        checks_passed += 1

    score = (checks_passed / total_checks * 100) if total_checks > 0 else 0
    return {"score": round(score, 1), "details": details}


def evaluate_builds_ran(cluster_name: str, _rubric_cat: dict) -> dict:
    """Check if any builds were triggered using `bk build list`."""
    if not shutil.which("bk"):
        return {"score": 0, "details": {"message": "bk CLI not found on PATH"}}

    # Find ralph/express pipelines
    pipelines = _bk(["pipeline", "list", "--name", "ralph"]) or []
    if not pipelines:
        pipelines = _bk(["pipeline", "list", "--name", "express"]) or []

    if not pipelines:
        return {
            "score": 0,
            "details": {"message": "No matching pipelines found to check builds for"},
        }

    total_pipelines = len(pipelines)
    pipelines_with_builds = 0
    pipelines_with_terminal_builds = 0
    pipelines_with_passed_builds = 0
    build_details = []

    for p in pipelines:
        slug = p.get("slug", "")

        # bk build list --pipeline <slug> --limit 5
        builds = _bk(["build", "list", "--pipeline", slug, "--limit", "5"], timeout=20) or []

        pipeline_info = {
            "pipeline": slug,
            "total_builds": len(builds),
            "build_states": [],
            "has_passed_build": False,
        }

        if builds:
            pipelines_with_builds += 1
            for b in builds:
                state = b.get("state", "unknown")
                pipeline_info["build_states"].append({
                    "number": b.get("number"),
                    "state": state,
                    "message": b.get("message", "")[:80],
                })

            # Check for terminal and passing builds
            states_seen = {b.get("state", "unknown") for b in builds}
            terminal_states = {"passed", "failed", "canceled", "not_run"}
            if states_seen & terminal_states:
                pipelines_with_terminal_builds += 1
            if "passed" in states_seen:
                pipelines_with_passed_builds += 1
                pipeline_info["has_passed_build"] = True

        build_details.append(pipeline_info)

    # 3-tier scoring:
    #   33% for having builds triggered (any pipeline has >= 1 build)
    #   33% for builds reaching a terminal state (finished running)
    #   34% for at least one build passing (the pipeline actually works)
    score = 0
    if pipelines_with_builds > 0:
        score += 33
    if pipelines_with_terminal_builds > 0:
        score += 33
    if pipelines_with_passed_builds > 0:
        score += 34

    return {
        "score": score,
        "details": {
            "pipelines_checked": total_pipelines,
            "pipelines_with_builds": pipelines_with_builds,
            "pipelines_with_terminal_builds": pipelines_with_terminal_builds,
            "pipelines_with_passed_builds": pipelines_with_passed_builds,
            "builds": build_details,
        },
    }


# --- Evaluator dispatch ---

# Functions that take (express_dir, rubric_cat)
FILE_EVALUATORS = {
    "file_existence": evaluate_file_existence,
    "yaml_validity": evaluate_yaml_validity,
    "workflow_coverage": evaluate_workflow_coverage,
    "matrix_builds": evaluate_matrix_builds,
    "buildkite_idioms": evaluate_buildkite_idioms,
    "conversion_notes": evaluate_conversion_notes,
    "no_anti_patterns": evaluate_no_anti_patterns,
}

# Categories that need bk CLI (cluster_name, rubric_cat)
BK_EVALUATORS = {
    "infrastructure_live": evaluate_infrastructure_live,
    "builds_ran": evaluate_builds_ran,
}


def run_evaluation(
    express_dir: Path,
    rubric: dict,
    cluster_name: str | None = None,
) -> dict:
    """Run all evaluation categories and return the full result."""
    categories_result = {}
    weighted_total = 0.0

    for cat_name, cat_config in rubric["categories"].items():
        weight = cat_config["weight"]

        if cat_name in BK_EVALUATORS:
            if cluster_name:
                result = BK_EVALUATORS[cat_name](cluster_name, cat_config)
            else:
                result = {
                    "score": 0,
                    "details": {"message": f"Skipped: --cluster-name required for {cat_name}"},
                }
        elif cat_name in FILE_EVALUATORS:
            result = FILE_EVALUATORS[cat_name](express_dir, cat_config)
        else:
            result = {"score": 0, "details": {"error": f"No evaluator for {cat_name}"}}

        result["weight"] = weight
        categories_result[cat_name] = result
        weighted_total += result["score"] * weight / 100

    all_files = collect_pipeline_files(express_dir)
    files_found = [str(f.relative_to(express_dir)) for f in all_files]

    summary_parts = []
    for cat_name, cat_result in categories_result.items():
        summary_parts.append(f"{cat_name}: {cat_result['score']}/100 (weight {cat_result['weight']}%)")
    summary = f"Total: {round(weighted_total, 1)}/100. " + "; ".join(summary_parts)

    return {
        "total_score": round(weighted_total, 1),
        "categories": categories_result,
        "files_found": files_found,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate a GHA-to-Buildkite conversion attempt")
    parser.add_argument("--express-dir", required=True, help="Path to the Express.js checkout")
    parser.add_argument("--version", type=int, required=True, help="Iteration version number")
    parser.add_argument("--output", required=True, help="Path to write the JSON result")
    parser.add_argument("--cluster-name", default=None,
                        help="Buildkite cluster name for live verification (e.g. 'ralph-express-v1')")
    args = parser.parse_args()

    express_dir = Path(args.express_dir).resolve()
    if not express_dir.is_dir():
        print(f"Error: express-dir does not exist: {express_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve()

    rubric_path = Path(__file__).parent / "rubric.yaml"
    if not rubric_path.exists():
        print(f"Error: rubric not found at {rubric_path}", file=sys.stderr)
        sys.exit(1)
    rubric = load_rubric(rubric_path)

    result = run_evaluation(
        express_dir,
        rubric,
        cluster_name=args.cluster_name,
    )
    result["version"] = args.version
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    if args.cluster_name:
        result["cluster_name"] = args.cluster_name

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"\nEvaluation complete. Total score: {result['total_score']}/100")
    for cat_name, cat_result in result["categories"].items():
        s = cat_result["score"]
        w = cat_result["weight"]
        bar = "█" * int(s / 5) + "░" * (20 - int(s / 5))
        print(f"  {cat_name:<25s} {bar} {s:5.1f}/100 (×{w}%)")
    print(f"\nResult written to: {output_path}")


if __name__ == "__main__":
    main()
