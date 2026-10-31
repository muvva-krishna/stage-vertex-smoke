"""Run provenance: content hashes + harness commit for reproducibility."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    """Map relative path -> sha256 for every file under root (sorted)."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = sha256_file(p)
    return out


def harness_commit(repo_root: Path) -> str:
    """Best-effort git commit of the harness repo; 'no-git' when unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "no-git"


def harness_dirty(repo_root: Path) -> bool | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
        )
        if proc.returncode == 0:
            return bool(proc.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return None
