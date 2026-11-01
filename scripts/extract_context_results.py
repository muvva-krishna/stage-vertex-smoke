"""Extract the detector's final JSON from raw CLI event logs.

Reads raw v2 logs, label-free detector inputs, and evaluator-only randomized-ID
map to restore slot IDs after the call. Writes to results_v2/; never overwrites
the v1 result files. Labels are not used.

Usage: python3 scripts/extract_context_results.py [--raw DIR] [--out DIR]
Defaults: stage4_context_grid/results/raw_v2 -> stage4_context_grid/results_v2.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "stage4_context_grid"
RAW = BASE / (sys.argv[sys.argv.index("--raw") + 1] if "--raw" in sys.argv else "results/raw_v2")
RESULTS = BASE / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "results_v2")
INPUTS = BASE / "detector_inputs"
EVALUATOR = BASE / "evaluator_only"


def final_text(events_path: Path) -> str:
    texts = []
    for line in events_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        part = event.get("part") or {}
        if part.get("type") == "text" and part.get("text"):
            texts.append(part["text"])
    return "\n".join(texts)


def parse_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def main() -> int:
    problems = []
    written = 0
    id_map_cache = {}
    for size in ("N1", "N4", "N8"):
        out_dir = RESULTS / size
        out_dir.mkdir(parents=True, exist_ok=True)
        for events in sorted((RAW / size).glob("*.jsonl")):
            cluster_id = events.stem
            input_path = INPUTS / size / f"{cluster_id}.json"
            expected = json.loads(input_path.read_text())
            try:
                doc = parse_json(final_text(events))
            except Exception as exc:
                problems.append(f"{size}/{cluster_id}: no parseable JSON ({exc})")
                continue
            # V2 emits trajectory IDs that are random and label-blind. Restore
            # internal slot IDs only in this parent-side extraction step.
            if isinstance(doc.get("trajectories"), list):
                suffix = "_batch2" if cluster_id.startswith("D") else ""
                map_path = EVALUATOR / f"rendered_prompt_manifest_v2{suffix}_EVALUATOR_ONLY.json"
                if map_path not in id_map_cache:
                    manifest = json.loads(map_path.read_text())
                    id_map_cache[map_path] = {
                        run["cluster_id"]: {m["trajectory_id"]: m["slot_id"]
                                            for m in run_map["trajectory_map"]}
                        for run, run_map in zip(manifest["runs"], manifest["trajectory_id_maps"])
                    }
                mapping = id_map_cache[map_path].get(cluster_id, {})
                slots = []
                for trajectory in doc["trajectories"]:
                    trajectory_id = trajectory.get("trajectory_id")
                    if trajectory_id not in mapping:
                        problems.append(f"{size}/{cluster_id}: unknown trajectory_id {trajectory_id}")
                        continue
                    slots.append({**{k:v for k,v in trajectory.items() if k != "trajectory_id"},
                                  "slot_id": mapping[trajectory_id]})
                schema = "v2"
            else:
                slots = doc.get("slots")
                schema = "v1"
            if not isinstance(slots, list):
                problems.append(f"{size}/{cluster_id}: missing trajectories/slots list")
                continue
            got = {s.get("slot_id") for s in slots if isinstance(s, dict)}
            want = {s["slot_id"] for s in expected["slots"]}
            if got != want:
                problems.append(f"{size}/{cluster_id}: slot mismatch got={sorted(got)} want={sorted(want)}")
                continue
            missing = [s["slot_id"] for s in slots if "is_hack" not in s]
            if missing:
                problems.append(f"{size}/{cluster_id}: slots missing is_hack: {missing}")
                continue
            doc.setdefault("cluster_id", cluster_id)
            doc["n"] = len(slots)
            doc["detector_model"] = "opencode-go/muse-spark-1.3-contributor#high"
            doc["prompt_version"] = schema
            doc["slots"] = slots
            doc.pop("trajectories", None)
            (out_dir / f"{cluster_id}.json").write_text(json.dumps(doc, indent=1))
            written += 1
    print(f"extracted {written} result files")
    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print("-", problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
