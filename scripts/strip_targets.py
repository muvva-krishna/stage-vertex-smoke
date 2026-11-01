"""Rebuild label-free N=1 detector inputs (offline, no model calls).

Usage:
  python scripts/strip_targets.py

Reads selected_terminal_wrench_groups.json and the downloaded transcript JSONs
from /tmp/opencode/tw_review/all/<task>__<traj>.json, writes
n1_stripped/target_01..10.json with {neutral_target_id, source_task, steps[]}.

Labels stay OUT of stripped files; they live in *_EVALUATOR_ONLY files.
Mapping (neutral_id -> task/traj/label) is defined in TARGET_SPECS below,
matching targets/registry_EVALUATOR_ONLY.json.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = Path("/tmp/opencode/tw_review/all")
OUT_DIR = REPO / "n1_stripped"

TARGET_SPECS = [
    ("TARGET-01", "buffer-overflow-exploit", "v5_13"),
    ("TARGET-02", "iot-device-registration-server", "v5_14"),
    ("TARGET-03", "iris-data-loading-script", "v5_2"),
    ("TARGET-04", "titanic-female-survival-prediction", "v5"),
    ("TARGET-05", "amuse-install", "v5"),
    ("TARGET-06", "buffer-overflow-exploit", "baseline:2"),
    ("TARGET-07", "iot-device-registration-server", "baseline:7"),
    ("TARGET-08", "iris-data-loading-script", "baseline:2"),
    ("TARGET-09", "titanic-female-survival-prediction", "baseline:2"),
    ("TARGET-10", "amuse-install", "baseline:11"),
]

OBS_CHAR_CAP = 12000


def strip_transcript(src: Path) -> list:
    d = json.loads(src.read_text())
    out = []
    for s in d.get("steps", []):
        ns = {"step_id": s.get("step_id"), "source": s.get("source"),
              "message": s.get("message", "")}
        if "tool_calls" in s:
            ns["tool_calls"] = [
                {"function_name": c.get("function_name"),
                 "keystrokes": c.get("arguments", {}).get("keystrokes", ""),
                 "duration": c.get("arguments", {}).get("duration")}
                for c in s["tool_calls"]]
        if "observation" in s:
            obs = s["observation"]
            if isinstance(obs, dict) and "results" in obs:
                ns["observation"] = {"results": [
                    {"content": str(r.get("content", ""))[:OBS_CHAR_CAP]}
                    for r in obs["results"]]}
            else:
                ns["observation"] = {"results": [{"content": str(obs)[:OBS_CHAR_CAP]}]}
        out.append(ns)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for nid, task, traj in TARGET_SPECS:
        src = SRC_DIR / f"{task}__{traj.replace(':', '_')}.json"
        steps = strip_transcript(src)
        num = nid.split("-")[1]
        dest = OUT_DIR / f"target_{num}.json"
        dest.write_text(json.dumps(
            {"neutral_target_id": nid, "source_task": task, "steps": steps}, indent=1))
        print(f"wrote {dest} ({len(steps)} steps)")


if __name__ == "__main__":
    main()
