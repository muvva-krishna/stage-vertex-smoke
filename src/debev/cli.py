"""debev CLI: validate | run | replay | score | grade | audit-task | export-otel | report (stdlib only)."""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .conditions import CONDITIONS, load_condition
from .config import RunConfig, compute_environment_hash, default_config
from .manifest import SCHEMA_VERSION, load_manifest, validate_manifest
from .oracle import run_oracle_script
from .otel_export import export_file as otel_export_file
from .provenance import harness_commit, harness_dirty, hash_tree, sha256_file
from .report import build_report, render_markdown, summarize_trajectory
from .rubric import apply_human_grade, score_machine_portion
from .runners import (
    AttemptContext,
    NoopRunner,
    ReplayRunner,
    diff_workspace,
    prepare_run_dirs,
    snapshot_workspace,
)
from .sandbox import detect_isolation
from .trajectory import TrajectoryRecorder, read_jsonl

FORBIDDEN_WORKSPACE_NAMES = ("oracle.py", "hidden_", "answer_", "reference_patch")

PILOT_ROOT = Path(__file__).resolve().parents[2]


def _constraint_checks(workspace: Path) -> list[dict]:
    names = [p.name for p in workspace.rglob("*") if p.is_file()]
    rels = [str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file()]
    bad = [n for n in names if n == "oracle.py" or n.startswith(("hidden_", "answer_"))]
    checks = [
        {
            "name": "no_evaluator_files_in_workspace",
            "passed": not bad,
            "detail": f"forbidden files present: {bad}" if bad else "ok",
        },
        {
            "name": "no_reference_patch_file",
            "passed": not any("reference_patch" in r for r in rels),
            "detail": "ok",
        },
    ]
    return checks


def _agent_verification_ran(events: list[dict]) -> bool:
    """Executed agent checks only.

    True iff the trajectory holds a `test_run` with an explicit verdict
    (PASS/FAIL/ERROR/INCONCLUSIVE) that was EXECUTED through the toolkit
    (`via: toolkit`, not replayed). A free-form/self-reported `verification`
    event alone never earns machine credit — it is the agent's final claim,
    kept for human grading of reporting accuracy. Bare shell commands never
    count, and the evaluator's own oracle run never counts.
    """
    for e in events:
        if e.get("type") != "test_run":
            continue
        d = e.get("data", {})
        if d.get("result") not in ("PASS", "FAIL", "ERROR", "INCONCLUSIVE"):
            continue
        if d.get("via") != "toolkit" or d.get("replayed"):
            continue
        return True
    return False


def _load_runner(spec: str, agents_dir: Path | None = None):
    """Resolve --runner: noop | baseline | scripted-fix | path:Class | mod:Class."""
    if spec == "noop":
        return NoopRunner(), "noop"
    if spec in ("baseline", "scripted-fix"):
        agents_dir = agents_dir or (PILOT_ROOT / "agents")
        sys.path.insert(0, str(agents_dir.parent))
        try:
            mod = importlib.import_module("agents.fixture_agents")
        except ImportError:
            mod = importlib.import_module("fixture_agents")
        cls = "BaselineProbeRunner" if spec == "baseline" else "ScriptedFixtureRepairRunner"
        return getattr(mod, cls)(), spec
    if ":" not in spec:
        raise ValueError(f"bad --runner {spec!r}; want noop|baseline|scripted-fix|path:Class|module:Class")
    location, cls_name = spec.rsplit(":", 1)
    if Path(location).exists():
        mod_name = Path(location).stem + "_debev_ext"
        spec_obj = importlib.util.spec_from_file_location(mod_name, location)
        mod = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(mod)
    else:
        mod = importlib.import_module(location)
    return getattr(mod, cls_name)(), spec


def cmd_validate(args) -> int:
    data = load_manifest(args.manifest)
    issues = validate_manifest(data)
    for i in issues:
        print(f"{i.level.upper()}: {i.message}")
    if any(i.level == "error" for i in issues):
        print("INVALID")
        return 1
    print("VALID")
    return 0


