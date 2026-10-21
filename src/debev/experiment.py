"""Versioned experiment-plan format for the multi-model pilot matrix.

Plan schema v1 (`plan_version: "1.0.0"`):
  study: str
  tasks: [task_id, ...]            # must match tasks/<id>/manifest.json task_id
  models: [{tier, model_id, model_version, temperature, settings{}}]  # exactly 2
  harness: {name, version, tool_policy}
  conditions: [5 evidence conditions]
  repetitions: int >= 1
  seed: int
  randomize: bool
  limits: {max_tool_calls, max_wall_seconds, max_evidence_tokens, per_command_timeout}
  budgeting (optional): {assumed_max_tokens_per_attempt,
                         prices: {<model_id>: {input_per_1k, output_per_1k,
                                               currency, source: "user-supplied"}}}
  provenance: filled at plan time (harness commit, config hash)

The default planned matrix is 3 tasks x 5 conditions x 2 models x 3 reps
= 90 attempts (exploratory — three tasks support no population claims).
Every model runs every condition on every task; harness, tools, wording,
and limits stay constant. `expand_matrix` randomizes cell order by seed.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLAN_VERSION = "1.0.0"

EXPECTED_CONDITIONS = (
    "symptom_only",
    "repro_log",
    "state_snapshot",
    "code_note",
    "combined",
)


@dataclass
class PlanIssue:
    level: str  # "error" or "warning"
    message: str


def load_plan(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def plan_hash(plan: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()
    ).hexdigest()


def validate_plan(plan: dict, tasks_root: str | Path | None = None) -> list[PlanIssue]:
    issues: list[PlanIssue] = []
    if plan.get("plan_version") != PLAN_VERSION:
        issues.append(PlanIssue("error", f"plan_version must be {PLAN_VERSION!r}"))
    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list) or len(tasks) < 1:
        issues.append(PlanIssue("error", "tasks must be a non-empty list"))
    if len(set(tasks)) != len(tasks):
        issues.append(PlanIssue("error", "tasks contains duplicate IDs"))
    models = plan.get("models", [])
    if not isinstance(models, list) or len(models) != 2:
        issues.append(PlanIssue("error", "models must list exactly 2 model tiers"))
    else:
        for m in models:
            for k in ("tier", "model_id", "model_version"):
                if not m.get(k) or (isinstance(m.get(k), str) and m[k].startswith("TODO")):
                    issues.append(PlanIssue(
                        "error", f"model tier {m.get('tier', '?')}: {k} missing or placeholder"))
    conds = plan.get("conditions", [])
    if list(conds) != list(EXPECTED_CONDITIONS):
        issues.append(PlanIssue(
            "error", f"conditions must be exactly {list(EXPECTED_CONDITIONS)}"))
    reps = plan.get("repetitions", 0)
    if not isinstance(reps, int) or reps < 1:
        issues.append(PlanIssue("error", "repetitions must be an integer >= 1"))
    if reps == 1:
        issues.append(PlanIssue("warning", "single repetition: no within-cell variation visible"))
    if reps == 2:
        issues.append(PlanIssue("warning", "two repetitions lower precision; prefer 3 when cost permits"))
    harness = plan.get("harness", {})
    if not harness.get("name"):
        issues.append(PlanIssue("error", "harness.name missing (one shared harness required)"))
    limits = plan.get("limits", {})
    for k in ("max_tool_calls", "max_wall_seconds", "max_evidence_tokens"):
        if k not in limits:
            issues.append(PlanIssue("error", f"limits missing key: {k}"))
    if tasks_root is not None and isinstance(tasks, list):
        root = Path(tasks_root)
        for tid in tasks:
            tdir = root / tid
            manifest = tdir / "manifest.json"
            if not manifest.is_file():
                issues.append(PlanIssue("error", f"task dir missing: {tdir}"))
                continue
            try:
                data = json.loads(manifest.read_text())
            except json.JSONDecodeError as e:
                issues.append(PlanIssue("error", f"task {tid}: manifest unparsable ({e})"))
                continue
            if data.get("task_id") != tid:
                issues.append(PlanIssue(
                    "error", f"task {tid}: manifest task_id is {data.get('task_id')!r}"))
            missing = [c for c in EXPECTED_CONDITIONS if c not in data.get("conditions", [])]
            if missing:
                issues.append(PlanIssue(
                    "error", f"task {tid}: manifest lacks conditions {missing}"))
    return issues


def expand_matrix(plan: dict) -> list[dict[str, Any]]:
    """Full cell list: every task x condition x model x repetition.

    Repetitions are repeated attempts at the SAME cell, not independent
    tasks. Order randomized by plan seed when plan.randomize is true.
    """
    cells = [
        {"task": t, "condition": c, "model": m["model_id"],
         "tier": m["tier"], "repetition": r}
        for t in plan["tasks"]
        for c in plan["conditions"]
        for m in plan["models"]
        for r in range(plan["repetitions"])
    ]
    if plan.get("randomize", True):
        random.Random(plan.get("seed", 0)).shuffle(cells)
    return cells


def matrix_count(plan: dict) -> int:
    return len(plan.get("tasks", [])) * len(plan.get("conditions", [])) * \
        len(plan.get("models", [])) * int(plan.get("repetitions", 0))


def cost_upper_bound(plan: dict) -> dict[str, Any] | None:
    """Upper-bound cost from USER-SUPPLIED prices only. Returns None (with
    reason) unless prices and a token assumption are both present. Never
    guesses prices."""
    budgeting = plan.get("budgeting", {}) or {}
    prices = budgeting.get("prices", {}) or {}
    assumed = budgeting.get("assumed_max_tokens_per_attempt")
    if not prices:
        return {"computable": False,
                "reason": "no user-supplied prices in plan.budgeting.prices"}
    if not assumed:
        return {"computable": False,
                "reason": "no budgeting.assumed_max_tokens_per_attempt set"}
    per_task = len(plan["conditions"]) * int(plan["repetitions"])
    out: dict[str, Any] = {"computable": True, "per_model": {}}
    for m in plan["models"]:
        p = prices.get(m["model_id"])
        if not p:
            out["per_model"][m["model_id"]] = {"computable": False,
                                               "reason": "no price supplied"}
            continue
        if p.get("source") != "user-supplied":
            out["per_model"][m["model_id"]] = {"computable": False,
                                               "reason": "price source must be user-supplied"}
            continue
        per_attempt = assumed / 1000 * (float(p["input_per_1k"]) + float(p["output_per_1k"]))
        cells = per_task * len(plan["tasks"])
        out["per_model"][m["model_id"]] = {
            "computable": True, "currency": p.get("currency", "?"),
            "upper_bound": round(per_attempt * cells, 2),
            "cells": cells,
        }
    return out
