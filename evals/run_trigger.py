#!/usr/bin/env python3
"""Trigger precision eval runner for Buildkite skills.

Tests whether Claude selects the correct skill given all skill descriptions
and a user query. Presents all descriptions in a system prompt and asks the
model to return a JSON skill selection.

Usage:
    python evals/run_trigger.py
    python evals/run_trigger.py --skill buildkite-pipelines
    python evals/run_trigger.py --tag near-miss
    python evals/run_trigger.py --runs 3 --parallel 5
    python evals/run_trigger.py --holdout
    python evals/run_trigger.py --compare evals/results/trigger-prev.json

Requires: ANTHROPIC_API_KEY environment variable.
"""

import argparse
import asyncio
import json
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

import anthropic
from lib.dataset import (
    filter_trigger_evals,
    load_all_skill_descriptions,
    load_trigger_dataset,
)
from lib.graders import grade_trigger
from lib.reporter import (
    print_trigger_comparison,
    print_trigger_header,
    print_trigger_multi_result,
    print_trigger_result,
    print_trigger_summary,
    write_trigger_json_results,
)

DEFAULT_MODEL = "claude-sonnet-4-6"


def build_system_prompt(skill_descriptions: dict[str, str]) -> str:
    """Build the system prompt presenting all skill descriptions."""
    skills_block = "\n\n".join(
        f"### {name}\n{desc}" for name, desc in sorted(skill_descriptions.items())
    )

    return (
        "You are a skill router for Buildkite CI/CD. Given a user query, "
        "select the single most appropriate skill to handle it, or select "
        "null if no skill is relevant.\n\n"
        "Available skills:\n\n"
        f"{skills_block}\n\n"
        'Respond with ONLY a JSON object: {"skill": "<skill-name>"} or {"skill": null}\n'
        "Do not explain your reasoning."
    )


def parse_skill_selection(response: str, valid_skills: list[str]) -> str | None:
    """Extract skill name from model's JSON response.

    Tries JSON parsing first, then regex, then scans for known skill names.
    Returns None if no skill selected or unparseable.
    """
    text = response.strip()

    # Try JSON parse
    try:
        data = json.loads(text)
        skill = data.get("skill")
        if skill is None or skill == "null":
            return None
        if skill in valid_skills:
            return skill
    except (json.JSONDecodeError, AttributeError):
        pass

    # Try regex for {"skill": "..."} pattern
    match = re.search(r'"skill"\s*:\s*"([^"]+)"', text)
    if match:
        skill = match.group(1)
        if skill in valid_skills:
            return skill

    # Try regex for null
    match = re.search(r'"skill"\s*:\s*null', text)
    if match:
        return None

    # Scan for known skill names in the text
    for skill in valid_skills:
        if skill in text:
            return skill

    print(
        f"  WARNING: Could not parse skill from response: {text[:100]}", file=sys.stderr
    )
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run trigger precision evals for Buildkite skills"
    )
    p.add_argument(
        "--skill", help="Filter to evals targeting a specific skill (by expected_skill)"
    )
    p.add_argument("--tag", action="append", help="Filter by tag (can repeat)")
    p.add_argument("--id", help="Comma-separated eval IDs to run")
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Runs per query for trigger rate (default: 1, max 5)",
    )
    p.add_argument(
        "--parallel",
        type=int,
        default=5,
        metavar="N",
        help="Run N evals concurrently (default: 5)",
    )
    p.add_argument(
        "--holdout", action="store_true", help="Only run holdout split (40%%)"
    )
    p.add_argument(
        "--compare",
        metavar="FILE",
        help="Compare against a previous trigger results JSON file",
    )
    p.add_argument("--no-save", action="store_true", help="Don't save results to JSON")
    p.add_argument(
        "--show-responses", action="store_true", help="Print raw model responses"
    )
    return p.parse_args()


async def run_single_trigger(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_prompt: str,
    query: str,
) -> str:
    """Send a single query and return the raw response text."""
    response = await client.messages.create(
        model=model,
        max_tokens=100,
        system=system_prompt,
        messages=[{"role": "user", "content": query}],
    )
    return response.content[0].text