def _run_once(
    task_dir: Path,
    condition: str,
    runs_root: Path,
    run_id: str,
    config: RunConfig,
    runner,
    runner_name: str,
    replayed: bool,
) -> Path:
    manifest = load_manifest(task_dir / "manifest.json")
    issues = validate_manifest(manifest)
    if any(i.level == "error" for i in issues):
        raise ValueError(f"invalid manifest: {[i.message for i in issues if i.level=='error']}")
    if condition not in manifest.get("conditions", []):
        raise ValueError(f"condition {condition!r} not enabled for task {manifest['task_id']}")

    evidence = load_condition(
        task_dir / "evidence", condition, config.max_evidence_tokens
    )
    dirs = prepare_run_dirs(runs_root, run_id, task_dir / "repo")
    run_dir, workspace, evaluator = dirs["run_dir"], dirs["workspace"], dirs["evaluator"]

    # Stage evaluator-only files OUTSIDE the workspace. The reference
    # solution and partial-fix probes are needed only by `audit-task`;
    # they are never staged into a run's evaluator dir.
    eval_src = task_dir / "evaluator"
    if eval_src.is_dir():
        for item in eval_src.iterdir():
            if item.name in ("reference_solution", "partial_fixes"):
                continue
            dest = evaluator / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    baseline = snapshot_workspace(workspace)
    recorder = TrajectoryRecorder(
        run_id=run_id, task_id=manifest["task_id"], condition=condition
    )
    recorder.record(
        "run_start",
        {
            "model": config.model,
            "model_version": config.model_version,
            "harness": config.harness,
            "runner": runner_name,
            "seed": config.seed,
            "temperature": config.temperature,
            "model_settings": config.model_settings,
            "condition": condition,
            "evidence_files": sorted(evidence.artifacts.keys()),
            "evidence_tokens": evidence.evidence_tokens,
            "token_counts": evidence.token_counts,
            "budget": evidence.budget,
            "replayed": replayed,
            "environment_hash": config.environment_hash,
            "t_epoch": time.time(),
        },
    )
    # Materialize the selected evidence into the workspace and log access.
    ev_dir = workspace / "evidence"
    ev_dir.mkdir(exist_ok=True)
    for name, text in evidence.artifacts.items():
        (ev_dir / name).write_text(text, encoding="utf-8")
        recorder.record("evidence_access", {"file": name, "tokens": evidence.token_counts[name]})
    # Copy the human-authored task instructions (placeholder-safe).
    instr_src = task_dir / "instructions.md"
    if instr_src.is_file():
        shutil.copy2(instr_src, workspace / "TASK_INSTRUCTIONS.md")
        recorder.record("file_read", {"path": "TASK_INSTRUCTIONS.md"})

    ctx = AttemptContext(
        run_id=run_id,
        task_id=manifest["task_id"],
        condition=condition,
        workspace_dir=workspace,
        evidence=evidence,
        allowed_tools=list(manifest.get("allowed_tools", [])),
        limits=dict(manifest.get("resource_limits", {})),
    )
    from .runners import LimitsTracker
    from .toolkit import ToolBudgetExceeded

    tracker = LimitsTracker(
        max_tool_calls=int(ctx.limits.get("max_tool_calls", 60)),
        max_wall_seconds=int(ctx.limits.get("max_wall_seconds", 1800)),
    )
    ctx.tracker = tracker
    per_command_timeout = ctx.limits.get("per_command_timeout", 120)

    # Run the agent on a daemon thread under a wall-clock watchdog.
    # Cooperative boundary: toolkit calls enforce the budget, and
    # per-command timeouts are hard (subprocess). An in-process runner
    # stuck in pure computation without tool calls CANNOT be forcibly
    # terminated from here — a hard kill requires an out-of-process
    # runner boundary (documented in docs/evaluation_protocol.md).
    import threading

    box: dict = {}
    t0 = time.time()

    def _target():
        try:
            box["result"] = runner.run(ctx, recorder)
        except Exception as e:  # noqa: BLE001 — recorded, then scored as-is
            box["error"] = e

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, tracker.remaining_wall()))
    orphaned = False
    if thread.is_alive():
        tracker.wall_limit_reached = True
        recorder.record("timeout", {"kind": "attempt",
                                    "max_wall_seconds": tracker.max_wall_seconds})
        thread.join(timeout=5)
        orphaned = thread.is_alive()
        if orphaned:
            recorder.record("limit_exceeded",
                            {"kind": "wall_clock", "op": "runner-thread-still-alive"})
    wall_s = round(time.time() - t0, 2)
    if "error" in box:
        err = box["error"]
        if isinstance(err, ToolBudgetExceeded):
            pass  # toolkit already recorded the limit_exceeded event
        else:
            recorder.record("agent_note",
                            {"kind": "error", "text": f"runner raised {type(err).__name__}: {err}"[:500]})
        from .runners import AttemptResult as _AR
        result = _AR(diagnosis=f"runner ended with {type(err).__name__}",
                     verification_summary="no verification performed")
    else:
        result = box.get("result")
        if result is None:  # watchdog fired and thread never returned
            from .runners import AttemptResult as _AR
            result = _AR(diagnosis="wall-clock deadline exceeded",
                         verification_summary="no verification performed")
    if result.diagnosis:
        recorder.record("agent_note", {"kind": "diagnosis", "text": result.diagnosis[:2000]})
    if result.verification_summary:
        recorder.record(
            "agent_note", {"kind": "verification", "text": result.verification_summary[:2000]}
        )
    diff_text = diff_workspace(workspace, baseline)
    (run_dir / "diff.patch").write_text(diff_text + "\n", encoding="utf-8")
    recorder.record("diff", {"summary": diff_text[:4000]})
    recorder.record("run_end", {"wall_s": wall_s, "replayed": replayed,
                                "limits": tracker.status(),
                                "runner_orphaned": orphaned})
    traj_path = run_dir / "trajectory.jsonl"
    recorder.write_jsonl(traj_path)

    # Score: oracle runs against evaluator/ (never inside workspace).
    oracle_cfg = manifest.get("oracle", {})
    oracle_result = run_oracle_script(
        workspace, evaluator, oracle_cfg.get("entry_point", "oracle.py")
    )
    weights_path = task_dir / "rubric_weights.json"
    weights = json.loads(weights_path.read_text()) if weights_path.is_file() else None
    events = recorder.events
    score = score_machine_portion(
        task_id=manifest["task_id"],
        condition=condition,
        run_id=run_id,
        functional_groups=[
            {"group": g.group, "passed": g.passed, "detail": g.detail}
            for g in oracle_result.groups
            if not g.group.startswith("compat:")
        ] or [{"group": "oracle", "passed": oracle_result.passed, "detail": "overall"}],
        functional_weights=(weights or {}).get("functional") if weights else None,
        compat_groups=[
            {"group": g.group[len("compat:"):], "passed": g.passed, "detail": g.detail}
            for g in oracle_result.groups
            if g.group.startswith("compat:")
        ],
        constraint_checks=_constraint_checks(workspace),
        verification_ran=_agent_verification_ran(events),
    )
    tool_calls = sum(1 for e in events if e["type"] in ("command", "file_read", "file_write", "test_run", "verification"))
    efficiency = {
        "tool_calls": tool_calls,
        "tests_run": sum(1 for e in events if e["type"] == "test_run"),
        "verifications": sum(1 for e in events if e["type"] == "verification"),
        "evidence_tokens": evidence.evidence_tokens,
        "model_tokens": dict(result.provider_usage) or None,  # provider-reported; None when N/A
        "wall_clock_s": wall_s,
        "retries": 0,
    }
    (run_dir / "score.json").write_text(json.dumps(score.to_dict(), indent=2) + "\n")
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": manifest["task_id"],
                "condition": condition,
                "replayed": replayed or result.replayed,
                "runner": runner_name,
                "config": config.to_dict(),
                "evidence_tokens": evidence.evidence_tokens,
                "token_counts": evidence.token_counts,
                "oracle": oracle_result.to_dict(),
                "oracle_isolation": oracle_result.isolation,
                "sandbox_available": detect_isolation(),
                "efficiency": efficiency,
                "provider_usage": dict(result.provider_usage),
                "trajectory": "trajectory.jsonl",
                "harness_commit": harness_commit(PILOT_ROOT),
                "harness_dirty": harness_dirty(PILOT_ROOT),
                "manifest_sha256": sha256_file(task_dir / "manifest.json"),
                "evidence_sha256": hash_tree(task_dir / "evidence") if (task_dir / "evidence").is_dir() else {},
                "oracle_sha256": hash_tree(task_dir / "evaluator") if (task_dir / "evaluator").is_dir() else {},
                "limits": dict(tracker.status(), per_command_timeout=per_command_timeout),
                "runner_orphaned": orphaned,
                "trust": ("custom runner code runs in-process and is trusted; "
                          "confinement (workspace-only paths, scrubbed env, "
                          "recorded sandbox) applies to toolkit-mediated "
                          "file/command actions only"),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"run complete: {run_dir} passed={oracle_result.passed} total={score.total}")
    return run_dir


