"""Partial-fix probe (PLUMBING FIXTURE ONLY): docstring-only edit.

Keeps the off-by-one. The oracle must still FAIL on this overlay —
otherwise it would be matching text rather than behavior.
"""


def add(a, b):
    """Return a + b. BUG (fixture): off-by-one added for plumbing exercise."""
    return a + b + 1


def format_total(a, b):
    return f"{a}+{b}={add(a, b)}"
