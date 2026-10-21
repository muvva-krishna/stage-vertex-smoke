"""Resumable frozen-plan matrix executor (dry-run | smoke | execute).

- dry-run: expansion, run IDs, paths, resume simulation, cost preflight.
  No provider calls, no staging beyond audits (audits are local-only).
- smoke: one plumbing-only attempt through the real ModelAgentRunner loop
  with a labeled loopback transport (no provider calls, no paid cost),
  then verifies toolkit mediation and fixture labeling.
- execute: paid provider calls. Refuses without --authorize-spend, a
  user-set spend cap covering the worst case, passing audits, and valid
  manifests. Fail closed everywhere; never substitutes models/settings.

State file (matrix_state.json): {plan_hash, cells: {key: {status, run_id,
attempts}}, spend: {model_id: {input_tokens, output_tokens, cost}},
currency}. Completed cells are never re-run on resume. A plan_hash
mismatch refuses to resume (use --fresh to restart deliberately).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from .experiment import (check_spend_cap, cost_upper_bound, expand_matrix,
                         load_plan, matrix_count, plan_hash, validate_plan)

CELL_DONE = "done"
CELL_FAILED = "failed"
CELL_PLANNED = "planned"


def cell_key(cell: dict) -> str:
    return f"{cell['task']}|{cell['condition']}|{cell['model']}|{cell['repetition']}"


def cell_run_id(study: str, cell: dict) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in study)[:24].strip("-")
    return f"{slug}-{cell['task']}-{cell['condition']}-{cell['tier']}-r{cell['repetition']:02d}"


def load_state(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text())
    return {"plan_hash": None, "cells": {}, "spend": {}, "currency": None}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def preflight(plan: dict, tasks_root: Path, audit: bool = True) -> list[str]:
    """Fail-closed gates: plan errors, manifest errors, audit failures."""
    from .experiment import validate_plan
    from .manifest import load_manifest, validate_manifest

    errors = [i.message for i in validate_plan(plan, tasks_root=tasks_root)
              if i.level == "error"]
    if errors:
        return errors
    for tid in plan["tasks"]:
        try:
            data = load_manifest(tasks_root / tid / "manifest.json")
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"task {tid}: manifest unreadable ({e})")
            continue
        for i in validate_manifest(data):
            if i.level == "error":
                errors.append(f"task {tid}: {i.message}")
    if errors:
        return errors
    if audit:
        from .cli import audit_task_dir
        for tid in plan["tasks"]:
            rc, messages = audit_task_dir(tasks_root / tid)
            for m in messages:
                print(f"  audit {tid}: {m}")
            if rc != 0:
                errors.append(f"task {tid}: audit-task failed")
    return errors


def _cell_upper_bound(plan: dict, model_id: str) -> float:
    est = cost_upper_bound(plan)
    c = (est.get("per_model", {}) or {}).get(model_id, {})
    if not c.get("computable"):
        raise ValueError(f"cost not computable for {model_id}")
    budgeting = plan.get("budgeting", {}) or {}
    turns = int(budgeting.get("max_model_turns_per_attempt", 1))
    retries = int(budgeting.get("max_retries_per_cell", 0))
    cap_in = int(budgeting["assumed_max_input_tokens_per_attempt"])
    cap_out = int(budgeting["assumed_max_output_tokens_per_attempt"])
    p = budgeting["prices"][model_id]
    per_attempt = (cap_in / 1000 * float(p["input_per_1k"])
                   + cap_out / 1000 * float(p["output_per_1k"])) * turns
    return round(per_attempt * (1 + retries), 4)


def _spend_total(state: dict) -> float:
    return round(sum(m.get("cost", 0.0) for m in state.get("spend", {}).values()), 4)


def _add_spend(state: dict, model_id: str, usage: dict, prices: dict) -> None:
    p = prices.get(model_id, {})
    cost = (usage.get("input_tokens", 0) / 1000 * float(p.get("input_per_1k", 0))
            + usage.get("output_tokens", 0) / 1000 * float(p.get("output_per_1k", 0)))
    slot = state["spend"].setdefault(
        model_id, {"input_tokens": 0, "output_tokens": 0, "cost": 0.0,
                   "currency": p.get("currency", "?")})
    slot["input_tokens"] += usage.get("input_tokens", 0)
    slot["output_tokens"] += usage.get("output_tokens", 0)
    slot["cost"] = round(slot["cost"] + cost, 4)


def _model_entry(plan: dict, model_id: str) -> dict:
    for m in plan["models"]:
        if m["model_id"] == model_id:
            return m
    raise ValueError(f"model {model_id!r} not in plan")


def _build_runner(model: dict, budgeting: dict,
                  transport_factory: Callable[[dict], Any] | None):
    from .model_runner import (LoopbackTransport, ModelAgentRunner,
                               OpenAICompatibleTransport, VertexTransport)

    max_turns = int(budgeting.get("max_model_turns_per_attempt", 20))
    if transport_factory is not None:
        transport = transport_factory(model)
    else:
        prov = model.get("provider", {}) or {}
        kind = prov.get("kind", "openai-compatible")
        if kind == "vertex-ai":
            for k in ("project", "location"):
                if not prov.get(k):
                    raise ValueError(f"vertex-ai provider needs {k!r}")
            transport = VertexTransport(
                project=prov["project"], location=prov["location"],
                model=model["model_id"],
                temperature=float(model.get("temperature", 0.0)))
        elif kind == "openai-compatible":
            for k in ("base_url", "env_key"):
                if not prov.get(k):
                    raise ValueError(f"openai-compatible provider needs {k!r}")
            transport = OpenAICompatibleTransport(
                base_url=prov["base_url"], model=model["model_id"],
                env_key=prov["env_key"])
        else:
            raise ValueError(f"unsupported provider kind {kind!r}")
    return ModelAgentRunner(
        model_id=model["model_id"], model_version=model["model_version"],
        temperature=float(model.get("temperature", 0.0)),
        settings=dict(model.get("settings", {}) or {}),
        transport=transport, max_turns=max_turns)


def _cell_transient_failure(runs_root: Path, run_id: str) -> bool:
    """Retryable iff the provider errored before any executed check ran."""
    from .trajectory import read_jsonl

    traj = runs_root / run_id / "trajectory.jsonl"
    if not traj.is_file():
        return True
    events = read_jsonl(traj)
    saw_provider_error = any(
        e.get("type") == "agent_note" and "provider call failed" in
        str(e.get("data", {}).get("text", "")) for e in events)
    saw_check = any(e.get("type") == "test_run" for e in events)
    return saw_provider_error and not saw_check


def run_matrix(plan_path: Path, tasks_root: Path, runs_root: Path,
               state_path: Path, mode: str,
               authorize_spend: bool = False, fresh: bool = False,
               transport_factory: Callable[[dict], Any] | None = None,
               smoke_task: Path | None = None,
               live: bool = False) -> int:
    """Execute the matrix. transport_factory(model_entry) overrides provider
    transport (loopback for smoke/tests). Returns process exit code."""
    from .cli import _run_once
    from .config import RunConfig, compute_environment_hash

    plan = load_plan(plan_path)
    if mode not in ("dry-run", "smoke", "execute"):
        print(f"unknown mode {mode!r}; want dry-run|smoke|execute")
        return 2
    if mode == "execute" and not authorize_spend:
        print("REFUSED: execute mode makes paid provider calls; re-run with "
              "--authorize-spend plus an explicit spend cap (protocol stop rule).")
        return 2

    print(f"== preflight ({mode}) ==")
    errors = preflight(plan, tasks_root, audit=(mode != "smoke"))
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
        print("ABORTED: fail-closed preflight (no cells run)")
        return 1
    if mode == "execute":
        cap_issues = check_spend_cap(plan)
        for i in cap_issues:
            print(f"  {i.level.upper()}: {i.message}")
        if any(i.level == "error" for i in cap_issues):
            print("ABORTED: spend cap missing or below worst case")
            return 1
        for m in plan["models"]:
            prov = m.get("provider", {}) or {}
            if prov.get("kind", "openai-compatible") == "openai-compatible":
                key = prov.get("env_key", "")
                if not os.environ.get(key):
                    print(f"  ERROR: credential env var {key!r} for tier {m['tier']} "
                          "is not set (provide via environment, never in the repo)")
                    return 1
            else:
                try:
                    from .model_runner import adc_access_token
                    adc_access_token()
                except Exception as e:
                    print(f"  ERROR: ADC unavailable for tier {m['tier']} ({e}); "
                          "run gcloud auth application-default login first")
                    return 1

    state = load_state(state_path) if not fresh else {"plan_hash": None, "cells": {}, "spend": {}, "currency": None}
    phash = plan_hash(plan)
    if state.get("plan_hash") not in (None, phash):
        print("ABORTED: state file belongs to a different plan hash "
              "(use --fresh to restart deliberately)")
        return 1
    state["plan_hash"] = phash
    state.setdefault("cells", {})
    state.setdefault("spend", {})
    budgeting = plan.get("budgeting", {}) or {}
    state["currency"] = (budgeting.get("spend_cap", {}) or {}).get("currency")

    if mode == "smoke":
        return _smoke(plan, tasks_root, runs_root, transport_factory,
                      smoke_task=smoke_task, live=live, live_turns=8)
    cells = expand_matrix(plan)
    print(f"== matrix: {len(cells)} cells ==")

    cost = cost_upper_bound(plan)
    if cost.get("computable"):
        for mid, c in cost["per_model"].items():
            print(f"  worst case {mid}: {c}")
    else:
        print(f"  cost preflight: not computable ({cost.get('reason')})")
        if mode == "execute":
            print("ABORTED: execute requires a computable worst case under the cap")
            return 1

    if mode == "dry-run":
        for cell in cells:
            key = cell_key(cell)
            rid = cell_run_id(plan.get("study", "study"), cell)
            st = state["cells"].get(key, {}).get("status", CELL_PLANNED)
            print(f"  [{st}] {key} -> {runs_root / rid}")
        save_state(state_path, state)
        print(f"dry-run complete: {len(cells)} cells planned, 0 provider calls, "
              f"0 files staged for runs")
        return 0

    # execute
    cap = (budgeting.get("spend_cap", {}) or {}).get("amount", 0)
    retries_allowed = int(budgeting.get("max_retries_per_cell", 0))
    limits = plan.get("limits", {}) or {}
    failed = 0
    for cell in cells:
        key = cell_key(cell)
        if state["cells"].get(key, {}).get("status") == CELL_DONE:
            print(f"  [resume-skip] {key}")
            continue
        model = _model_entry(plan, cell["model"])
        if _spend_total(state) + _cell_upper_bound(plan, cell["model"]) > float(cap):
            print(f"  STOP: spend cap would be exceeded by next cell "
                  f"(spent {_spend_total(state)} of {cap})")
            save_state(state_path, state)
            return 1
        base_id = cell_run_id(plan.get("study", "study"), cell)
        ok, run_id, tries, usage = _run_cell_with_retries(
            plan, cell, model, tasks_root, runs_root, base_id,
            limits, budgeting, transport_factory, retries_allowed)
        _add_spend(state, cell["model"], usage,
                   (budgeting.get("prices", {}) or {}))
        if ok:
            state["cells"][key] = {"status": CELL_DONE, "run_id": run_id, "attempts": tries}
        else:
            state["cells"][key] = {"status": CELL_FAILED, "run_id": run_id, "attempts": tries}
            failed += 1
        save_state(state_path, state)
    print(f"execute complete: {len(cells) - failed}/{len(cells)} cells done; "
          f"spend {_spend_total(state)} {state['currency']}")
    return 0 if failed == 0 else 1


def _run_cell_with_retries(plan: dict, cell: dict, model: dict,
                           tasks_root: Path, runs_root: Path, base_id: str,
                           limits: dict, budgeting: dict,
                           transport_factory: Callable[[dict], Any] | None,
                           retries_allowed: int) -> tuple[bool, str, int, dict]:
    """Run one cell, retrying transient provider failures. Returns
    (ok, final_run_id, attempts_used, final_usage). Never reuses a run_id."""
    from .cli import _run_once
    from .config import RunConfig, compute_environment_hash

    task_dir = tasks_root / cell["task"]
    usage: dict = {}
    run_id = base_id
    for attempt in range(1 + retries_allowed):
        run_id = base_id if attempt == 0 else f"{base_id}-try{attempt:02d}"
        config = RunConfig(
            model=model["model_id"], model_version=model["model_version"],
            harness=f"{plan['harness']['name']}-{plan['harness'].get('version', '?')}",
            temperature=float(model.get("temperature", 0.0)),
            seed=int(plan.get("seed", 0)),
            model_settings=dict(model.get("settings", {}) or {}),
            max_tool_calls=int(limits.get("max_tool_calls", 60)),
            max_wall_seconds=int(limits.get("max_wall_seconds", 1800)),
            max_evidence_tokens=int(limits.get("max_evidence_tokens", 2000)),
            environment_hash=compute_environment_hash(),
        )
        runner = _build_runner(model, budgeting, transport_factory)
        runner._check_frozen(cell["model"], model["model_version"])
        _run_once(task_dir, cell["condition"], runs_root, run_id, config,
                  runner, f"model:{model['model_id']}", replayed=False)
        _stamp_tier(runs_root / run_id, cell["tier"], model["model_id"])
        meta_path = runs_root / run_id / "run_meta.json"
        meta = json.loads(meta_path.read_text())
        usage = meta.get("provider_usage", {}) or {}
        if attempt > 0:
            meta["efficiency"]["retries"] = attempt
            meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        if _cell_ok(runs_root / run_id) or not _cell_transient_failure(runs_root, run_id):
            return True, run_id, attempt + 1, usage
        print(f"  transient provider failure in {run_id}; retrying "
              f"({attempt + 1}/{retries_allowed})")
    return False, run_id, 1 + retries_allowed, usage


def _cell_ok(run_dir: Path) -> bool:
    try:
        return bool(json.loads((run_dir / "run_meta.json").read_text()
                               ).get("oracle", {}).get("passed"))
    except (OSError, ValueError):
        return False


def _stamp_tier(run_dir: Path, tier: str, model_id: str) -> None:
    meta_path = run_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text())
    meta["tier"] = tier
    meta["model_id"] = model_id
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")


def _smoke(plan: dict, tasks_root: Path, runs_root: Path,
           transport_factory: Callable[[dict], Any] | None,
           smoke_task: Path | None = None,
           live: bool = False, live_turns: int = 8) -> int:
    """One plumbing-only attempt through the real model loop.

    Default transport is loopback (no provider calls, no cost). With
    live=True the plan's first model entry drives via its real provider
    transport, capped at live_turns turns; usage/cost are recorded and the
    output is still labeled plumbing-only, never a benchmark result.
    """
    from .cli import _run_once, audit_task_dir
    from .config import RunConfig, compute_environment_hash
    from .model_runner import LoopbackTransport

    if smoke_task is None:
        target = Path(__file__).resolve().parents[2] / "fixtures" / "plumbing_fixture"
        label, run_id = "plumbing fixture", "smoke-loopback"
        script = [json.dumps({"actions": [
            {"op": "read", "path": "counter.py"},
            {"op": "test", "name": "smoke-repro",
             "cmd": [sys.executable, "-c",
                     "from counter import add; assert add(1, 2) == 4"]},
            {"op": "verify", "name": "smoke-claim", "result": "FAIL",
             "detail": "loopback smoke (plumbing-only)"},
            {"op": "finish", "diagnosis": "loopback smoke (plumbing-only)",
             "verification_summary": "loopback smoke (plumbing-only)"}]})]
    else:
        target = Path(smoke_task)
        label, run_id = "draft task", f"smoke-{target.name}"
        script = [json.dumps({"actions": [
            {"op": "read", "path": "TASK_INSTRUCTIONS.md"},
            {"op": "test", "name": "smoke-compile",
             "cmd": [sys.executable, "-c",
                     "import compileall,sys; sys.exit(0 if compileall.compile_dir('.', quiet=1) else 1)"]},
            {"op": "verify", "name": "smoke-claim", "result": "INCONCLUSIVE",
             "detail": "loopback smoke on draft task (plumbing-only)"},
            {"op": "finish", "diagnosis": "loopback smoke (plumbing-only)",
             "verification_summary": "loopback smoke (plumbing-only)"}]})]
    model = plan["models"][0]
    rc, messages = audit_task_dir(target)
    for m in messages:
        print(f"  audit {label}: {m}")
    if rc != 0:
        print(f"SMOKE ABORTED: {label} audit failed")
        return 1
    from .model_runner import ModelAgentRunner
    if live:
        run_id = run_id + "-live"
        print(f"== smoke: LIVE provider attempt ({model['model_id']}) on {label} "
              f"({target}), max {live_turns} turns ==")
        budgeting = plan.get("budgeting", {}) or {}
        prices = (budgeting.get("prices", {}) or {}).get(model["model_id"])
        if not prices or prices.get("source") != "user-supplied":
            print("SMOKE ABORTED: live smoke needs user-supplied prices for "
                  f"{model['model_id']} to bound the attempt")
            return 1
        worst_1 = (int(budgeting.get("assumed_max_input_tokens_per_attempt", 0)) / 1000
                   * float(prices["input_per_1k"])
                   + int(budgeting.get("assumed_max_output_tokens_per_attempt", 0)) / 1000
                   * float(prices["output_per_1k"])) * live_turns
        cap = (budgeting.get("spend_cap", {}) or {}).get("amount") or 0
        print(f"  1-cell worst case at {live_turns} turns: {worst_1:.4f} "
              f"{prices.get('currency', '?')} (cap: {cap})")
        if worst_1 > float(cap):
            print("SMOKE ABORTED: worst case exceeds spend cap")
            return 1
        runner = _build_runner(model, budgeting, transport_factory)
        runner.max_turns = live_turns
        runner_name = f"model:{model['model_id']}(live-smoke)"
    else:
        transport = LoopbackTransport(script) if transport_factory is None \
            else transport_factory(model)
        runner = ModelAgentRunner(
            model_id=model["model_id"], model_version=model["model_version"],
            temperature=float(model.get("temperature", 0.0)),
            settings=dict(model.get("settings", {}) or {}),
            transport=transport, max_turns=5)
        runner_name = "model-loopback(smoke)"
    config = RunConfig(model=model["model_id"], model_version=model["model_version"],
                       harness="debev-smoke", temperature=0.0, seed=0,
                       environment_hash=compute_environment_hash())
    run_dir = _run_once(target, "symptom_only", runs_root, run_id,
                        config, runner, "model-loopback(smoke)", replayed=False)
    from .trajectory import read_jsonl
    events = read_jsonl(run_dir / "trajectory.jsonl")
    kinds = {e["type"] for e in events}
    writes = [e["data"].get("path", "") for e in events if e["type"] == "file_write"]
    checks = {
        "file_read observed": "file_read" in kinds,
        "executed test observed": any(e["type"] == "test_run" and
                                      e.get("data", {}).get("via") == "toolkit"
                                      for e in events),
        "no writes outside workspace": all(".." not in p and not p.startswith("/")
                                           for p in writes),
    }
    ok = all(checks.values())
    for k, v in checks.items():
        print(f"  smoke check {k}: {'OK' if v else 'FAIL'}")
    meta = json.loads((run_dir / "run_meta.json").read_text())
    meta["plumbing_only"] = True
    meta["tier"] = model.get("tier", "?")
    meta["model_id"] = model.get("model_id", "?")
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("SMOKE " + ("PASSED (plumbing-only; not a model result)" if ok else "FAILED"))
    return 0 if ok else 1

