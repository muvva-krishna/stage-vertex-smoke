"""Correctness oracle interface.

The oracle runs existing + hidden evaluator checks OUTSIDE the agent
workspace. The agent workspace is passed read-only; the oracle itself lives
in the run's evaluator/ directory (or the task's evaluator source) which the
agent can never read.
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OracleGroupResult:
    group: str
    passed: bool
    detail: str = ""


@dataclass
class OracleResult:
    passed: bool
    groups: list[OracleGroupResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    isolation: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "groups": [
                {"group": g.group, "passed": g.passed, "detail": g.detail}
                for g in self.groups
            ],
            "returncode": self.returncode,
            "isolation": self.isolation,
        }


class Oracle(ABC):
    @abstractmethod
    def run(self, workspace: Path, evaluator_dir: Path) -> "OracleResult":
        raise NotImplementedError


def run_oracle_script(
    workspace: Path, evaluator_dir: Path, entry_point: str = "oracle.py"
) -> OracleResult:
    """Run <evaluator_dir>/<entry_point> with workspace path as argv[1].

    The script must print one line per group: `GROUP <name> PASS|FAIL <detail>`,
    and exit 0 iff all groups pass. Anything else is scored as failure.

    The script executes with cwd locked to the evaluator dir, a scrubbed
    environment, and bwrap confinement when available (see debev.sandbox).
    The recorded `isolation` level states what actually confined the run —
    "bwrap-sandbox" or "fs-separation" (same-filesystem directory
    separation only; NOT a container boundary).
    """
    from .sandbox import run_command

    script = Path(evaluator_dir) / entry_point
    if not script.is_file():
        return OracleResult(
            passed=False,
            groups=[],
            stderr=f"oracle entry point not found: {script}",
            returncode=127,
            isolation="none",
        )
    res = run_command(
        [sys.executable, str(script), str(workspace)],
        cwd=Path(evaluator_dir),
        timeout=300,
        extra_mounts=[(str(workspace), "/workspace", "ro")],
    )
    groups: list[OracleGroupResult] = []
    for line in res.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) >= 3 and parts[0] == "GROUP":
            _, name, verdict, *rest = parts
            groups.append(
                OracleGroupResult(
                    group=name,
                    passed=verdict.upper() == "PASS",
                    detail=rest[0] if rest else "",
                )
            )
    passed = res.returncode == 0 and bool(groups) and all(g.passed for g in groups)
    return OracleResult(
        passed=passed,
        groups=groups,
        stdout=res.stdout[-4000:],
        stderr=res.stderr[-4000:],
        returncode=res.returncode,
        isolation=res.isolation,
    )
