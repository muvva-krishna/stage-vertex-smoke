"""Minimal tool callbacks for connecting a real agent.

This is an adapter surface, not a framework: five small functions bound to
one attempt. Every call enforces the workspace boundary and records an
observable trajectory event. Agents built elsewhere import this module and
receive a `Toolkit` — they never touch the recorder or filesystem directly.

Policy decisions (what to read, run, or edit) belong to the agent, not here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runners import AttemptContext
from .sandbox import run_command
from .trajectory import TrajectoryRecorder


def _resolve(workspace: Path, relpath: str) -> Path:
    target = (workspace / relpath).resolve()
    if target != workspace.resolve() and workspace.resolve() not in target.parents:
        raise PermissionError(f"path escapes workspace: {relpath!r}")
    return target


@dataclass
class Toolkit:
    ctx: AttemptContext
    recorder: TrajectoryRecorder

    def read(self, relpath: str, max_chars: int = 20000) -> str:
        target = _resolve(self.ctx.workspace_dir, relpath)
        text = target.read_text(encoding="utf-8", errors="replace")[:max_chars]
        self.recorder.record("file_read", {"path": relpath, "chars": len(text)})
        return text

    def write(self, relpath: str, content: str) -> None:
        target = _resolve(self.ctx.workspace_dir, relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.recorder.record(
            "file_write", {"path": relpath, "chars": len(content)}
        )

    def exec(self, cmd: list[str], timeout: int = 120) -> dict:
        res = run_command(cmd, self.ctx.workspace_dir, timeout=timeout)
        self.recorder.record(
            "command",
            {"cmd": " ".join(cmd)[:500], "rc": res.returncode,
             "isolation": res.isolation},
        )
        return {"rc": res.returncode, "stdout": res.stdout, "stderr": res.stderr}

    def test(self, name: str, cmd: list[str], timeout: int = 120) -> str:
        """Run a check; records a structured test_run (not the oracle)."""
        res = run_command(cmd, self.ctx.workspace_dir, timeout=timeout)
        result = "PASS" if res.returncode == 0 else "FAIL"
        self.recorder.record(
            "test_run",
            {"name": name, "result": result, "rc": res.returncode,
             "output": (res.stdout + res.stderr)[-1000:]},
        )
        return result

    def verify(self, name: str, result: str, detail: str = "") -> None:
        """Agent's explicit structured verification claim.

        `result` in PASS|FAIL|ERROR|INCONCLUSIVE. This is the agent's own
        statement about what it ran and observed — the evaluator's oracle
        run is recorded separately and never counts as agent verification.
        """
        if result not in ("PASS", "FAIL", "ERROR", "INCONCLUSIVE"):
            raise ValueError(f"bad verification result: {result!r}")
        self.recorder.record("verification", {"name": name, "result": result,
                                              "detail": detail[:1000]})
