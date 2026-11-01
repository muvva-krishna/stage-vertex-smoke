"""Behavioral checks for the migration-resume task; evaluator only."""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import tempfile
from pathlib import Path


def emit(name: str, passed: bool, detail: str) -> bool:
    print(f"GROUP {name} {'PASS' if passed else 'FAIL'} {detail}")
    return passed


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(workspace))
    migration = importlib.import_module("debev_config.migration")
    cli = importlib.import_module("debev_config.cli")
    results = []
    with tempfile.TemporaryDirectory(prefix="migration-oracle-") as tmp:
        root = Path(tmp)
        # A regular v1 migration preserves arbitrary extension preferences.
        p = root / "fresh.json"
        original = {"schema_version":1,"endpoint":"https://api.example","retries":4,
                    "preferences":{"layout":{"compact":True},"plugin_x":[1,2]}}
        p.write_text(json.dumps(original), encoding="utf-8")
        try:
            got = migration.migrate_file(p)
            ok = (got.get("schema_version") == 2 and
                  got.get("service",{}).get("endpoint") == original["endpoint"] and
                  got.get("retry",{}).get("max_attempts") == 4 and
                  got.get("extensions") == original["preferences"])
        except Exception as exc:
            ok = False
            got = {"error":repr(exc)}
        results.append(emit("fresh_migration", ok, "v1 fields and preferences retained"))

        # Crash after the converted file landed, before the marker was updated.
        p = root / "resume-valid.json"
        target = {"schema_version":2,"service":{"endpoint":"https://api.example"},
                  "retry":{"max_attempts":4},"extensions":{"layout":{"compact":True}}}
        backup = {"schema_version":1,"endpoint":"https://api.example","retries":4,
                  "preferences":{"layout":{"compact":True}}}
        p.write_text(json.dumps(target), encoding="utf-8")
        Path(str(p)+".migration.json").write_text('{"status":"in_progress"}', encoding="utf-8")
        Path(str(p)+".migration.bak").write_text(json.dumps(backup), encoding="utf-8")
        try:
            got = migration.migrate_file(p)
            marker = json.loads(Path(str(p)+".migration.json").read_text())
            ok = got == target and marker.get("status") == "complete"
        except Exception as exc:
            ok = False
            got = {"error":repr(exc)}
        results.append(emit("resume_committed_target", ok, "valid v2 target survives restart"))

        # Crash during target write: the backup is the only complete input.
        p = root / "resume-partial.json"
        p.write_text('{"schema_version":2,"extensions":', encoding="utf-8")
        Path(str(p)+".migration.json").write_text('{"status":"in_progress"}', encoding="utf-8")
        Path(str(p)+".migration.bak").write_text(json.dumps(backup), encoding="utf-8")
        try:
            got = migration.migrate_file(p)
            ok = (got.get("schema_version") == 2 and
                  got.get("extensions") == backup["preferences"] and
                  json.loads(Path(str(p)+".migration.json").read_text()).get("status") == "complete")
        except Exception as exc:
            ok = False
            got = {"error":repr(exc)}
        results.append(emit("resume_partial_target", ok, "partial target recovers from backup"))

        # Once complete, a second call is a no-op, including on-disk bytes.
        p = root / "idempotent.json"
        stable = '{\n  "schema_version": 2,\n  "service": {"endpoint": "x"},\n  "retry": {"max_attempts": 7},\n  "extensions": {"a": 1}\n}\n'
        p.write_text(stable, encoding="utf-8")
        Path(str(p)+".migration.json").write_text('{"status":"complete"}', encoding="utf-8")
        try:
            got = migration.migrate_file(p)
            ok = p.read_text(encoding="utf-8") == stable and got["extensions"] == {"a":1}
        except Exception as exc:
            ok = False
            got = {"error":repr(exc)}
        results.append(emit("completed_idempotence", ok, "completed v2 file remains unchanged"))

        # Preserve the public command-line interface for a normal migration.
        p = root / "cli.json"
        p.write_text(json.dumps({"schema_version":1,"endpoint":"x","retries":2,
                                 "preferences":{"theme":"dark"}}), encoding="utf-8")
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                rc = cli.main(["migrate", str(p)])
            output = json.loads(p.read_text(encoding="utf-8"))
            ok = rc == 0 and "schema version 2" in stdout.getvalue() and output["schema_version"] == 2
        except Exception as exc:
            ok = False
            stdout.write(repr(exc))
        results.append(emit("compat:cli", ok, "migrate command remains available"))

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
