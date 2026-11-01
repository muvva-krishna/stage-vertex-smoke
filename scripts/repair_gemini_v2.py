"""Repair/recover malformed Gemini v2 outputs. Same model, same project, no prompt changes.

Two classes:
- TRUNCATED (finish=MAX_TOKENS): rerun identical prompt with larger output budget
  (8192 -> 16384). Output budget is not a scoring variable; the prompt is byte-identical.
- MALFORMED-STOP: ask the same model to fix ONLY the JSON syntax of its own
  output (temp 0.0, "return only the repaired JSON"). Verdict content untouched;
  repaired outputs must contain exactly N trajectories with known IDs or they
  are queued for fresh rerun instead.

Usage: python3 scripts/repair_gemini_v2.py [--workers 20]
Writes back into stage4_context_grid/results_gemini/<size>/<cluster>.json
(keeps original raw_text as raw_text_v1_attempt).
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "stage4_context_grid"
G = BASE / "results_gemini"
SNAP = BASE / "agent_snapshots_v2"

JOB_INTEL_SCRIPTS = Path(os.environ.get(
    "JOB_INTEL_SCRIPTS", str(Path.home() / "job-intelligence" / "scripts")))
sys.path.insert(0, str(JOB_INTEL_SCRIPTS))
import gemini_client as g  # noqa: E402

from run_gemini_v2 import _gemini_cfg, MODEL, TIER, LEDGER  # noqa: E402

g.TOKEN_LEDGER_FILE = LEDGER / "token_usage.json"
g.TOKEN_EVENTS_JSONL = LEDGER / "token_events.jsonl"

REPAIR_CFG = dict(_gemini_cfg)
REPAIR_CFG["generation"] = {"temperature": 0.0, "max_output_tokens": 16384}
BIG_CFG = dict(_gemini_cfg)
BIG_CFG["generation"] = {"temperature": 0.0, "max_output_tokens": 16384}


def parse(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(text[text.find("{"):text.rfind("}") + 1])


def maps():
    out = {}
    for tag, suf in (("", ""), ("batch2", "_batch2")):
        man = json.loads((BASE / f"evaluator_only/rendered_prompt_manifest_v2{suf}_EVALUATOR_ONLY.json").read_text())
        for run, rm in zip(man["runs"], man["trajectory_id_maps"]):
            out[run["cluster_id"]] = {m["trajectory_id"]: m["slot_id"] for m in rm["trajectory_map"]}
    return out


def validate(doc, cluster_id, size):
    mp = maps()[cluster_id]
    d = parse(doc["raw_text"])
    assert isinstance(d.get("trajectories"), list) and len(d["trajectories"]) == int(size[1:])
    slots = []
    for t in d["trajectories"]:
        assert t["trajectory_id"] in mp, f"unknown id {t['trajectory_id']}"
        slots.append({"slot_id": mp[t["trajectory_id"]], "is_hack": bool(t["is_hack"]),
                      "hack_description": t.get("hack_description", ""),
                      "confidence": t.get("confidence"),
                      "reasoning": t.get("evidence", t.get("reasoning", ""))})
    return slots


def needs_help():
    todo = []
    for size in ("N1", "N4", "N8"):
        for f in sorted((G / size).glob("*.json")):
            doc = json.loads(f.read_text())
            if "slots" in doc:
                continue
            kind = "rerun-big" if doc.get("finish_reason") == "MAX_TOKENS" else "repair"
            todo.append((kind, size, f.stem))
    return todo


def fix_one(kind, size, cid):
    f = G / size / f"{cid}.json"
    doc = json.loads(f.read_text())
    if kind == "repair":
        prompt = ("Fix ONLY the JSON syntax of the following model output so it parses "
                  "with strict json.loads(). Do not change any verdict, text, or value. "
                  "Return ONLY the repaired JSON, no fences, no commentary:\n\n" + doc["raw_text"][:60000])
        text, meta = g.generate_with_metadata(prompt, tier=TIER, cfg=REPAIR_CFG, model_override=MODEL)
        doc["raw_text_v1_attempt"] = doc.pop("raw_text")
        doc["raw_text"] = text
        doc["finish_reason"] = meta.get("finishReason")
        doc["repair"] = True
    else:
        prompt = (SNAP / cid / "prompt.txt").read_text()
        text, meta = g.generate_with_metadata(prompt, tier=TIER, cfg=BIG_CFG, model_override=MODEL)
        doc["raw_text_v1_attempt"] = doc.pop("raw_text")
        doc["raw_text"] = text
        doc["finish_reason"] = meta.get("finishReason")
        doc["rerun_big_budget"] = True
    doc["usage"] = meta.get("usage")
    try:
        slots = validate(doc, cid, size)
    except Exception as exc:
        f.write_text(json.dumps(doc, indent=1))
        return f"{kind} {cid}: STILL BAD ({str(exc)[:100]})"
    doc["slots"] = slots
    doc["prompt_version"] = "v2-gemini"
    f.write_text(json.dumps(doc, indent=1))
    return f"{kind} {cid}: recovered"


def main():
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 20
    LEDGER.mkdir(parents=True, exist_ok=True)
    todo = needs_help()
    print(f"repair queue: {len(todo)}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fix_one, k, s, c): (k, s, c) for k, s, c in todo}
        for fut in as_completed(futs):
            try:
                print(" ", fut.result(), flush=True)
            except Exception as exc:
                print(f"  FAILED {futs[fut]}: {str(exc)[:200]}", flush=True)


if __name__ == "__main__":
    main()
