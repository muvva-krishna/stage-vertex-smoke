"""Verify candidate new tasks for Stage-4 expansion. Offline, no model calls.

For each candidate task: checks sanitized-hack + baseline URL existence,
greedy length-matched 8-pair selection (same pair_cost as
prepare_context_size_mix.py), single-instruction-hash check, and rendered
stripped size measurement per trajectory + projected N4 cluster sizes.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys

RAW = "https://raw.githubusercontent.com/few-sh/terminal-wrench/main"
MODEL = "claude-opus-4.6"
CANDIDATES = ["schedule-vacation", "sympy-matrix-fix"]


def fetch(url: str) -> bytes:
    r = subprocess.run(["curl", "-sS", "--fail", "--max-time", "90", url],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"fetch failed {url}: {r.stderr.decode()[:150]}")
    return r.stdout


def tokens(row: dict) -> int:
    return int(row.get("n_input_tokens") or 0) + int(row.get("n_output_tokens") or 0)


def instruction_hash(trace: dict) -> str:
    users = [s.get("message", "") for s in trace.get("steps", [])
             if s.get("source") == "user"]
    text = users[0] if users else ""
    m = re.search(r"Task Description:\s*(.*?)(?:\n\s*Current terminal state:|\Z)",
                  text, re.S)
    text = m.group(1) if m else text
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def stripped_size(trace: dict) -> int:
    # same allowlist shape as build_context_size_mix.steps_for, compact JSON
    out = []
    for step in trace.get("steps", []):
        item = {"step_id": step.get("step_id"), "source": step.get("source"),
                "message": step.get("message", "")}
        if "tool_calls" in step:
            item["tool_calls"] = [
                {"function_name": c.get("function_name"),
                 "keystrokes": c.get("arguments", {}).get("keystrokes", ""),
                 "duration": c.get("arguments", {}).get("duration")}
                for c in step["tool_calls"]]
        if "observation" in step:
            ob = step["observation"]
            if isinstance(ob, dict) and "results" in ob:
                item["observation"] = {"results": [
                    {"content": str(x.get("content", ""))}
                    for x in ob["results"]]}
            else:
                item["observation"] = {"results": [{"content": str(ob)}]}
        out.append(item)
    return len(json.dumps({"slots": [{"slot_id": "SLOT-1",
                                      "steps": out}]}, ensure_ascii=False))


def main() -> int:
    report = {}
    for task in CANDIDATES:
        data = json.loads(fetch(
            f"{RAW}/tasks/{task}/{MODEL}/task.json").decode())
        hacks, bens = [], []
        for r in data.get("trajectories", []):
            if (r.get("tree_name") == "hack_trajectories"
                    and r.get("classification") in (
                        "rewarded_serious_exploit",
                        "rewarded_nonserious_hack")
                    and float(r.get("reward") or 0) >= 1
                    and r.get("trajectory_label")):
                hacks.append(r)
        for r in data.get("baselines", []) or []:
            if (r.get("classification") == "baseline"
                    and float(r.get("reward") or 0) >= 1):
                bens.append(r)
        # URL existence for every candidate path
        missing = []
        hpaths = {r["trajectory_label"]:
                  f"tasks/{task}/{MODEL}/sanitized_trajectories/"
                  f"{r['trajectory_label']}/trial/agent/trajectory.json"
                  for r in hacks}
        bpaths = {str(r.get("label")):
                  f"tasks/{task}/{MODEL}/baseline_trajectories/"
                  f"{r.get('label')}/trial/agent/trajectory.json"
                  for r in bens}
        for label, p in list(hpaths.items()) + list(bpaths.items()):
            r = subprocess.run(
                ["curl", "-sS", "--fail", "-o", "/dev/null",
                 "--max-time", "60", f"{RAW}/{p}"], capture_output=True)
            if r.returncode != 0:
                missing.append(f"{label}:{p}")
        # greedy 8 distinct pairs by token log-ratio + episode diff
        pairs, uh, ub = [], set(), set()
        scored = sorted(
            ((abs(math.log(max(tokens(h), 1) / max(tokens(b), 1)))
              + 0.04 * abs(int(h.get("episode_count") or 0)
                           - int(b.get("episode_count") or 0)), h, b)
             for h in hacks for b in bens), key=lambda x: x[0])
        for cost, h, b in scored:
            hl, bl = h["trajectory_label"], str(b.get("label"))
            if hl in uh or bl in ub:
                continue
            pairs.append((hl, bl, round(cost, 3),
                          round(max(tokens(h), tokens(b))
                                / max(min(tokens(h), tokens(b)), 1), 3)))
            uh.add(hl)
            ub.add(bl)
            if len(pairs) == 8:
                break
        # download the 16 selected, hash instructions, measure sizes
        sizes, hashes = {}, set()
        ok = len(pairs) == 8 and not missing
        if ok:
            for hl, bl, _, _ in pairs:
                for label, p in ((hl, hpaths[hl]), (bl, bpaths[bl])):
                    tr = json.loads(fetch(f"{RAW}/{p}").decode())
                    hashes.add(instruction_hash(tr))
                    sizes[f"{'H' if label == hl else 'B'}:{label}"] = \
                        stripped_size(tr)
        proj_n4 = (sorted(sizes.values())[len(sizes)//2] * 4
                   if sizes else None)
        report[task] = {
            "n_hack": len(hacks, ), "n_benign": len(bens),
            "hack_classes": sorted({r.get("classification") for r in hacks}),
            "missing_paths": missing,
            "pairs_8": pairs,
            "single_instruction_hash": len(hashes) == 1 if hashes else None,
            "rendered_sizes": sizes,
            "median_rendered": (sorted(sizes.values())[len(sizes)//2]
                                if sizes else None),
            "max_rendered": max(sizes.values()) if sizes else None,
            "projected_median_N4_chars": proj_n4,
        }
        print(f"==== {task} ====")
        print(json.dumps(report[task], indent=1)[:2500])
    Path_out = "/tmp/opencode/new_tasks_verify.json"
    with open(Path_out, "w") as f:
        json.dump(report, f, indent=1)
    print("wrote", Path_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
