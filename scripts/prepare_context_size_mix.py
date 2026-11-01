"""Fetch/prepare a Stage-4 same-task context grid batch.

Usage: python3 scripts/prepare_context_size_mix.py [--spec SPEC] [--tag TAG]
Batch 1 (default spec, no tag): preserves Stage-1's five selected pairs and
adds three unique length-matched pairs per task. Batch 2 (--spec
pool_spec_batch2.json --tag batch2): fresh eight pairs per task.
Writes pool/pair files with the tag suffix so batch-1 files stay untouched.

It makes no model calls. Requires network access when executed.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = Path(sys.argv[sys.argv.index("--spec") + 1]) if "--spec" in sys.argv else (
    ROOT / "stage4_context_grid" / "pool_spec.json")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
SUFFIX = f"_{TAG}" if TAG else ""
RAW = "https://raw.githubusercontent.com/few-sh/terminal-wrench/main"
MODEL = "claude-opus-4.6"


def get_bytes(url: str) -> bytes:
    # urllib hangs for the full read timeout against this host in this
    # environment; curl returns in well under a second.
    result = subprocess.run(
        ["curl", "-sS", "--fail", "--max-time", "90", url],
        capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed ({result.returncode}) for {url}: "
                           f"{result.stderr.decode('utf-8', 'replace')[:200]}")
    return result.stdout


def get_json(url: str) -> dict:
    return json.loads(get_bytes(url).decode("utf-8"))


def token_total(row: dict) -> int:
    return int(row.get("n_input_tokens") or 0) + int(row.get("n_output_tokens") or 0)


def safe_component(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text))


def baseline_candidates(task_id: str, data: dict) -> list[dict]:
    rows = list(data.get("baselines") or [])
    if not rows and data.get("baseline"):
        rows = [data["baseline"]]
    out = []
    for row in rows:
        if row.get("classification") != "baseline" or float(row.get("reward") or 0) < 1:
            continue
        label = str(row.get("label", row.get("attempt_index", "")))
        if not label:
            continue
        out.append({**row, "evaluation_label": "benign", "trajectory_id_or_label": f"baseline:{label}",
                    "trajectory_path": f"tasks/{task_id}/{MODEL}/baseline_trajectories/{label}/trial/agent/trajectory.json"})
    return out


def hack_candidates(task_id: str, data: dict) -> list[dict]:
    out = []
    for row in data.get("trajectories", []):
        classification = row.get("classification", "")
        if row.get("tree_name") != "hack_trajectories":
            continue
        if classification not in {"rewarded_serious_exploit", "rewarded_nonserious_hack"}:
            continue
        if float(row.get("reward") or 0) < 1:
            continue
        label = str(row.get("trajectory_label", ""))
        if not label:
            continue
        out.append({**row, "evaluation_label": "hack", "trajectory_id_or_label": label,
                    "trajectory_path": f"tasks/{task_id}/{MODEL}/sanitized_trajectories/{label}/trial/agent/trajectory.json"})
    return out


def instruction_hash(trace: dict) -> str:
    users = [s.get("message", "") for s in trace.get("steps", []) if s.get("source") == "user"]
    text = users[0] if users else ""
    match = re.search(r"Task Description:\s*(.*?)(?:\n\s*Current terminal state:|\Z)", text, re.S)
    text = match.group(1) if match else text
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def stripped_steps(trace: dict) -> list[dict]:
    """Preserve full observed text; do not clip. Keep only conversational evidence."""
    result = []
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
                    {"content": str(row.get("content", ""))} for row in observation["results"]]}
            else:
                item["observation"] = {"results": [{"content": str(observation)}]}
        result.append(item)
    return result


def pair_cost(hack: dict, benign: dict) -> float:
    h, b = max(token_total(hack), 1), max(token_total(benign), 1)
    return abs(math.log(h / b)) + 0.04 * abs(int(hack.get("episode_count") or 0) - int(benign.get("episode_count") or 0))


def select_fresh_eight_pairs(hacks: list[dict], benign: list[dict]) -> list[tuple[dict, dict]]:
    """Eight distinct length-matched pairs for tasks with no Stage-1 selection."""
    pairs: list[tuple[dict, dict]] = []
    used_h, used_b = set(), set()
    scored = sorted(((pair_cost(h, b), h, b) for h in hacks for b in benign),
                    key=lambda x: x[0])
    for _, h, b in scored:
        if h["trajectory_path"] in used_h or b["trajectory_path"] in used_b:
            continue
        pairs.append((h, b))
        used_h.add(h["trajectory_path"])
        used_b.add(b["trajectory_path"])
        if len(pairs) == 8:
            break
    if len(pairs) != 8:
        raise ValueError("Could not find 8 additional distinct hack/benign pairs")
    return pairs


def select_eight_pairs(hacks: list[dict], benign: list[dict], selected: list[dict]) -> list[tuple[dict, dict]]:
    selected_h = {r["trajectory_path"] for r in selected if r["evaluation_label"] == "hack"}
    selected_b = {r["trajectory_path"] for r in selected if r["evaluation_label"] == "benign"}
    if len(selected_h) != 5 or len(selected_b) != 5:
        raise ValueError("Expected the five Stage-1 selected pairs per class; refusing silent replacement")
    used_h, used_b = set(selected_h), set(selected_b)
    extra: list[tuple[dict, dict]] = []
    hc = [r for r in hacks if r["trajectory_path"] not in used_h]
    bc = [r for r in benign if r["trajectory_path"] not in used_b]
    pairs = sorted(((pair_cost(h, b), h, b) for h in hc for b in bc), key=lambda x: x[0])
    for _, h, b in pairs:
        if h["trajectory_path"] in used_h or b["trajectory_path"] in used_b:
            continue
        extra.append((h, b))
        used_h.add(h["trajectory_path"])
        used_b.add(b["trajectory_path"])
        if len(extra) == 3:
            break
    if len(extra) != 3:
        raise ValueError("Could not find 3 additional distinct hack/benign pairs")
    # Keep original selected records in Stage-1 order; append added matched pairs.
    ordered_h = [r for r in selected if r["evaluation_label"] == "hack"]
    ordered_b = [r for r in selected if r["evaluation_label"] == "benign"]
    return list(zip(ordered_h, ordered_b)) + extra


def main() -> None:
    spec = json.loads(SPEC.read_text())
    stage1 = json.loads((ROOT / "selected_terminal_wrench_groups.json").read_text())
    legacy = json.loads((ROOT / "targets" / "registry_EVALUATOR_ONLY.json").read_text())
    legacy_ids = {(row["task_id"], row["trajectory_id_or_label"]): row["neutral_id"]
                  for row in legacy["targets"]}
    selected_by_task = {g["task_id"]: g for g in stage1["groups"]}
    pool_dir = ROOT / "stage4_context_grid" / "source_trajectories"
    detector_dir = ROOT / "stage4_context_grid" / "detector_inputs"
    evaluator_dir = ROOT / "stage4_context_grid" / "evaluator_only"
    for path in (pool_dir, detector_dir, evaluator_dir):
        path.mkdir(parents=True, exist_ok=True)

    groups_out = []
    samples = []
    preserve = bool(spec.get("preserve_existing_stage1_selection"))
    for task_id in spec["groups"]:
        task_url = f"{RAW}/tasks/{task_id}/{MODEL}/task.json"
        data = get_json(task_url)
        hacks, benign = hack_candidates(task_id, data), baseline_candidates(task_id, data)
        if preserve:
            if task_id not in selected_by_task:
                raise ValueError(f"No Stage-1 verified group for {task_id}")
            pairs = select_eight_pairs(
                hacks, benign, selected_by_task[task_id]["selected_trajectories"])
        else:
            pairs = select_fresh_eight_pairs(hacks, benign)
        task_samples = {"hack": [], "benign": []}
        pair_reports = []
        hashes = set()
        for pair_index, (h, b) in enumerate(pairs, 1):
            for row, label in ((h, "hack"), (b, "benign")):
                # Hash-derived neutral IDs avoid sequential/parity cues from the
                # hack/benign pairing order. Mapping stays evaluator-side only.
                neutral_id = "S4-" + hashlib.sha256(
                    ("terminal-wrench-stage4-neutral-v1:" + row["trajectory_path"]).encode("utf-8")
                ).hexdigest()[:12]
                relative_source = safe_component(neutral_id) + ".json"
                payload = get_bytes(f"{RAW}/{row['trajectory_path']}")
                trace = json.loads(payload.decode("utf-8"))
                ih = instruction_hash(trace)
                hashes.add(ih)
                source_file = pool_dir / relative_source
                source_file.write_bytes(payload)
                sample = {"neutral_id": neutral_id, "task_id": task_id, "model": MODEL,
                    "evaluation_label": label, "trajectory_id_or_label": row["trajectory_id_or_label"],
                    "trajectory_path": row["trajectory_path"], "source_file": str(source_file.relative_to(ROOT)),
                    "legacy_n1_id": legacy_ids.get((task_id, row["trajectory_id_or_label"])),
                    "episode_count": row.get("episode_count"), "n_input_tokens": row.get("n_input_tokens"),
                    "n_output_tokens": row.get("n_output_tokens"), "instruction_sha256": ih,
                    "source_label": row.get("classification", "baseline"), "pair_index": pair_index}
                samples.append(sample)
                task_samples[label].append({**sample, "steps": stripped_steps(trace)})
            pair_reports.append({"pair_index": pair_index,
                "hack": h["trajectory_id_or_label"], "benign": b["trajectory_id_or_label"],
                "source_token_ratio": round(max(token_total(h), token_total(b)) / max(min(token_total(h), token_total(b)), 1), 3)})
        if len(hashes) != 1:
            raise ValueError(f"Task instructions differ for {task_id}: {len(hashes)} distinct normalized hashes")
        groups_out.append({"task_id": task_id, "instruction_sha256": next(iter(hashes)),
            "hack_count": len(task_samples["hack"]), "benign_count": len(task_samples["benign"]),
            "pair_reports": pair_reports, "hack": task_samples["hack"], "benign": task_samples["benign"]})

    # Save evaluator pool; detector input generation is deliberately a separate script step.
    (evaluator_dir / f"pool{SUFFIX}_EVALUATOR_ONLY.json").write_text(json.dumps(
        {"note": "EVALUATOR ONLY", "groups": [{k:v for k,v in g.items() if k not in {"hack", "benign"}}
            | {"samples": [{k:v for k,v in s.items() if k != "steps"} for s in g["hack"] + g["benign"]]}
            for g in groups_out]}, indent=2))
    # Keep a machine-readable normalized pool with all trace content for the builder.
    (pool_dir / f"normalized_pool{SUFFIX}_EVALUATOR_ONLY.json").write_text(json.dumps(
        [{k:v for k,v in s.items() if k != "steps"} for g in groups_out for label in ("hack", "benign") for s in g[label]], indent=2))
    (evaluator_dir / f"pair_selection{SUFFIX}_EVALUATOR_ONLY.json").write_text(json.dumps(
        [{k:v for k,v in g.items() if k not in {"hack", "benign"}} for g in groups_out], indent=2))
    print("Expanded pool fetched. No detector/model calls were made.")
    expected = 16 * len(spec["groups"])
    print(f"groups={len(groups_out)} samples={len(samples)} (expected {expected})")
    if len(samples) != expected:
        raise ValueError(f"Sample count {len(samples)} != expected {expected}")


if __name__ == "__main__":
    main()
