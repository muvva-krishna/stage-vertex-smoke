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
    """Structured agent verification only.

    True iff the trajectory holds a `verification` event or a `test_run`
    with an explicit verdict (PASS/FAIL/ERROR/INCONCLUSIVE). Bare shell
    commands (ls, cat, …) never count, and the evaluator's own oracle run
    is recorded separately and never counts as agent verification.
    """
    for e in events:
        if e.get("type") == "verification":
            return True
        if e.get("type") == "test_run" and e.get("data", {}).get("result") in (
            "PASS", "FAIL", "ERROR", "INCONCLUSIVE",
        ):
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
            "condition": condition,
            "evidence_files": sorted(evidence.artifacts.keys()),
            "evidence_tokens": evidence.evidence_tokens,
            "token_counts": evidence.token_counts,
            "budget": evidence.budget,
            "replayed": replayed,
            "environment_hash": config.environment_hash,
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
    t0 = time.time()
    result = runner.run(ctx, recorder)
    wall_s = round(time.time() - t0, 2)
    if result.diagnosis:
        recorder.record("agent_note", {"kind": "diagnosis", "text": result.diagnosis[:2000]})
    if result.verification_summary:
        recorder.record(
            "agent_note", {"kind": "verification", "text": result.verification_summary[:2000]}
        )
    diff_text = diff_workspace(workspace, baseline)
    (run_dir / "diff.patch").write_text(diff_text + "\n", encoding="utf-8")
    recorder.record("diff", {"summary": diff_text[:4000]})
    recorder.record("run_end", {"wall_s": wall_s, "replayed": replayed})
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
        "model_tokens": None,  # recorded by the agent harness when available
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
                "trajectory": "trajectory.jsonl",
                "harness_commit": harness_commit(PILOT_ROOT),
                "harness_dirty": harness_dirty(PILOT_ROOT),
                "manifest_sha256": sha256_file(task_dir / "manifest.json"),
                "evidence_sha256": hash_tree(task_dir / "evidence") if (task_dir / "evidence").is_dir() else {},
                "oracle_sha256": hash_tree(task_dir / "evaluator") if (task_dir / "evaluator").is_dir() else {},
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


def cmd_audit_task(args) -> int:
    """Task-quality audit: oracle must FAIL on broken start, PASS on the
    human-authored reference solution, and still FAIL on partial-fix probes."""
    from .oracle import OracleResult  # noqa: F401

    task_dir = Path(args.task_dir)
    manifest = load_manifest(task_dir / "manifest.json")
    issues = validate_manifest(manifest)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        print("manifest INVALID:")
        for i in errors:
            print(f"  ERROR: {i.message}")
        return 1
    eval_src = task_dir / "evaluator"
    ref = eval_src / "reference_solution"
    if not ref.is_dir():
        print("FAIL: evaluator/reference_solution/ overlay missing "
              "(human-authored fixed files that overlay the repo)")
        return 1
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
        print(f"broken-start oracle: passed={res_broken.passed} "
              f"groups={[g.group for g in res_broken.groups]}")
        if res_broken.passed:
            failures.append("oracle PASSES on the broken starting state (must FAIL)")
        # 2. reference solution must PASS
        ws_fixed = _stage_task(task_dir, tmp_p / "fixed", overlay=ref)
        res_fixed = run_oracle_script(ws_fixed, eval_stage, entry)
        print(f"reference-solution oracle: passed={res_fixed.passed}")
        if not res_fixed.passed:
            failures.append("oracle FAILS on the human-authored reference solution (must PASS)")
        # 3. partial fixes must still FAIL (else the oracle is overfit/insensitive)
        partials = eval_src / "partial_fixes"
        if partials.is_dir():
            for probe in sorted(p for p in partials.iterdir() if p.is_dir()):
                ws_part = _stage_task(task_dir, tmp_p / f"partial-{probe.name}", overlay=probe)
                res_part = run_oracle_script(ws_part, eval_stage, entry)
                print(f"partial-fix {probe.name}: passed={res_part.passed} (want False)")
                if res_part.passed:
                    failures.append(f"partial fix {probe.name!r} PASSES the oracle (must FAIL)")
        else:
            print("note: no evaluator/partial_fixes/ probes; consider adding at least one")
    if failures:
        print("AUDIT FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("AUDIT PASSED")
    return 0


def cmd_export_otel(args) -> int:
    out = otel_export_file(Path(args.run_dir), Path(args.out))
    print(f"wrote OTLP JSON trace -> {out}")
    return 0


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
        records.append(
            {
                "run_id": meta["run_id"],
                "task_id": meta["task_id"],
                "condition": meta["condition"],
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
