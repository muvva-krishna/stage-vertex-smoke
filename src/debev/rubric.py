"""100-point task rubric (rubric v1.0.0).

Components (reported separately and as a total):
  functional_correctness  50 pts  MACHINE  (evaluator test groups)
  root_cause_diagnosis    20 pts  HUMAN    (placeholder until task authored)
  compatibility_regression 15 pts MACHINE  (existing-interface checks)
  constraint_compliance   10 pts  MACHINE  (evaluator-file/constraint checks)
  verification_reporting   5 pts  MIXED    (machine: ran checks; human: accuracy)

Efficiency (tool calls, tests run, tokens, wall-clock, retries) is reported
separately and never folded into the correctness total.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RUBRIC_VERSION = "1.0.0"

WEIGHTS = {
    "functional_correctness": 50,
    "root_cause_diagnosis": 20,
    "compatibility_regression": 15,
    "constraint_compliance": 10,
    "verification_reporting": 5,
}

GRADE_MODE = {
    "functional_correctness": "machine",
    "root_cause_diagnosis": "human",
    "compatibility_regression": "machine",
    "constraint_compliance": "machine",
    "verification_reporting": "mixed",
}

FAILURE_TAXONOMY = (
    "missed_evidence",
    "misread_evidence",
    "wrong_causal_hypothesis",
    "incomplete_repair",
    "regression",
    "constraint_violation",
    "inadequate_verification",
    "inaccurate_final_report",
)


@dataclass
class ComponentScore:
    component: str
    points: float
    max_points: int
    grade_mode: str
    detail: str = ""


@dataclass
class TaskScore:
    task_id: str
    condition: str
    run_id: str
    components: list[ComponentScore] = field(default_factory=list)
    total: float = 0.0
    passed: bool = False  # correctness pass = functional full marks (see docs/rubric.md)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "condition": self.condition,
            "run_id": self.run_id,
            "components": [
                {
                    "component": c.component,
                    "points": c.points,
                    "max_points": c.max_points,
                    "grade_mode": c.grade_mode,
                    "detail": c.detail,
                }
                for c in self.components
            ],
            "total": self.total,
            "passed": self.passed,
        }


def score_machine_portion(
    task_id: str,
    condition: str,
    run_id: str,
    functional_groups: list[dict],
    functional_weights: dict[str, float] | None,
    compat_groups: list[dict],
    constraint_checks: list[dict],
    verification_ran: bool,
) -> TaskScore:
    """Score the machine-graded portion. Human-graded components are 0.0 with
    an explicit 'pending human grade' marker (never invented).

    verification_ran must reflect STRUCTURED agent verification (a
    `verification` event or a `test_run` with a PASS/FAIL/ERROR/INCONCLUSIVE
    result) — never a bare shell command, and never the evaluator's own
    oracle run. The caller computes it; see cli._agent_verification_ran.
    """
    functional_weights = functional_weights or {}

    def group_points(groups: list[dict], maximum: int, weights: dict | None = None):
        if not groups:
            return 0.0, "no groups reported"
        if weights:
            total_w = sum(weights.get(g["group"], 1.0) for g in groups)
            earned_w = sum(
                weights.get(g["group"], 1.0) for g in groups if g.get("passed")
            )
            pts = maximum * earned_w / total_w if total_w else 0.0
        else:
            pts = maximum * sum(1 for g in groups if g.get("passed")) / len(groups)
        detail = "; ".join(
            f"{g['group']}={'PASS' if g.get('passed') else 'FAIL'}" for g in groups
        )
        return round(pts, 2), detail

    f_pts, f_detail = group_points(functional_groups, 50, functional_weights or None)
    c_pts, c_detail = group_points(compat_groups, 15)
    if not constraint_checks:
        k_pts, k_detail = 0.0, "no constraint checks reported"
    else:
        ok = all(c.get("passed", False) for c in constraint_checks)
        k_pts = 10.0 if ok else 0.0
        k_detail = "; ".join(
            f"{c.get('name', '?')}={'PASS' if c.get('passed') else 'FAIL'}"
            for c in constraint_checks
        )
    v_pts = 2.5 if verification_ran else 0.0
    v_detail = (
        "machine portion: structured agent verification observed "
        "(verification event or test_run with a verdict; oracle run excluded)"
        if verification_ran
        else "machine portion: no structured agent verification observed; "
        "human accuracy grade pending"
    )
    comps = [
        ComponentScore("functional_correctness", f_pts, 50, "machine", f_detail),
        ComponentScore(
            "root_cause_diagnosis", 0.0, 20, "human", "PENDING HUMAN GRADE (placeholder)"
        ),
        ComponentScore("compatibility_regression", c_pts, 15, "machine", c_detail),
        ComponentScore("constraint_compliance", k_pts, 10, "machine", k_detail),
        ComponentScore("verification_reporting", v_pts, 5, "mixed", v_detail),
    ]
    total = round(sum(c.points for c in comps), 2)
    passed = bool(functional_groups) and all(g.get("passed") for g in functional_groups)
    return TaskScore(task_id, condition, run_id, comps, total, passed)


def is_pending_human_grade(score_dict: dict, component: str) -> bool:
    for c in score_dict.get("components", []):
        if c.get("component") == component:
            return "PENDING" in c.get("detail", "")
    return False


def apply_human_grade(
    score_dict: dict,
    diagnosis_pts: float | None = None,
    reporting_pts: float | None = None,
    grader: str = "",
    rationale: str = "",
) -> dict:
    """Persist a human grade onto a stored score dict.

    Only the human-owned portions may change: root_cause_diagnosis (0-20)
    and the human half of verification_reporting (+0-2.5 on top of the
    machine half). Machine components are never touched. Returns the
    updated dict with `human_grade` provenance attached.
    """
    if diagnosis_pts is not None and not 0 <= diagnosis_pts <= 20:
        raise ValueError("diagnosis_pts must be within 0..20")
    if reporting_pts is not None and not 0 <= reporting_pts <= 2.5:
        raise ValueError("reporting_pts must be within 0..2.5")
    if (diagnosis_pts is not None or reporting_pts is not None) and not grader:
        raise ValueError("grader name is required for a human grade")
    for c in score_dict.get("components", []):
        if c["component"] == "root_cause_diagnosis" and diagnosis_pts is not None:
            c["points"] = round(diagnosis_pts, 2)
            c["detail"] = f"human-graded by {grader}: {rationale[:500]}" or f"human-graded by {grader}"
        if c["component"] == "verification_reporting" and reporting_pts is not None:
            # machine half is 2.5 iff structured agent verification ran.
            machine_half = 2.5 if "structured agent verification observed" in c.get("detail", "") else 0.0
            c["points"] = round(machine_half + reporting_pts, 2)
            c["detail"] = (
                f"machine {machine_half}/2.5 + human {reporting_pts}/2.5 by {grader}: "
                f"{rationale[:300]}"
            )
    score_dict["total"] = round(
        sum(c["points"] for c in score_dict.get("components", [])), 2
    )
    score_dict["human_grade"] = {
        "grader": grader,
        "rationale": rationale[:1000],
        "diagnosis_pts": diagnosis_pts,
        "reporting_pts": reporting_pts,
    }
    return score_dict
