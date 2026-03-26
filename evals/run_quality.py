#!/usr/bin/env python3
"""Quality eval runner for Buildkite skills.

Runs eval questions against a skill's SKILL.md content via the Anthropic API,
then grades responses using string-match checks on expected_contains /
expected_not_contains terms.

Usage:
    python evals/run_quality.py --skill buildkite-pipelines
    python evals/run_quality.py --skill buildkite-pipelines --cluster pipeline-config
    python evals/run_quality.py --skill buildkite-pipelines --id pipeline-001,pipeline-006
    python evals/run_quality.py --skill buildkite-pipelines --compare evals/results/prev.json

Requires: ANTHROPIC_API_KEY environment variable.
"""

import argparse
import asyncio
import os
import sys

import anthropic

from lib.dataset import load_dataset, filter_evals, load_skill, skill_path
from lib.graders import grade_eval
from lib.reporter import (
    print_header,
    print_result,
    print_summary,
    write_json_results,
    print_comparison,
)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
SYSTEM_PREAMBLE = (
    "You are a helpful AI assistant specializing in Buildkite CI/CD. "
    "Answer the user's question using the skill content below as your primary knowledge source. "
    "Be specific, accurate, and actionable.\n\n"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run quality evals for a Buildkite skill")
    p.add_argument("--skill", required=True, help="Skill name (e.g. buildkite-pipelines)")
    p.add_argument("--cluster", help="Filter to a specific cluster")
    p.add_argument("--tag", action="append", help="Filter by tag (can repeat)")
    p.add_argument("--difficulty", help="Filter by difficulty level")
    p.add_argument("--id", help="Comma-separated eval IDs to run")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    p.add_argument("--compare", metavar="FILE", help="Compare against a previous results JSON file")
    p.add_argument("--parallel", type=int, default=1, metavar="N", help="Run N evals concurrently")
    p.add_argument("--no-save", action="store_true", help="Don't save results to JSON")
    p.add_argument("--show-responses", action="store_true", help="Print full model responses")
    return p.parse_args()


async def run_eval_async(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_message: str,
    eval_entry: dict,
) -> tuple[dict, dict, str]:
    """Run a single eval and return (eval_entry, grade, response_text)."""
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_message,
        messages=[{"role": "user", "content": eval_entry["question"]}],
    )
    text = response.content[0].text
    grade = grade_eval(text, eval_entry)
    return eval_entry, grade, text


async def run_batch(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_message: str,
    evals: list[dict],
    parallel: int,
    show_responses: bool,
) -> tuple[list[dict], list[dict]]:
    """Run all evals with concurrency limit. Returns (grades, evals_in_order)."""
    semaphore = asyncio.Semaphore(parallel)
    all_results = []

    async def run_with_semaphore(eval_entry):
        async with semaphore:
            return await run_eval_async(client, model, system_message, eval_entry)

    tasks = [run_with_semaphore(e) for e in evals]

    grades = []
    ordered_evals = []
    for coro in asyncio.as_completed(tasks):
        eval_entry, grade, response_text = await coro
        ordered_evals.append(eval_entry)
        grades.append(grade)
        print_result(eval_entry, grade)
        if show_responses:
            print(f"        Response: {response_text[:200]}...")
            print()

    return grades, ordered_evals


def run_sequential(
    client: anthropic.Anthropic,
    model: str,
    system_message: str,
    evals: list[dict],
    show_responses: bool,
) -> tuple[list[dict], list[dict]]:
    """Run evals sequentially. Returns (grades, evals_in_order)."""
    grades = []
    for eval_entry in evals:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_message,
            messages=[{"role": "user", "content": eval_entry["question"]}],
        )
        text = response.content[0].text
        grade = grade_eval(text, eval_entry)
        grades.append(grade)
        print_result(eval_entry, grade)
        if show_responses:
            print(f"        Response: {text[:200]}...")
            print()

    return grades, evals


def main():
    args = parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    # Load and filter dataset
    all_evals = load_dataset()
    ids = args.id.split(",") if args.id else None
    evals = filter_evals(
        all_evals,
        skill=args.skill,
        cluster=args.cluster,
        tags=args.tag,
        difficulty=args.difficulty,
        ids=ids,
    )

    if not evals:
        print(f"No evals found matching filters (skill={args.skill}).", file=sys.stderr)
        sys.exit(1)

    # Load skill content
    description, full_content = load_skill(args.skill)
    skill_size = len(full_content.encode())
    system_message = SYSTEM_PREAMBLE + full_content

    # Build filter description for header
    filter_parts = [f"primary_skill={args.skill}"]
    if args.cluster:
        filter_parts.append(f"cluster={args.cluster}")
    if args.tag:
        filter_parts.append(f"tags={','.join(args.tag)}")
    if args.difficulty:
        filter_parts.append(f"difficulty={args.difficulty}")
    if args.id:
        filter_parts.append(f"ids={args.id}")

    print_header(args.skill, skill_size, args.model, len(evals), ", ".join(filter_parts))

    # Run evals
    if args.parallel > 1:
        async_client = anthropic.AsyncAnthropic()
        grades, ordered_evals = asyncio.run(
            run_batch(async_client, args.model, system_message, evals, args.parallel, args.show_responses)
        )
    else:
        sync_client = anthropic.Anthropic()
        grades, ordered_evals = run_sequential(
            sync_client, args.model, system_message, evals, args.show_responses
        )

    # Summary
    print_summary(grades, ordered_evals)

    # Save results
    if not args.no_save:
        result_path = write_json_results(grades, ordered_evals, args.skill, args.model, skill_size)
        print(f"Results saved to: {result_path}")

    # Compare
    if args.compare:
        print_comparison(grades, ordered_evals, args.compare)

    # Exit with non-zero if any failures
    if any(not g["passed"] for g in grades):
        sys.exit(1)


if __name__ == "__main__":
    main()
