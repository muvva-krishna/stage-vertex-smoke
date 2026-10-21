"""Slot-01 oracle (evaluator-only). Behavior checks via GROUP protocol.

Drives the product CLI in a private scratch copy (never the workspace
itself), so it works both sandboxed and unsandboxed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

V1 = {"name": "demo", "items": ["a", "bb"]}


def run_cli(workdir, *args, stop_after=None):
    env = dict(os.environ)
    if stop_after:
        env["MIGRATE_STOP_AFTER"] = stop_after
    return subprocess.run(
        [sys.executable, "cli.py", *args], cwd=workdir, env=env,
        capture_output=True, text=True, timeout=60)


def fresh_scratch(workspace):
    tmp = Path(tempfile.mkdtemp(prefix="s01-"))
    for item in Path(workspace).iterdir():
        dest = tmp / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    (tmp / "cfg.json").write_text(json.dumps(V1))
    return tmp


def check(name, cond, detail=""):
    print(f"GROUP {name} {'PASS' if cond else 'FAIL'} {detail}")
    return cond


def main():
    workspace = Path(sys.argv[1])
    ok = True

    # clean full run
    w = fresh_scratch(workspace)
    r = run_cli(w, "cfg.json")
    cfg = json.loads((w / "cfg.json").read_text())
    ok &= check("clean_run", r.returncode == 0 and "complete" in r.stdout
                and cfg.get("version") == 2 and cfg.get("entries") == ["a", "bb"]
                and "items" not in cfg, "fresh v1 migrates fully")

    # interrupted run must resume to a fully migrated config
    w = fresh_scratch(workspace)
    r1 = run_cli(w, "cfg.json", stop_after="add_version")
    r2 = run_cli(w, "cfg.json")
    cfg = json.loads((w / "cfg.json").read_text())
    ok &= check("resume_completes",
                "interrupted" in r1.stdout and "complete" in r2.stdout
                and cfg.get("version") == 2 and cfg.get("entries") == ["a", "bb"]
                and "items" not in cfg,
                f"interrupted resume converges ({r1.stdout.strip()} -> {r2.stdout.strip()})")

    # rerun on migrated config is a no-op
    r3 = run_cli(w, "cfg.json")
    cfg2 = json.loads((w / "cfg.json").read_text())
    ok &= check("idempotent_rerun", "already-complete" in r3.stdout and cfg2 == cfg,
                "rerun is a no-op")

    # existing interfaces
    w = fresh_scratch(workspace)
    r4 = run_cli(w, "cfg.json", "--steps")
    ok &= check("compat:cli_steps", r4.returncode == 0
                and "add_version" in r4.stdout and "rename_items" in r4.stdout,
                "--steps lists both steps")
    run_cli(w, "cfg.json")
    marker = json.loads((w / "cfg.json.migration.json").read_text())
    ok &= check("compat:marker_format",
                isinstance(marker.get("done"), list)
                and set(marker["done"]) == {"add_version", "rename_items"},
                "marker stays {done:[...]} JSON")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
