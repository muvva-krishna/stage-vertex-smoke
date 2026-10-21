"""AgentRunner interface, ReplayRunner, and isolated run workspaces.

Evaluator-only files (oracle, hidden tests, answers) must never be placed
inside the agent workspace. The workspace layout per attempt is:

  runs/<run_id>/
    trajectory.jsonl
    run_meta.json
    workspace/     <- agent-accessible files only
    evaluator/     <- oracle + hidden checks, NOT visible to the agent
    diff.patch
    score.json
"""
from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .conditions import EvidencePacket
from .trajectory import TrajectoryRecorder, read_jsonl


@dataclass
class AttemptContext:
    run_id: str
    task_id: str
    condition: str
    workspace_dir: Path
    evidence: EvidencePacket
    allowed_tools: list[str]
    limits: dict[str, Any]
    tracker: Any = None  # LimitsTracker, attached by the harness per attempt


class ToolBudgetExceeded(Exception):
    """Raised when no further tool calls are allowed in this attempt."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind  # "tool_calls" or "wall_clock"


class LimitsTracker:
    """Per-attempt enforcement of tool-call and wall-clock budgets.

    Cooperative for in-process runners: every toolkit operation calls
    `use_tool()` first, which raises ToolBudgetExceeded past the budget.
    This cannot preempt a runner stuck in pure computation without tool
    calls — see cli._run_once notes on the subprocess boundary.
    """

    def __init__(self, max_tool_calls: int = 60, max_wall_seconds: int = 1800):
        import time as _time

        self.max_tool_calls = max_tool_calls
        self.max_wall_seconds = max_wall_seconds
        self.tool_calls = 0
        self._t0 = _time.time()
        self._time = _time
        self.tool_limit_reached = False
        self.wall_limit_reached = False

    def elapsed(self) -> float:
        return self._time.time() - self._t0

    def remaining_wall(self) -> float:
        return self.max_wall_seconds - self.elapsed()

    def use_tool(self, op: str) -> int:
        if self.elapsed() >= self.max_wall_seconds:
            self.wall_limit_reached = True
            raise ToolBudgetExceeded("wall_clock", f"op {op!r} after deadline")
        if self.tool_calls >= self.max_tool_calls:
            self.tool_limit_reached = True
            raise ToolBudgetExceeded("tool_calls", f"op {op!r} over budget")
        self.tool_calls += 1
        return self.tool_calls

    def status(self) -> dict[str, Any]:
        return {
            "max_tool_calls": self.max_tool_calls,
            "max_wall_seconds": self.max_wall_seconds,
            "tool_calls_used": self.tool_calls,
            "elapsed_s": round(self.elapsed(), 2),
            "tool_limit_reached": self.tool_limit_reached,
            "wall_limit_reached": self.wall_limit_reached,
        }


@dataclass
class AttemptResult:
    diagnosis: str = ""  # short user-visible diagnosis (not chain-of-thought)
    verification_summary: str = ""  # short user-visible verification summary
    extra_events: list[dict[str, Any]] = field(default_factory=list)
    replayed: bool = False


class AgentRunner(ABC):
    """Interface for connecting a local or hosted coding agent later."""

    @abstractmethod
    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder) -> AttemptResult:
        """Drive the agent inside ctx.workspace_dir. Must not touch evaluator/."""


class ReplayRunner(AgentRunner):
    """Replays recorded example events. Output is NEVER a real model run."""

    def __init__(self, replay_path: str | Path):
        self.replay_path = Path(replay_path)

    # Harness-owned event types are never replayed: the loader records the
    # true per-condition evidence itself, and run_start/run_end/diff belong
    # to the current run. Replaying them would leak cross-condition data
    # (e.g. evidence files not supplied in this condition) into the trace.
    SKIP_REPLAY_TYPES = frozenset({"run_start", "run_end", "evidence_access", "diff"})

    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder) -> AttemptResult:
        raw = read_jsonl(self.replay_path)
        if raw and raw[0].get("data", {}).get("fixture_marker") != "plumbing-only":
            raise ValueError("replay file is not labeled as plumbing-only fixture data")
        for entry in raw:
            etype = entry.get("type", "agent_note")
            if etype in self.SKIP_REPLAY_TYPES:
                continue
            data = dict(entry.get("data", {}))
            data["replayed"] = True
            try:
                recorder.record(etype, data)
            except ValueError:
                recorder.record("agent_note", {"text": json.dumps(data)[:500]})
        # Apply any fixture file_writes from the replay into the workspace so the
        # oracle has something deterministic to score.
        for entry in raw:
            d = entry.get("data", {})
            if entry.get("type") == "file_write" and "path" in d and "content" in d:
                target = ctx.workspace_dir / d["path"]
                if _is_within(ctx.workspace_dir, target):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(d["content"], encoding="utf-8")
        return AttemptResult(
            diagnosis="REPLAYED fixture diagnosis (not a model output)",
            verification_summary="REPLAYED fixture verification (not a model output)",
            replayed=True,
        )


class NoopRunner(AgentRunner):
    """Placeholder runner used when no agent is connected. Makes no edits."""

    def run(self, ctx: AttemptContext, recorder: TrajectoryRecorder) -> AttemptResult:
        recorder.record("agent_note", {"text": "noop: no agent connected"})
        return AttemptResult(
            diagnosis="no agent connected",
            verification_summary="no verification performed",
        )


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def prepare_run_dirs(
    runs_root: str | Path, run_id: str, repo_source: str | Path
) -> dict[str, Path]:
    """Create an isolated workspace copy; evaluator dir stays outside it."""
    runs_root = Path(runs_root)
    run_dir = runs_root / run_id
    workspace = run_dir / "workspace"
    evaluator = run_dir / "evaluator"
    if run_dir.exists():
        raise FileExistsError(f"run dir already exists: {run_dir}")
    workspace.mkdir(parents=True)
    evaluator.mkdir(parents=True)
    repo_source = Path(repo_source)
    if repo_source.is_dir():
        for item in repo_source.iterdir():
            dest = workspace / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
    return {"run_dir": run_dir, "workspace": workspace, "evaluator": evaluator}


def diff_workspace(workspace: Path, baseline: dict[str, str]) -> str:
    """Compact diff summary of workspace files vs baseline {relpath: content}."""
    lines: list[str] = []
    current: dict[str, str] = {}
    for p in sorted(workspace.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(workspace))
            current[rel] = p.read_text(encoding="utf-8", errors="replace")
    for rel in sorted(set(baseline) | set(current)):
        old, new = baseline.get(rel), current.get(rel)
        if old is None:
            lines.append(f"+++ ADDED {rel} ({len(new.splitlines())} lines)")
        elif new is None:
            lines.append(f"--- REMOVED {rel}")
        elif old != new:
            old_lines, new_lines = old.splitlines(), new.splitlines()
            lines.append(f"~~~ MODIFIED {rel} ({len(old_lines)} -> {len(new_lines)} lines)")
    if not lines:
        lines.append("(no changes)")
    return "\n".join(lines)


def snapshot_workspace(workspace: Path) -> dict[str, str]:
    snap: dict[str, str] = {}
    for p in sorted(workspace.rglob("*")):
        if p.is_file():
            snap[str(p.relative_to(workspace))] = p.read_text(
                encoding="utf-8", errors="replace"
            )
    return snap