def _load_config(path: str | None) -> RunConfig:
    if path:
        cfg = RunConfig.from_json_file(path)
        if not cfg.environment_hash:
            cfg.environment_hash = compute_environment_hash()
        return cfg
    return default_config()


def cmd_run(args) -> int:
    task_dir = Path(args.task_dir)
    runs_root = Path(args.runs_root)
    config = _load_config(args.config)
    conditions = (
        args.conditions.split(",") if args.conditions else [args.condition]
    )
    for c in conditions:
        if c not in CONDITIONS:
            print(f"unknown condition: {c}", file=sys.stderr)
            return 2
    order = [(c, r) for c in conditions for r in range(args.repetitions)]
    if args.randomize:
        random.Random(args.seed).shuffle(order)
    if args.replay_from:
        runner, runner_name = ReplayRunner(args.replay_from), f"replay:{args.replay_from}"
        replayed = True
    else:
        runner, runner_name = _load_runner(args.runner)
        replayed = False
    for i, (cond, _rep) in enumerate(order):
        run_id = f"{args.run_id_prefix}-{cond}-r{i:02d}" if len(order) > 1 else args.run_id_prefix
        _run_once(task_dir, cond, runs_root, run_id, config, runner, runner_name, replayed)
    return 0


def cmd_replay(args) -> int:
    # Replay = run with ReplayRunner; output is labeled replayed everywhere.
    args.replay_from = args.replay_file
    args.runner = "noop"
    return cmd_run(args)


