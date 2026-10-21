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
  budgeting: {assumed_max_input_tokens_per_attempt,
              assumed_max_output_tokens_per_attempt,
              max_model_turns_per_attempt, max_retries_per_cell,
              spend_cap: {currency, amount},
              prices: {<model_id>: {input_per_1k, output_per_1k,
                                    currency, source: "user-supplied"}}}
  provider (per model): {kind: "openai-compatible", base_url,
                         env_key: "NAME_OF_ENV_VAR_HOLDING_KEY"}
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
            prov = m.get("provider", {}) or {}
            if prov.get("kind", "openai-compatible") != "openai-compatible":
                issues.append(PlanIssue(
                    "error", f"model tier {m.get('tier', '?')}: only provider kind "
                    "'openai-compatible' is supported"))
            if not prov.get("base_url") or str(prov.get("base_url", "")).startswith("TODO"):
                issues.append(PlanIssue(
                    "error", f"model tier {m.get('tier', '?')}: provider.base_url missing or placeholder"))
            if not prov.get("env_key") or str(prov.get("env_key", "")).startswith("TODO"):
                issues.append(PlanIssue(
                    "error", f"model tier {m.get('tier', '?')}: provider.env_key missing or "
                    "placeholder (name of the environment variable holding the credential)"))
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
    """Worst-case cost from USER-SUPPLIED prices only.

    Input and output tokens are capped and priced separately; the per-cell
    worst case assumes max_model_turns_per_attempt turns each hitting both
    caps, times (1 + max_retries_per_cell). Never guesses prices.

    The legacy single `assumed_max_tokens_per_attempt` field is rejected as
    ambiguous (it cannot be split into input vs output spend).
    """
    budgeting = plan.get("budgeting", {}) or {}
    prices = budgeting.get("prices", {}) or {}
    if "assumed_max_tokens_per_attempt" in budgeting:
        return {"computable": False,
                "reason": "legacy assumed_max_tokens_per_attempt is ambiguous; "
                          "use assumed_max_input/output_tokens_per_attempt"}
    cap_in = budgeting.get("assumed_max_input_tokens_per_attempt")
    cap_out = budgeting.get("assumed_max_output_tokens_per_attempt")
    turns = budgeting.get("max_model_turns_per_attempt", 1)
    retries = budgeting.get("max_retries_per_cell", 0)
    if not prices:
        return {"computable": False,
                "reason": "no user-supplied prices in plan.budgeting.prices"}
    if not cap_in or not cap_out:
        return {"computable": False,
                "reason": "set assumed_max_input_tokens_per_attempt and "
                          "assumed_max_output_tokens_per_attempt"}
    try:
        turns, retries, cap_in, cap_out = int(turns), int(retries), int(cap_in), int(cap_out)
    except (TypeError, ValueError):
        return {"computable": False, "reason": "token/turn budgets must be integers"}
    if turns < 1 or retries < 0 or cap_in < 1 or cap_out < 1:
        return {"computable": False, "reason": "token/turn budgets must be positive"}
    per_task = len(plan["conditions"]) * int(plan["repetitions"])
    out: dict[str, Any] = {"computable": True, "per_model": {}, "assumptions": {
        "max_input_tokens_per_attempt": cap_in,
        "max_output_tokens_per_attempt": cap_out,
        "max_model_turns_per_attempt": turns,
        "max_retries_per_cell": retries}}
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
        per_attempt = (cap_in / 1000 * float(p["input_per_1k"])
                       + cap_out / 1000 * float(p["output_per_1k"])) * turns * (1 + retries)
        cells = per_task * len(plan["tasks"])
        out["per_model"][m["model_id"]] = {
            "computable": True, "currency": p.get("currency", "?"),
            "upper_bound": round(per_attempt * cells, 2),
            "cells": cells,
        }
    return out


def check_spend_cap(plan: dict) -> list[PlanIssue]:
    """Execute mode requires an explicit user-set spend cap at or above the
    worst-case estimate. No cap, no paid execution."""
    issues: list[PlanIssue] = []
    budgeting = plan.get("budgeting", {}) or {}
    cap = budgeting.get("spend_cap", {}) or {}
    if not cap.get("amount"):
        issues.append(PlanIssue("error", "budgeting.spend_cap.amount is required for execution"))
        return issues
    est = cost_upper_bound(plan)
    if not est.get("computable"):
        issues.append(PlanIssue("error", f"cost not computable: {est.get('reason')}"))
        return issues
    for mid, c in est["per_model"].items():
        if not c.get("computable"):
            issues.append(PlanIssue(
                "error", f"cost not computable for {mid}: {c.get('reason')}"))
            continue
        if c.get("currency") != cap.get("currency"):
            issues.append(PlanIssue(
                "error", f"currency mismatch for {mid}: {c.get('currency')} vs cap {cap.get('currency')}"))
        elif c["upper_bound"] > float(cap["amount"]):
            issues.append(PlanIssue(
                "error", f"worst-case {c['upper_bound']} {c['currency']} for {mid} "
                f"exceeds spend cap {cap['amount']} {cap.get('currency')}"))
    return issues
