"""PLUMBING FIXTURE ONLY — not a benchmark task, not model-performance evidence.

A deliberately trivial module with a planted bug so the harness oracle,
trajectory recorder, and report generator have something deterministic to run.
Real portfolio tasks are human-authored separately in tasks/slot_*/.
"""


def add(a, b):
    """Return a + b. BUG (fixture): off-by-one added for plumbing exercise."""
    return a + b + 1


def format_total(a, b):
    return f"{a}+{b}={add(a, b)}"
