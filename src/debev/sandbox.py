"""Sandbox execution for agent commands and oracle runs.

Honest isolation model:
  - Always: agent/oracle subprocesses run with a scrubbed environment
    (small allowlist; secrets are never forwarded) and a timeout.
  - Best effort: if `bwrap` (bubblewrap) is installed, the subprocess is
    confined under a tmpfs root so the host filesystem is hidden: only the
    given working directory is visible read-write, plus read-only
    interpreter libraries. The evaluator directory and the rest of the
    host filesystem are not mounted and not reachable.
  - Fallback: plain filesystem separation (workspace vs evaluator
    directories). This does NOT stop a malicious agent that reaches for
    parent paths — it only keeps honest agents out of evaluator files.

The actual level used is detected per run and recorded in run_meta.json
as `isolation` ("bwrap-sandbox" or "fs-separation"). Reports must describe
the recorded level, never claim a container boundary that was not used.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SAFE_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "TZ", "PYTHONHASHSEED")


_BWRAP_PROBE: bool | None = None


def _bwrap_prefix(workdir: Path, extra_mounts: list[tuple]) -> list[str]:
    """Prefix hiding the host filesystem (tmpfs root) and exposing only
    workdir at /work (rw), extra mounts, + interpreter libs (ro)."""
    prefix = [
        "bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--tmpfs", "/",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--bind", str(workdir), "/work",
        "--tmpfs", "/tmp",
        "--chdir", "/work",
    ]
    for host, sb, mode in extra_mounts:
        prefix += ["--bind" if mode == "rw" else "--ro-bind", str(host), sb]
    return prefix


def _bwrap_usable() -> bool:
    """Probe once per process whether bwrap confinement actually works here
    (binary present, user namespaces allowed, interpreter reachable)."""
    global _BWRAP_PROBE
    if _BWRAP_PROBE is not None:
        return _BWRAP_PROBE
    import tempfile

    _BWRAP_PROBE = False
    if shutil.which("bwrap") and sys.executable.startswith("/usr/"):
        try:
            with tempfile.TemporaryDirectory(prefix="debev-probe-") as tmp:
                proc = subprocess.run(
                    _bwrap_prefix(Path(tmp), []) + [sys.executable, "-c", "pass"],
                    capture_output=True, text=True, timeout=30,
                    env=scrubbed_env(),
                )
                _BWRAP_PROBE = proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            _BWRAP_PROBE = False
    return _BWRAP_PROBE


def detect_isolation() -> str:
    if _bwrap_usable():
        return "bwrap-sandbox"
    return "fs-separation"


def _map_args(cmd: list[str], mounts: list[tuple]) -> list[str]:
    """Rewrite host-absolute args under a mount to their sandbox paths."""
    out = []
    for arg in cmd:
        for host, sb, _mode in mounts:
            h = str(host)
            if arg == h:
                arg = sb
                break
            if arg.startswith(h + "/"):
                arg = sb + arg[len(h):]
                break
        out.append(arg)
    return out


def scrubbed_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: os.environ[k] for k in SAFE_ENV_ALLOWLIST if k in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin")
    if extra:
        env.update(extra)
    return env


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    isolation: str


def run_command(
    cmd: list[str],
    cwd: Path,
    timeout: int = 300,
    extra_env: dict[str, str] | None = None,
    extra_mounts: list[tuple] | None = None,
) -> ExecResult:
    """Run cmd with cwd locked to `cwd`, scrubbed env, and bwrap if usable.

    extra_mounts: [(host_path, sandbox_path, "ro"|"rw")] — e.g. the oracle
    mounts the agent workspace read-only at /workspace while cwd is the
    evaluator dir (/work). Host-absolute cmd args under any mount are
    rewritten to their sandbox paths.
    """
    extra_mounts = extra_mounts or []
    mounts = [(Path(cwd), "/work", "rw")] + [
        (Path(h), sb, mode) for h, sb, mode in extra_mounts
    ]
    use_bwrap = _bwrap_usable()
    isolation = "bwrap-sandbox" if use_bwrap else "fs-separation"
    full_cmd = (_bwrap_prefix(Path(cwd), extra_mounts) + _map_args(cmd, mounts)
                if use_bwrap else cmd)
    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=None if use_bwrap else str(cwd),
            env=scrubbed_env(extra_env),
        )
        return ExecResult(proc.returncode, proc.stdout[-6000:], proc.stderr[-6000:], isolation)
    except subprocess.TimeoutExpired as e:
        return ExecResult(124, str(e.stdout or ""), "TIMEOUT", isolation)
    except (OSError, FileNotFoundError):
        # bwrap failed at spawn despite a passing probe: fall back once.
        if use_bwrap:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
                env=scrubbed_env(extra_env),
            )
            return ExecResult(
                proc.returncode, proc.stdout[-6000:], proc.stderr[-6000:], "fs-separation"
            )
        raise
