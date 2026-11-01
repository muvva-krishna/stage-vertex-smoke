"""Offline checks for one Stage-4 batch. Does not call models.

Usage: python3 scripts/check_context_size_mix.py [--spec SPEC] [--tag TAG]
Counts derive from the spec (16 clusters per task at N1, 8 at N4, 4 at N8);
only clusters with the spec's ID prefix are counted, so batch-1 stays PASS
after batch-2 files are added.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DETECTOR = ROOT / "stage4_context_grid" / "detector_inputs"
EVALUATOR = ROOT / "stage4_context_grid" / "evaluator_only"
FORBIDDEN_KEYS = {
    "evaluation_label", "is_hack", "classification_explanation", "trajectory_path",
    "task_id", "source_label", "trajectory_id_or_label", "neutral_id", "legacy_n1_id",
    "n_input_tokens", "n_output_tokens", "reward", "label_source", "source_file",
}


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def main() -> int:
    errors = []
    counts = {}
    TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    SPEC = Path(sys.argv[sys.argv.index("--spec") + 1]) if "--spec" in sys.argv else (
        ROOT / "stage4_context_grid" / "pool_spec.json")
    spec = json.loads(SPEC.read_text())
    n_tasks = len(spec["groups"])
    PREFIX = spec.get("cluster_id_prefix", "C")
    for size, expected_n, per_task in (("N1", 1, 16), ("N4", 4, 8), ("N8", 8, 4)):
        expected_files = per_task * n_tasks
        files = sorted(p for p in (DETECTOR / size).glob("*.json")
                       if p.stem.startswith(PREFIX))
        counts[size] = len(files)
        if len(files) != expected_files:
            errors.append(f"{size}: expected {expected_files} files, found {len(files)}")
        for path in files:
            try:
                doc = json.loads(path.read_text())
            except Exception as exc:
                errors.append(f"{path}: invalid JSON: {exc}")
                continue
            if len(doc.get("slots", [])) != expected_n:
                errors.append(f"{path}: expected N={expected_n}")
            bad = sorted(set(walk_keys(doc)) & FORBIDDEN_KEYS)
            if bad:
                errors.append(f"{path}: forbidden fields {bad}")
            for slot in doc.get("slots", []):
                if not slot.get("steps"):
                    errors.append(f"{path}: empty slot {slot.get('slot_id')}")
    # Detect pre-existing explicit truncation markers; never hide them.
    markers = re.compile(r"\(line truncated to \d+ chars\)|\[truncated\]", re.I)
    for path in DETECTOR.rglob("*.json"):
        if markers.search(path.read_text()):
            errors.append(f"{path}: source contains a truncation marker; manual review required")
    # Per-run snapshot must contain only its own prompt (prefix-filtered).
    snapshots = ROOT / "stage4_context_grid" / "agent_snapshots_v2"
    snapshot_dirs = ([p for p in snapshots.iterdir()
                      if p.is_dir() and p.name.startswith(PREFIX)]
                     if snapshots.exists() else [])
    expected_snapshot_count = n_tasks * (16 + 8 + 4)
    if len(snapshot_dirs) != expected_snapshot_count:
        errors.append(f"snapshots: expected {expected_snapshot_count} v2 prompts, found {len(snapshot_dirs)}")
    for run_dir in snapshot_dirs:
        names = {p.name for p in run_dir.iterdir()}
        if names != {"prompt.txt"}:
            errors.append(f"{run_dir}: snapshot has unexpected files {sorted(names)}")
        if (run_dir / "prompt.txt").exists():
            prompt = (run_dir / "prompt.txt").read_text()
            marker = "COMPLETE TRAJECTORY SET:\n"
            try:
                payload = json.loads(prompt.split(marker, 1)[1])
                if set(payload) != {"trajectories"}:
                    errors.append(f"{run_dir}: prompt payload has non-neutral top-level keys {sorted(payload)}")
                expected_trajectories = int(run_dir.name[len(PREFIX)])
                if len(payload["trajectories"]) != expected_trajectories:
                    errors.append(f"{run_dir}: expected {expected_trajectories} trajectories")
                ids = [trajectory.get("trajectory_id") for trajectory in payload["trajectories"]]
                if len(ids) != len(set(ids)) or any(not re.fullmatch(r"T-[0-9a-f]{12}", x or "") for x in ids):
                    errors.append(f"{run_dir}: trajectory IDs are not unique opaque IDs")
                for trajectory in payload["trajectories"]:
                    if set(trajectory) != {"trajectory_id", "steps"}:
                        errors.append(f"{run_dir}: trajectory has unexpected metadata keys {sorted(trajectory)}")
                    for step in trajectory["steps"]:
                        allowed = {"step_id", "source", "message", "tool_calls", "observation"}
                        if set(step) - allowed:
                            errors.append(f"{run_dir}: step contains unexpected keys {sorted(set(step)-allowed)}")
            except Exception as exc:
                errors.append(f"{run_dir}: cannot audit neutral prompt payload ({exc})")
    if errors:
        print("FAIL", counts)
        for error in errors:
            print("-", error)
        return 1
    print("PASS", counts, "(no detector-label fields; cluster sizes/counts valid)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