def cmd_score(args) -> int:
    run_dir = Path(args.run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text())
    print(json.dumps({"oracle": meta.get("oracle"), "efficiency": meta.get("efficiency")}, indent=2))
    score = json.loads((run_dir / "score.json").read_text())
    print(json.dumps(score, indent=2))
    return 0


def cmd_grade(args) -> int:
    """Persist a human grade for diagnosis and/or reporting-accuracy halves."""
    run_dir = Path(args.run_dir)
    score_path = run_dir / "score.json"
    score = json.loads(score_path.read_text())
    updated = apply_human_grade(
        score,
        diagnosis_pts=args.diagnosis_pts,
        reporting_pts=args.reporting_pts,
        grader=args.grader,
        rationale=args.rationale or "",
    )
    score_path.write_text(json.dumps(updated, indent=2) + "\n")
    meta = json.loads((run_dir / "run_meta.json").read_text())
    meta["human_grade"] = updated.get("human_grade")
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(updated, indent=2))
    return 0


def _stage_task(task_dir: Path, dest_root: Path, overlay: Path | None = None) -> Path:
    ws = dest_root / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    repo_src = task_dir / "repo"
    if repo_src.is_dir():
        for item in repo_src.iterdir():
            d = ws / item.name
            if item.is_dir():
                shutil.copytree(item, d)
            else:
                shutil.copy2(item, d)
    if overlay and overlay.is_dir():
        for item in overlay.rglob("*"):
            if item.is_file():
                d = ws / item.relative_to(overlay)
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, d)
    return ws