async def run_trigger_eval(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_prompt: str,
    eval_entry: dict,
    valid_skills: list[str],
    runs: int,
) -> tuple[dict, dict | list[dict], str]:
    """Run a trigger eval (possibly multiple times).

    Returns (eval_entry, grade_or_grades, last_response_text).
    When runs=1, grade is a single dict. When runs>1, it's a list.
    """
    if runs == 1:
        text = await run_single_trigger(
            client, model, system_prompt, eval_entry["query"]
        )
        selected = parse_skill_selection(text, valid_skills)
        grade = grade_trigger(selected, eval_entry)
        return eval_entry, grade, text
    else:
        grades = []
        last_text = ""
        for _ in range(runs):
            text = await run_single_trigger(
                client, model, system_prompt, eval_entry["query"]
            )
            last_text = text
            selected = parse_skill_selection(text, valid_skills)
            grades.append(grade_trigger(selected, eval_entry))
        return eval_entry, grades, last_text


async def run_batch(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_prompt: str,
    evals: list[dict],
    valid_skills: list[str],
    parallel: int,
    runs: int,
    show_responses: bool,
) -> tuple[list[dict], list[dict]]:
    """Run all trigger evals with concurrency. Returns (grades, evals_in_order).

    For multi-run mode, grades are aggregated (majority vote).
    """
    semaphore = asyncio.Semaphore(parallel)

    async def run_with_semaphore(eval_entry):
        async with semaphore:
            return await run_trigger_eval(
                client, model, system_prompt, eval_entry, valid_skills, runs
            )

    tasks = [run_with_semaphore(e) for e in evals]

    final_grades = []
    ordered_evals = []

    for coro in asyncio.as_completed(tasks):
        eval_entry, grade_or_grades, response_text = await coro
        ordered_evals.append(eval_entry)

        if runs == 1:
            final_grades.append(grade_or_grades)
            print_trigger_result(eval_entry, grade_or_grades)
        else:
            # Multi-run: use majority vote for the aggregate grade
            run_grades = grade_or_grades
            correct_count = sum(1 for g in run_grades if g["passed"])
            # Use the most common selection as the aggregate
            selections = {}
            for g in run_grades:
                s = g["selected_skill"]
                selections[s] = selections.get(s, 0) + 1
            majority_skill = max(selections, key=selections.get)
            aggregate = grade_trigger(majority_skill, eval_entry)
            aggregate["trigger_rate"] = correct_count / len(run_grades)
            aggregate["run_details"] = run_grades
            final_grades.append(aggregate)
            print_trigger_multi_result(eval_entry, run_grades)

        if show_responses:
            print(f"        Response: {response_text}")
            print()

    return final_grades, ordered_evals


def main():
    args = parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Error: ANTHROPIC_API_KEY environment variable is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.runs < 1 or args.runs > 5:
        print("Error: --runs must be between 1 and 5.", file=sys.stderr)
        sys.exit(1)

    # Load skill descriptions
    skill_descriptions = load_all_skill_descriptions()
    skill_names = sorted(skill_descriptions.keys())

    if not skill_descriptions:
        print("Error: No skills found with descriptions.", file=sys.stderr)
        sys.exit(1)

    # Load and filter trigger dataset
    all_evals = load_trigger_dataset()
    ids = args.id.split(",") if args.id else None
    evals = filter_trigger_evals(
        all_evals,
        skill=args.skill,
        tags=args.tag,
        ids=ids,
        holdout=args.holdout,
    )

    if not evals:
        print(f"No trigger evals found matching filters.", file=sys.stderr)
        sys.exit(1)

    # Build system prompt
    system_prompt = build_system_prompt(skill_descriptions)

    # Build filter description
    filter_parts = []
    if args.skill:
        filter_parts.append(f"expected_skill={args.skill}")
    if args.tag:
        filter_parts.append(f"tags={','.join(args.tag)}")
    if args.id:
        filter_parts.append(f"ids={args.id}")
    if args.holdout:
        filter_parts.append("holdout=true")

    print_trigger_header(
        args.model,
        len(evals),
        len(skill_names),
        ", ".join(filter_parts),
        args.runs,
    )

    # Run evals (always async for simplicity since responses are tiny)
    client = anthropic.AsyncAnthropic()
    grades, ordered_evals = asyncio.run(
        run_batch(
            client,
            args.model,
            system_prompt,
            evals,
            skill_names,
            args.parallel,
            args.runs,
            args.show_responses,
        )
    )

    # Summary
    print_trigger_summary(grades, ordered_evals, skill_names)

    # Save results
    if not args.no_save:
        result_path = write_trigger_json_results(
            grades,
            ordered_evals,
            args.model,
            skill_names,
            args.runs,
        )
        print(f"Results saved to: {result_path}")

    # Compare
    if args.compare:
        print_trigger_comparison(grades, ordered_evals, args.compare)

    # Exit with non-zero if any failures
    if any(not g["passed"] for g in grades):
        sys.exit(1)


if __name__ == "__main__":
    main()
