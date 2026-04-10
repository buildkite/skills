"""Grading functions for eval responses."""


def check_contains(response: str, expected: list[str]) -> tuple[list[str], list[str]]:
    """Check which expected terms appear in the response (case-insensitive).

    Returns (matched, missed) lists.
    """
    response_lower = response.lower()
    matched = []
    missed = []
    for term in expected:
        # Support alternation with | (e.g. "latest attempt|final attempt")
        alternatives = [t.strip() for t in term.split("|")]
        if any(alt.lower() in response_lower for alt in alternatives):
            matched.append(term)
        else:
            missed.append(term)
    return matched, missed


def check_not_contains(response: str, not_expected: list[str]) -> list[str]:
    """Check which forbidden terms appear in the response.

    Returns list of violations (terms that were found but shouldn't be).
    """
    response_lower = response.lower()
    return [term for term in not_expected if term.lower() in response_lower]


def grade_eval(response: str, eval_entry: dict) -> dict:
    """Grade a single eval response against its expected criteria.

    Returns dict with: passed, contains_matched, contains_missed,
    not_contains_violated, total_expected, response_length.
    """
    expected = eval_entry.get("expected_contains", [])
    not_expected = eval_entry.get("expected_not_contains", [])

    matched, missed = check_contains(response, expected)
    violations = check_not_contains(response, not_expected)

    passed = len(missed) == 0 and len(violations) == 0

    return {
        "passed": passed,
        "contains_matched": matched,
        "contains_missed": missed,
        "not_contains_violated": violations,
        "total_expected": len(expected),
        "response_length": len(response),
        "response": response,
    }


# --- Trigger eval grading ---


def grade_trigger(selected_skill: str | None, eval_entry: dict) -> dict:
    """Grade a trigger eval result.

    Returns dict with: passed, selected_skill, expected_skill,
    correct_selection, is_false_positive, is_false_negative, expected_not_violations.
    """
    expected = eval_entry.get("expected_skill")
    expected_not = eval_entry.get("expected_not_skills", [])

    correct = (selected_skill == expected)
    not_violations = [s for s in expected_not if selected_skill == s]
    passed = correct and len(not_violations) == 0

    return {
        "passed": passed,
        "selected_skill": selected_skill,
        "expected_skill": expected,
        "correct_selection": correct,
        "expected_not_violations": not_violations,
        "is_false_positive": expected is None and selected_skill is not None,
        "is_false_negative": expected is not None and selected_skill is None,
    }