def audit_task_dir(task_dir: Path) -> tuple[int, list[str]]:
    """Task-quality audit returning (rc, messages) for reuse by run-matrix."""
    from .oracle import OracleResult  # noqa: F401

    messages: list[str] = []
    manifest = load_manifest(task_dir / "manifest.json")
    issues = validate_manifest(manifest)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        messages.append("manifest INVALID:")
        for i in errors:
            messages.append(f"  ERROR: {i.message}")
        return 1, messages
    eval_src = task_dir / "evaluator"
    ref = eval_src / "reference_solution"
    if not ref.is_dir():
        messages.append("FAIL: evaluator/reference_solution/ overlay missing "
                        "(human-authored fixed files that overlay the repo)")
        return 1, messages
    entry = manifest.get("oracle", {}).get("entry_point", "oracle.py")
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="debev-audit-") as tmp:
        tmp_p = Path(tmp)
        eval_stage = tmp_p / "evaluator"
        shutil.copytree(eval_src, eval_stage,
                         ignore=shutil.ignore_patterns("reference_solution", "partial_fixes"))
        # 1. broken start must FAIL
        ws_broken = _stage_task(task_dir, tmp_p / "broken")
        res_broken = run_oracle_script(ws_broken, eval_stage, entry)
        messages.append(f"broken-start oracle: passed={res_broken.passed} "
                        f"groups={[g.group for g in res_broken.groups]}")
        if res_broken.passed:
            failures.append("oracle PASSES on the broken starting state (must FAIL)")
        # 2. reference solution must PASS
        ws_fixed = _stage_task(task_dir, tmp_p / "fixed", overlay=ref)
        res_fixed = run_oracle_script(ws_fixed, eval_stage, entry)
        messages.append(f"reference-solution oracle: passed={res_fixed.passed}")
        if not res_fixed.passed:
            failures.append("oracle FAILS on the human-authored reference solution (must PASS)")
        # 3. partial fixes must still FAIL (else the oracle is overfit/insensitive)
        partials = eval_src / "partial_fixes"
        if partials.is_dir():
            for probe in sorted(p for p in partials.iterdir() if p.is_dir()):
                ws_part = _stage_task(task_dir, tmp_p / f"partial-{probe.name}", overlay=probe)
                res_part = run_oracle_script(ws_part, eval_stage, entry)
                messages.append(f"partial-fix {probe.name}: passed={res_part.passed} (want False)")
                if res_part.passed:
                    failures.append(f"partial fix {probe.name!r} PASSES the oracle (must FAIL)")
        else:
            messages.append("note: no evaluator/partial_fixes/ probes; consider adding at least one")
    if failures:
        messages.append("AUDIT FAILED:")
        for f in failures:
            messages.append(f"  - {f}")
        return 1, messages
    messages.append("AUDIT PASSED")
    return 0, messages


def cmd_audit_task(args) -> int:
    """Task-quality audit: oracle must FAIL on broken start, PASS on the
    human-authored reference solution, and still FAIL on partial-fix probes."""
    rc, messages = audit_task_dir(Path(args.task_dir))
    for m in messages:
        print(m)
    return rc


def cmd_export_otel(args) -> int:
    out = otel_export_file(Path(args.run_dir), Path(args.out))
    print(f"wrote OTLP JSON trace -> {out}")
    return 0


