"""Example external agent adapters (import via --runner module:Class).

- BaselineProbeRunner: a real, deterministic, local-only investigation probe.
  It actually reads the evidence + repo files and actually executes import
  checks, recording genuine trajectory events. It attempts NO repair, so its
  oracle score is whatever the broken starting state earns. Use it to verify
  that tool actions flow into the trajectory — not as a model result.
- ScriptedFixtureRepairRunner: a fixture-specific scripted repair used only
  for harness plumbing (like ReplayRunner, but with live tool calls instead
  of replayed events). Labeled plumbing-only everywhere. Never point it at a
  real task.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debev.runners import AttemptContext, AgentRunner  # noqa: E402
from debev.toolkit import Toolkit  # noqa: E402
from debev.trajectory import TrajectoryRecorder  # noqa: E402


class BaselineProbeRunner(AgentRunner):
    """Local-only baseline: investigate + run checks, never edit."""

    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder):
        from debev.runners import AttemptResult

        tk = Toolkit(ctx, recorder)
        tk.read("TASK_INSTRUCTIONS.md") if (ctx.workspace_dir / "TASK_INSTRUCTIONS.md").is_file() else None
        py_files = sorted(
            str(p.relative_to(ctx.workspace_dir))
            for p in ctx.workspace_dir.rglob("*.py")
            if "evaluator" not in p.parts
        )[:20]
        for rel in py_files:
            tk.read(rel)
        results = []
        for rel in py_files:
            results.append(tk.test(f"compile:{rel}", [sys.executable, "-m", "py_compile", rel]))
        overall = "PASS" if results and all(r == "PASS" for r in results) else (
            "FAIL" if results else "INCONCLUSIVE")
        tk.verify("baseline-import-check", overall,
                  f"py_compile over {len(py_files)} file(s); no repair attempted")
        return AttemptResult(
            diagnosis="baseline probe: investigation only, no repair attempted",
            verification_summary=f"baseline probe ran py_compile on {len(py_files)} file(s): {overall}",
        )


class ScriptedFixtureRepairRunner(AgentRunner):
    """PLUMBING ONLY: scripted repair for the counter fixture. Not a model."""

    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder):
        from debev.runners import AttemptResult

        if ctx.task_id != "fixture-plumbing":
            raise ValueError("ScriptedFixtureRepairRunner is fixture-only; refusing real task")
        tk = Toolkit(ctx, recorder)
        src = tk.read("counter.py")
        assert "a + b + 1" in src, "fixture precondition changed; aborting scripted repair"
        tk.exec([sys.executable, "-c", "from counter import add; print(add(1, 2))"])
        tk.write(
            "counter.py",
            'def add(a, b):\n    """Return a + b."""\n    return a + b\n\n\n'
            'def format_total(a, b):\n    return f"{a}+{b}={add(a, b)}"\n',
        )
        check = tk.test("scripted-repro-check",
                        [sys.executable, "-c", "from counter import add; assert add(1, 2) == 3"])
        tk.verify("scripted-repro-claim", check,
                  "executed repro check via toolkit (scripted, fixture-only)")
        return AttemptResult(
            diagnosis="SCRIPTED fixture repair (not a model output): removed +1",
            verification_summary="SCRIPTED fixture verification (not a model output)",
        )
