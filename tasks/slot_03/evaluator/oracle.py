"""Slot-03 oracle (evaluator-only). Behavior checks via GROUP protocol."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def fresh_scratch(workspace):
    tmp = Path(tempfile.mkdtemp(prefix="s03-"))
    for item in Path(workspace).iterdir():
        dest = tmp / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    return tmp


def run_cli(workdir, *args, fake_now=None):
    env = dict(os.environ)
    if fake_now is not None:
        env["FAKE_NOW"] = str(fake_now)
    return subprocess.run(
        [sys.executable, "app.py", *args], cwd=workdir, env=env,
        capture_output=True, text=True, timeout=60)


def check(name, cond, detail=""):
    print(f"GROUP {name} {'PASS' if cond else 'FAIL'} {detail}")
    return cond


def main():
    workspace = Path(sys.argv[1])
    ok = True

    # entry readable before TTL passes
    w = fresh_scratch(workspace)
    run_cli(w, "put", "k", "v", "--ttl", "100", fake_now=1000)
    r = run_cli(w, "get", "k", fake_now=1050)
    ok &= check("fresh_hit", "HIT v" in r.stdout, "read inside TTL hits")

    # entry expires after TTL passes
    w = fresh_scratch(workspace)
    run_cli(w, "put", "k", "v", "--ttl", "100", fake_now=1000)
    r = run_cli(w, "get", "k", fake_now=1200)
    ok &= check("expired_miss", r.stdout.strip() == "MISS",
                f"read 200s after 100s TTL misses ({r.stdout.strip()})")

    # prune drops only the expired entry
    w = fresh_scratch(workspace)
    run_cli(w, "put", "old", "1", "--ttl", "100", fake_now=1000)
    run_cli(w, "put", "new", "2", "--ttl", "10000", fake_now=1150)
    r = run_cli(w, "prune", fake_now=1200)
    data = json.loads((w / "cache.json").read_text())
    ok &= check("prune_expired_only",
                "pruned 1" in r.stdout and set(data.keys()) == {"new"},
                f"prune removes only expired ({r.stdout.strip()})")

    # existing interfaces
    w = fresh_scratch(workspace)
    r = run_cli(w, "put", "k", "v", "--ttl", "100", fake_now=1000)
    ok &= check("compat:cli_put", r.returncode == 0 and "stored k ttl=100" in r.stdout,
                "put prints stored line")
    data = json.loads((w / "cache.json").read_text())
    entry = data["k"]
    ok &= check("compat:entry_schema",
                set(entry.keys()) == {"value", "ts", "ttl"}
                and entry["value"] == "v" and entry["ttl"] == 100,
                "entry stays {value, ts, ttl}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
