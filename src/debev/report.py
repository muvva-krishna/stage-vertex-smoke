"""Report generator: outcomes by task x condition, failures, trajectories.

Rules enforced here:
  - correctness pass rate is the primary outcome; efficiency is separate.
  - small pilots are labeled as pilots; no significance claims.
  - replayed runs are labeled as replays, never as model results.
  - each failure label links to observable event seqs; observed events and
    evaluator interpretation are kept in separate fields.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def summarize_trajectory(events: list[dict]) -> dict[str, Any]:
    evidence_opened: list[str] = []
    commands: list[dict] = []
    tests: list[dict] = []
    files_read: list[str] = []
    files_changed: list[str] = []
    for e in events:
        t, d = e.get("type"), e.get("data", {})
        if t == "evidence_access" and d.get("file"):
            evidence_opened.append(d["file"])
        elif t == "command":
            commands.append({"seq": e["seq"], "cmd": d.get("cmd", ""), "rc": d.get("rc")})
        elif t == "test_run":
            tests.append(
                {"seq": e["seq"], "name": d.get("name", ""), "result": d.get("result", "")}
            )
        elif t == "file_read" and d.get("path"):
            files_read.append(d["path"])
        elif t == "file_write" and d.get("path"):
            files_changed.append(d["path"])
    return {
        "n_events": len(events),
        "evidence_opened": sorted(set(evidence_opened)),
        "commands": commands,
        "tests": tests,
        "files_read": sorted(set(files_read)),
        "files_changed": sorted(set(files_changed)),
    }


def build_report(run_records: list[dict]) -> dict[str, Any]:
    """run_records: list of {run_id, task_id, condition, model, tier, score,
    full_passed, efficiency, trajectory_summary, failure_labels:[...], replayed}.

    Terminology (see docs/evaluation_protocol.md):
    - functional_passes: attempts whose required FUNCTIONAL groups all pass
      (TaskScore.passed). A functional-only pass is NOT a task pass.
    - full_passes: attempts whose functional AND compatibility groups all
      pass (non-vacuous: at least one functional group reported). This is
      the primary complete-repair outcome.
    """
    by_cell: dict[tuple, list[dict]] = defaultdict(list)
    for r in run_records:
        by_cell[(r["task_id"], r["condition"], r.get("model", "?"))].append(r)
    cells = []
    for (task_id, condition, model), attempts in sorted(by_cell.items()):
        fpasses = sum(1 for a in attempts if a.get("score", {}).get("passed"))
        full = sum(1 for a in attempts if a.get("full_passed"))
        tok = [a.get("evidence_tokens") for a in attempts]
        tiers = sorted({a.get("tier", "?") for a in attempts})
        cells.append(
            {
                "task_id": task_id,
                "condition": condition,
                "model": model,
                "tier": tiers[0] if len(tiers) == 1 else tiers,
                "attempts": len(attempts),
                "functional_passes": fpasses,
                "functional_pass_rate": round(fpasses / len(attempts), 3) if attempts else 0.0,
                "full_passes": full,
                "full_pass_rate": round(full / len(attempts), 3) if attempts else 0.0,
                "totals": [a.get("score", {}).get("total") for a in attempts],
                "evidence_tokens": tok,
                "replayed": any(a.get("replayed") for a in attempts),
            }
        )
    return {
        "pilot": True,
        "warning": (
            "Small pilot: per-task outcomes and raw attempt counts only. "
            "Do not claim population-level conclusions or statistical "
            "significance from this sample."
        ),
        "n_runs": len(run_records),
        "cells": cells,
        "runs": run_records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Debugging-evidence pilot report",
        "",
        "> " + report.get("warning", ""),
        "",
        f"Total runs: {report['n_runs']}",
        "",
        "Packet sizes differ by condition by design (combined carries more);",
        "read pass rates as 'which realistic packet works best', not as",
        "evidence-type attribution. See `evidence_tokens` per cell.",
        "",
        "## Outcomes by task x condition x model",
        "",
        "functional = functional groups all pass (NOT a task pass). "
        "full = functional + compatibility groups all pass (complete repair).",
        "",
        "| task | condition | model | attempts | funct_pass | full_pass | totals | evid_tokens | replayed |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in report["cells"]:
        lines.append(
            f"| {c['task_id']} | {c['condition']} | {c.get('model', '?')} | {c['attempts']} | {c['functional_passes']} "
            f"| {c['full_passes']} | {c['totals']} | {c['evidence_tokens']} | {c['replayed']} |"
        )
    lines += ["", "## Runs (trajectory summaries + failure labels)", ""]
    for r in report["runs"]:
        lines.append(f"### {r['run_id']} ({r['task_id']} / {r['condition']} / "
                     f"{r.get('model', '?')}:{r.get('tier', '?')})")
        if r.get("replayed"):
            lines.append("- REPLAYED fixture data; not a model result.")
        lines.append(f"- runner: {r.get('runner')}; isolation: {r.get('isolation')}; "
                     f"commit: {r.get('harness_commit')}")
        hg = r.get("human_grade")
        lines.append("- human grade: " + (
            f"graded by {hg.get('grader')}" if hg else "PENDING (not a zero)"))
        if r.get("full_passed"):
            lines.append("- outcome: FULL PASS (functional + compatibility groups green)")
        elif (r.get("score", {}) or {}).get("passed"):
            lines.append("- outcome: FUNCTIONAL-ONLY (compat failed; not a task pass)")
        else:
            lines.append("- outcome: FAIL (a functional group failed or the oracle "
                         "reported no groups)")
        ts = r.get("trajectory_summary", {})
        lines.append(f"- events: {ts.get('n_events')}; evidence opened: {ts.get('evidence_opened')}")
        lines.append(f"- tests: {ts.get('tests')}")
        lines.append(f"- files changed: {ts.get('files_changed')}")
        lines.append(f"- score: {r.get('score')}")
        lines.append(f"- efficiency: {r.get('efficiency')}")
        for fl in r.get("failure_labels", []):
            lines.append(
                f"- failure `{fl.get('label')}` -> event seqs {fl.get('event_seqs')} "
                f"(observed: {fl.get('observed')}; interpretation: {fl.get('interpretation')})"
            )
        lines.append("")
    return "\n".join(lines)
