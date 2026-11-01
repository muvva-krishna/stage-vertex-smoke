"""Offline leakage + validity check (no model calls).

Usage:
  python scripts/check_leakage.py

Checks:
 1. No label/path strings in n1_stripped/*.json.
 2. All 10 result files exist and parse with required keys.
 3. Registry counts: 5 hack + 5 benign, 10 unique files.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEAK = re.compile(
    r"is_hack|evaluation_label|sanitized_trajectories|baseline_trajectories"
    r"|classification_explanation|red team hack instruction", re.I)
REQUIRED = {"neutral_target_id", "trajectory_index", "is_hack",
            "hack_description", "confidence", "reasoning", "defects"}


def main() -> int:
    fails = []
    for p in sorted((REPO / "n1_stripped").glob("*.json")):
        hits = LEAK.findall(p.read_text())
        if hits:
            fails.append(f"{p.name}: leakage hits {hits}")
    reg = json.loads((REPO / "targets" / "registry_EVALUATOR_ONLY.json").read_text())
    tg = reg["targets"]
    labs = [t["evaluation_label"] for t in tg]
    if len(tg) != 10 or labs.count("hack") != 5 or labs.count("benign") != 5:
        fails.append(f"registry counts wrong: {len(tg)} total, {labs}")
    if len({t["file"] for t in tg}) != 10:
        fails.append("registry files not unique")
    for t in tg:
        num = t["neutral_id"].split("-")[1]
        rp = REPO / "n1_results" / f"result_TARGET-{num}.json"
        if not rp.exists():
            fails.append(f"missing {rp.name}")
            continue
        r = json.loads(rp.read_text())
        if not REQUIRED.issubset(r):
            fails.append(f"{rp.name}: missing keys {REQUIRED - set(r)}")
    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS: 10 stripped inputs clean, 10 results valid, registry 5 hack + 5 benign.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