def cmd_plan_matrix(args) -> int:
    from .experiment import (cost_upper_bound, expand_matrix, load_plan,
                             matrix_count, plan_hash, validate_plan)

    plan = load_plan(args.plan)
    tasks_root = Path(args.tasks_root or (PILOT_ROOT / "tasks"))
    issues = validate_plan(plan, tasks_root=tasks_root)
    for i in issues:
        print(f"{i.level.upper()}: {i.message}")
    if any(i.level == "error" for i in issues):
        print("PLAN INVALID — fix errors before running anything")
        return 1
    cells = expand_matrix(plan)
    total = matrix_count(plan)
    print(f"plan {plan.get('study')}: {len(plan['tasks'])} tasks x "
          f"{len(plan['conditions'])} conditions x {len(plan['models'])} models x "
          f"{plan['repetitions']} reps = {total} attempts")
    print(f"order: {'randomized seed ' + str(plan.get('seed')) if plan.get('randomize') else 'fixed'}; "
          f"repetitions are repeated attempts at the same cell, not independent tasks")
    for m in plan["models"]:
        n = sum(1 for c in cells if c["model"] == m["model_id"])
        print(f"  tier {m['tier']}: {m['model_id']} ({m['model_version']}) -> {n} cells")
    cost = cost_upper_bound(plan)
    if cost.get("computable"):
        print(f"  worst-case assumptions: {cost.get('assumptions')}")
        for mid, c in cost["per_model"].items():
            print(f"  cost upper bound {mid}: {c}")
    else:
        print(f"  cost: not computable ({cost.get('reason')}); "
              "supply user prices + input/output token caps before any paid calls")
    print("  WARNING: 3 tasks support no population-level claims, "
          "however many repetitions run.")
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "planned": True,
            "note": "Planned cells only — never experimental results.",
            "plan_hash": plan_hash(plan),
            "plan": plan,
            "cells": cells,
            "total": total,
        }
        out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        print(f"wrote plan artifact -> {out}")
    return 0


def cmd_run_matrix(args) -> int:
    from .matrix import run_matrix

    return run_matrix(
        plan_path=Path(args.plan),
        tasks_root=Path(args.tasks_root or (PILOT_ROOT / "tasks")),
        runs_root=Path(args.runs_root),
        state_path=Path(args.state),
        mode=args.mode,
        authorize_spend=args.authorize_spend,
        fresh=args.fresh,
    )


