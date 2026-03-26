"""Grading functions for eval responses."""


def check_contains(response: str, expected: list[str]) -> tuple[list[str], list[str]]:
    """Check which expected terms appear in the response (case-insensitive).

    Returns (matched, missed) lists.
    """
    response_lower = response.lower()
    matched = []
    missed = []
    for term in expected:
        if term.lower() in response_lower:
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
