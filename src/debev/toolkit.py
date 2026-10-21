"""Minimal tool callbacks for connecting a real agent.

This is an adapter surface, not a framework: small functions bound to
one attempt. Every call enforces the workspace boundary, consumes the
per-attempt tool/wall budget (raising ToolBudgetExceeded past it), and
records an observable trajectory event. Agents built elsewhere import
this module and receive a `Toolkit` — they never touch the recorder or
filesystem directly.

Policy decisions (what to read, run, or edit) belong to the agent, not here.

Trust note: custom AgentRunner *code* runs in-process and is trusted like
harness code. Confinement (workspace-only paths, scrubbed env, bwrap where
available) applies to actions mediated here and to the commands they spawn —
not to arbitrary code in a custom runner. See docs/evaluation_protocol.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runners import AttemptContext, LimitsTracker, ToolBudgetExceeded
from .sandbox import run_command
from .trajectory import TrajectoryRecorder


def _resolve(workspace: Path, relpath: str) -> Path:
    target = (workspace / relpath).resolve()
    if target != workspace.resolve() and workspace.resolve() not in target.parents:
        raise PermissionError(f"path escapes workspace: {relpath!r}")
    return target


def _is_timeout(rc: int, stderr: str) -> bool:
    return rc == 124 and "TIMEOUT" in stderr


@dataclass
class Toolkit:
    ctx: AttemptContext
    recorder: TrajectoryRecorder
    tracker: LimitsTracker | None = None

    def __post_init__(self):
        if self.tracker is None:
            if getattr(self.ctx, "tracker", None) is not None:
                self.tracker = self.ctx.tracker
            else:
                limits = self.ctx.limits or {}
                self.tracker = LimitsTracker(
                    max_tool_calls=int(limits.get("max_tool_calls", 60)),
                    max_wall_seconds=int(limits.get("max_wall_seconds", 1800)),
                )

    def _spend(self, op: str) -> None:
        try:
            self.tracker.use_tool(op)
        except ToolBudgetExceeded as e:
            self.recorder.record(
                "limit_exceeded", {"kind": e.kind, "op": op}
            )
            raise

    def _cmd_timeout(self, timeout: int | None) -> int:
        if timeout is not None:
            return timeout
        try:
            return int((self.ctx.limits or {}).get("per_command_timeout", 120))
        except (TypeError, ValueError):
            return 120

    def read(self, relpath: str, max_chars: int = 20000) -> str:
        self._spend("read")
        target = _resolve(self.ctx.workspace_dir, relpath)
        text = target.read_text(encoding="utf-8", errors="replace")[:max_chars]
        self.recorder.record("file_read", {"path": relpath, "chars": len(text)})
        return text

    def write(self, relpath: str, content: str) -> None:
        self._spend("write")
        target = _resolve(self.ctx.workspace_dir, relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.recorder.record(
            "file_write", {"path": relpath, "chars": len(content)}
        )

    def exec(self, cmd: list[str], timeout: int | None = None) -> dict:
        self._spend("exec")
        timeout = self._cmd_timeout(timeout)
        res = run_command(cmd, self.ctx.workspace_dir, timeout=timeout)
        self.recorder.record(
            "command",
            {"cmd": " ".join(cmd)[:500], "rc": res.returncode,
             "isolation": res.isolation},
        )
        if _is_timeout(res.returncode, res.stderr):
            self.recorder.record(
                "timeout", {"kind": "command", "cmd": " ".join(cmd)[:500],
                            "timeout_s": timeout}
            )
        return {"rc": res.returncode, "stdout": res.stdout, "stderr": res.stderr}

    def test(self, name: str, cmd: list[str], timeout: int | None = None) -> str:
        """Run an executed check; records a test_run with an explicit result.

        A TIMEOUT maps to INCONCLUSIVE (the check did not complete), never
        to a pass. The `via: toolkit` marker proves the check was executed
        through this adapter rather than self-reported — only such events
        earn machine verification credit (see cli._agent_verification_ran).
        """
        self._spend("test")
        timeout = self._cmd_timeout(timeout)
        res = run_command(cmd, self.ctx.workspace_dir, timeout=timeout)
        if _is_timeout(res.returncode, res.stderr):
            result = "INCONCLUSIVE"
            self.recorder.record(
                "timeout", {"kind": "test", "name": name, "timeout_s": timeout}
            )
        else:
            result = "PASS" if res.returncode == 0 else "FAIL"
        self.recorder.record(
            "test_run",
            {"name": name, "result": result, "rc": res.returncode,
             "via": "toolkit",
             "output": (res.stdout + res.stderr)[-1000:]},
        )
        return result

    def verify(self, name: str, result: str, detail: str = "") -> None:
        """Agent's explicit final claim about what it ran and observed.

        Free-form/self-reported: recorded for human grading of reporting
        accuracy, but NEVER earns machine verification credit on its own.
        """
        if result not in ("PASS", "FAIL", "ERROR", "INCONCLUSIVE"):
            raise ValueError(f"bad verification result: {result!r}")
        self.recorder.record("verification", {"name": name, "result": result,
                                              "detail": detail[:1000]})