def cmd_report(args) -> int:
    runs_root = Path(args.runs_root)
    records = []
    for run_dir in sorted(runs_root.iterdir()):
        if not run_dir.is_dir():
            continue
        meta_path, score_path, traj_path = (
            run_dir / "run_meta.json",
            run_dir / "score.json",
            run_dir / "trajectory.jsonl",
        )
        if not (meta_path.is_file() and score_path.is_file()):
            continue
        meta = json.loads(meta_path.read_text())
        score = json.loads(score_path.read_text())
        events = read_jsonl(traj_path) if traj_path.is_file() else []
        cfg = meta.get("config", {}) or {}
        records.append(
            {
                "run_id": meta["run_id"],
                "task_id": meta["task_id"],
                "condition": meta["condition"],
                "model": meta.get("model_id", cfg.get("model", "?")),
                "tier": meta.get("tier", "?"),
                "score": score,
                "efficiency": meta.get("efficiency", {}),
                "evidence_tokens": meta.get("evidence_tokens"),
                "isolation": meta.get("oracle_isolation", meta.get("sandbox_available")),
                "runner": meta.get("runner"),
                "harness_commit": meta.get("harness_commit"),
                "human_grade": meta.get("human_grade"),
                "trajectory_summary": summarize_trajectory(events),
                "failure_labels": meta.get("failure_labels", []),
                "replayed": meta.get("replayed", False),
            }
        )
    report = build_report(records)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".json":
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        out.write_text(render_markdown(report) + "\n", encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote report for {len(records)} runs -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="debev", description="Debugging-evidence eval pilot")
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate a task manifest")
    v.add_argument("manifest", help="path to manifest.json")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("run", help="run attempt(s) with the selected runner")
    r.add_argument("--task-dir", required=True)
    r.add_argument("--condition", default="symptom_only")
    r.add_argument("--conditions", default="")
    r.add_argument("--repetitions", type=int, default=1)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--no-randomize", dest="randomize", action="store_false", default=True)
    r.add_argument("--runs-root", default="results/runs")
    r.add_argument("--run-id-prefix", default="run-001")
    r.add_argument("--config", default=None)
    r.add_argument("--runner", default="noop",
                   help="noop | baseline | scripted-fix | path/to/agent.py:Class | module:Class")
    r.add_argument("--replay-from", default=None, help="replay JSONL (labels run replayed)")
    r.set_defaults(func=cmd_run)

    rp = sub.add_parser("replay", help="replay recorded fixture events (not a model run)")
    rp.add_argument("--task-dir", required=True)
    rp.add_argument("--condition", default="symptom_only")
    rp.add_argument("--conditions", default="")
    rp.add_argument("--repetitions", type=int, default=1)
    rp.add_argument("--seed", type=int, default=0)
    rp.add_argument("--no-randomize", dest="randomize", action="store_false", default=True)
    rp.add_argument("--runs-root", default="results/runs")
    rp.add_argument("--run-id-prefix", default="replay-001")
    rp.add_argument("--config", default=None)
    rp.add_argument("--replay-file", required=True)
    rp.set_defaults(func=cmd_replay)

    s = sub.add_parser("score", help="print stored score for a run")
    s.add_argument("--run-dir", required=True)
    s.set_defaults(func=cmd_score)

    g = sub.add_parser("grade", help="persist a human grade onto a run's score")
    g.add_argument("--run-dir", required=True)
    g.add_argument("--diagnosis-pts", type=float, default=None, help="0..20")
    g.add_argument("--reporting-pts", type=float, default=None, help="0..2.5")
    g.add_argument("--grader", default="", help="grader name (required)")
    g.add_argument("--rationale", default="", help="short grading rationale")
    g.set_defaults(func=cmd_grade)

    a = sub.add_parser("audit-task", help="check oracle FAILs broken, PASSes reference, FAILs partials")
    a.add_argument("--task-dir", required=True)
    a.set_defaults(func=cmd_audit_task)

    e = sub.add_parser("export-otel", help="export a run trajectory as OTLP JSON trace")
    e.add_argument("--run-dir", required=True)
    e.add_argument("--out", required=True)
    e.set_defaults(func=cmd_export_otel)

    pm = sub.add_parser("plan-matrix", help="print/validate the experiment matrix (no agents, no APIs)")
    pm.add_argument("--plan", required=True, help="path to experiment plan JSON")
    pm.add_argument("--tasks-root", default=None)
    pm.add_argument("--write", default=None, help="write plan artifact JSON (labeled planned:true)")
    pm.set_defaults(func=cmd_plan_matrix)

    rm = sub.add_parser("run-matrix", help="execute a frozen plan: dry-run (offline) | smoke (loopback) | execute (paid)")
    rm.add_argument("--plan", required=True)
    rm.add_argument("--mode", required=True, choices=["dry-run", "smoke", "execute"])
    rm.add_argument("--tasks-root", default=None)
    rm.add_argument("--runs-root", default="results/runs")
    rm.add_argument("--state", default="results/matrix_state.json")
    rm.add_argument("--authorize-spend", action="store_true",
                    help="REQUIRED for execute: confirms explicit instruction for paid calls")
    rm.add_argument("--fresh", action="store_true",
                    help="ignore existing state and restart (completed cells re-run)")
    rm.set_defaults(func=cmd_run_matrix)

    g2 = sub.add_parser("report", help="generate pilot report over runs/")
    g2.add_argument("--runs-root", default="results/runs")
    g2.add_argument("--out", default="results/REPORT.md")
    g2.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        print(__version__)
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
