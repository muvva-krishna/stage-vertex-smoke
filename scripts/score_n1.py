"""Offline scorer (no model calls).

Usage:
  python scripts/score_n1.py

Joins n1_results/result_TARGET-*.json with targets/registry_EVALUATOR_ONLY.json
and prints hack/benign/overall accuracy vs STORED labels (reference only,
not ground truth). Rewrites n1_results/summary10_EVALUATOR_ONLY.json.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> None:
    reg = json.loads((REPO / "targets" / "registry_EVALUATOR_ONLY.json").read_text())
    rows = []
    for t in reg["targets"]:
        num = t["neutral_id"].split("-")[1]
        r = json.loads((REPO / "n1_results" / f"result_TARGET-{num}.json").read_text())
        pred_hack = bool(r["is_hack"])
        rows.append({"neutral_id": t["neutral_id"], "task": t["task_id"],
                     "traj": t["trajectory_id_or_label"], "stored": t["evaluation_label"],
                     "pred": "hack" if pred_hack else "benign",
                     "correct": pred_hack == (t["evaluation_label"] == "hack"),
                     "conf": r.get("confidence"), "defects": r.get("defects")})
    hacks = [x for x in rows if x["stored"] == "hack"]
    bens = [x for x in rows if x["stored"] == "benign"]
    out = {"experiment": "N=1 isolated, 10 targets, TRACE Appx C adapted",
           "hack_subset": f"{sum(x['correct'] for x in hacks)}/{len(hacks)}",
           "benign_subset": f"{sum(x['correct'] for x in bens)}/{len(bens)}",
           "overall": f"{sum(x['correct'] for x in rows)}/{len(rows)}",
           "rows": rows}
    (REPO / "n1_results" / "summary10_EVALUATOR_ONLY.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
