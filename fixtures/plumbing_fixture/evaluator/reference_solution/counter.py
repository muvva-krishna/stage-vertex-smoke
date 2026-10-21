"""Human-authored reference solution overlay (PLUMBING FIXTURE ONLY).

Files here overlay the repo workspace during `audit-task` to prove the
oracle PASSes a correct fix. Never staged into agent workspaces or runs.
"""


def add(a, b):
    """Return a + b."""
    return a + b


def format_total(a, b):
    return f"{a}+{b}={add(a, b)}"
