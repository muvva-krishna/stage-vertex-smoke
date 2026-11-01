"""Build label-free N=1/N=4/N=8 detector clusters from a fetched Stage-4 pool.

Usage: python3 scripts/build_context_size_mix.py [--spec SPEC] [--tag TAG]
Default builds batch 1 (prefix C). Batch 2 uses --spec pool_spec_batch2.json
--tag batch2 (prefix D) so batch-1 clusters, maps, and results stay untouched.

Run only after user approval. This script does no detector calls.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "stage4_context_grid"
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
SUFFIX = f"_{TAG}" if TAG else ""
SPEC = Path(sys.argv[sys.argv.index("--spec") + 1]) if "--spec" in sys.argv else (
    BASE / "pool_spec.json")
PREFIX = json.loads(SPEC.read_text()).get("cluster_id_prefix", "C")
POOL = BASE / "evaluator_only" / f"pool{SUFFIX}_EVALUATOR_ONLY.json"
SOURCE = BASE / "source_trajectories"
DETECTOR = BASE / "detector_inputs"
EVALUATOR = BASE / "evaluator_only"


def steps_for(sample: dict) -> list[dict]:
    trace = json.loads((ROOT / sample["source_file"]).read_text())
    out = []
    for step in trace.get("steps", []):
        item = {"step_id": step.get("step_id"), "source": step.get("source"),
                "message": step.get("message", "")}
        if "tool_calls" in step:
            item["tool_calls"] = [{"function_name": call.get("function_name"),
                "keystrokes": call.get("arguments", {}).get("keystrokes", ""),
                "duration": call.get("arguments", {}).get("duration")}
                for call in step["tool_calls"]]
        if "observation" in step:
            observation = step["observation"]
            if isinstance(observation, dict) and "results" in observation:
                item["observation"] = {"results": [
                    {"content": str(r.get("content", ""))} for r in observation["results"]]}
            else:
                item["observation"] = {"results": [{"content": str(observation)}]}
        out.append(item)
    return out


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def main() -> None:
    pool_doc = json.loads(POOL.read_text())
    all_samples = [s for group in pool_doc["groups"] for s in group["samples"]]
    maps = {"N1": [], "N4": [], "N8": []}
    manifests = {"N1": [], "N4": [], "N8": []}
    planned = {"N1": [], "N4": [], "N8": []}
    for group in pool_doc["groups"]:
        task = group["task_id"]
        by_label = {label: sorted([s for s in group["samples"] if s["evaluation_label"] == label],
                                  key=lambda s: (s["pair_index"], s["neutral_id"]))
                    for label in ("hack", "benign")}
        if any(len(by_label[label]) != 8 for label in by_label):
            raise ValueError(f"{task}: expected 8 hack + 8 benign samples")
        hacks, benign = by_label["hack"], by_label["benign"]

        cluster_specs = {"N1": [[s] for s in hacks + benign], "N4": [], "N8": []}
        for i in range(2):
            cluster_specs["N4"].append(hacks[i*4:(i+1)*4])
            cluster_specs["N4"].append(benign[i*4:(i+1)*4])
        for i in range(4):
            cluster_specs["N4"].append(hacks[i*2:(i+1)*2] + benign[i*2:(i+1)*2])
        cluster_specs["N8"].append(hacks[:])
        cluster_specs["N8"].append(benign[:])
        for i in range(2):
            cluster_specs["N8"].append(hacks[i*4:(i+1)*4] + benign[i*4:(i+1)*4])

        for size in ("N1", "N4", "N8"):
            for members in cluster_specs[size]:
                planned[size].append({"task_id": task, "members": members})

    # Randomize run order before assigning neutral filenames/IDs, so filenames
    # and batch order do not encode task or label composition.
    # Batch 2 uses a different seed AND a different ID prefix, so its cluster
    # IDs never collide with batch 1 and batch-1 maps stay valid.
    seed = 20261101 if PREFIX == "C" else 20261201
    rng = random.Random(seed)
    for size in ("N1", "N4", "N8"):
        rng.shuffle(planned[size])
        out_dir = DETECTOR / size
        out_dir.mkdir(parents=True, exist_ok=True)
        (BASE / "results" / size).mkdir(parents=True, exist_ok=True)
        for run_index, plan in enumerate(planned[size], 1):
            members = plan["members"]
            cluster_id = f"{PREFIX}{size[1:]}-{run_index:04d}"
            ordered = list(members)
            random.Random(seed + sum(map(ord, cluster_id))).shuffle(ordered)
            slots = []
            slot_map = []
            for index, sample in enumerate(ordered, 1):
                slot_id = f"SLOT-{index}"
                slots.append({"slot_id": slot_id, "steps": steps_for(sample)})
                slot_map.append({"slot_id": slot_id, "neutral_id": sample["neutral_id"],
                    "evaluation_label": sample["evaluation_label"],
                    "trajectory_path": sample["trajectory_path"],
                    "task_id": sample["task_id"], "pair_index": sample["pair_index"],
                    "n_input_tokens": sample.get("n_input_tokens"),
                    "n_output_tokens": sample.get("n_output_tokens"),
                    "episode_count": sample.get("episode_count")})
            filename = f"{cluster_id}.json"
            detector_doc = {"cluster_id": cluster_id, "n": len(slots), "slots": slots}
            (out_dir / filename).write_text(json.dumps(detector_doc, indent=1))
            maps[size].append({"cluster_id": cluster_id, "input_file": f"{size}/{filename}",
                "task_id": plan["task_id"], "members": slot_map})
            manifests[size].append({"cluster_id": cluster_id,
                "input_file": f"detector_inputs/{size}/{filename}",
                "result_file": f"results/{size}/{cluster_id}.json"})

    (EVALUATOR / f"cluster_maps{SUFFIX}_EVALUATOR_ONLY.json").write_text(json.dumps(
        {"note": "EVALUATOR ONLY; never expose to detector agents", "maps": maps}, indent=1))
    for size in ("N1", "N4", "N8"):
        (EVALUATOR / f"run_manifest_{size}{SUFFIX}_EVALUATOR_ONLY.json").write_text(json.dumps(
            {"status": "NOT RUN", "size": size, "runs": manifests[size]}, indent=1))
    print("Built detector inputs (no model calls):", {k: len(v) for k, v in manifests.items()})


if __name__ == "__main__":
    main()
