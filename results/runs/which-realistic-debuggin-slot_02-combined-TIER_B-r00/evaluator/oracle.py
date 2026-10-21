"""Slot-02 oracle (evaluator-only). Behavior checks via GROUP protocol."""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DUP_CSV = "name,email\nAnn,A@x.com\nAnn2, a@x.com\nAnn3,A@X.COM \n"
MIX_CSV = "name,email\nAnn,A@x.com\nBob,b@x.com\nAnn2, a@x.com\n"


def fresh_scratch(workspace):
    tmp = Path(tempfile.mkdtemp(prefix="s02-"))
    for item in Path(workspace).iterdir():
        dest = tmp / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    return tmp


def run_import(workdir, csv_text, store="store.json"):
    (workdir / "in.csv").write_text(csv_text)
    return subprocess.run(
        [sys.executable, "importer.py", "in.csv", store],
        cwd=workdir, capture_output=True, text=True, timeout=60)


def check(name, cond, detail=""):
    print(f"GROUP {name} {'PASS' if cond else 'FAIL'} {detail}")
    return cond


def main():
    workspace = Path(sys.argv[1])
    ok = True

    w = fresh_scratch(workspace)
    r = run_import(w, DUP_CSV)
    store = json.loads((w / "store.json").read_text())
    ok &= check("dedup_case_variants",
                r.returncode == 0 and len(store["rows"]) == 1
                and "imported 1 of 3" in r.stdout,
                f"case/space variants collapse to 1 ({r.stdout.strip()})")

    w = fresh_scratch(workspace)
    r = run_import(w, MIX_CSV)
    store = json.loads((w / "store.json").read_text())
    emails = sorted(row["email"] for row in store["rows"])
    ok &= check("distinct_kept",
                len(store["rows"]) == 2 and "imported 2 of 3" in r.stdout,
                f"distinct addresses kept ({emails})")

    w = fresh_scratch(workspace)
    r1 = run_import(w, MIX_CSV)
    r2 = run_import(w, "name,email\nBob2,B@X.COM\n", store="store.json")
    store = json.loads((w / "store.json").read_text())
    ok &= check("repeat_import_stable", len(store["rows"]) == 2
                and "imported 0 of 1" in r2.stdout,
                "second import adds no duplicates")

    w = fresh_scratch(workspace)
    run_import(w, MIX_CSV)
    store = json.loads((w / "store.json").read_text())
    ok &= check("compat:store_schema",
                set(store.keys()) == {"rows", "seen"}
                and all(set(r.keys()) == {"name", "email"} for r in store["rows"]),
                "store stays {rows, seen} JSON")
    r = subprocess.run([sys.executable, "importer.py", "--help"],
                       cwd=w, capture_output=True, text=True, timeout=60)
    ok &= check("compat:cli_help", r.returncode == 0 and "csv_file" in r.stdout,
                "--help works")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
