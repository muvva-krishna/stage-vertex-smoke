"""Stage-4 v2 detector runs on the user's own GCP project via ADC (NOT OpenCode).

Model: gemini-2.5-flash-lite on Vertex AI, project gen-lang-client-0430700811,
global endpoint. Auth: Application Default Credentials only (no API keys);
ADC file is never copied — the client reads it in place via oauth2 refresh.
Client logic is imported by path from ~/job-intelligence/scripts/gemini_client.py
(ADC minting, Vertex URL, retries); usage ledger is repointed to
stage4_context_grid/gemini_ledger/ so job-intelligence data is untouched.

Sandbox: each call sends ONLY one rendered v2 prompt.txt (neutral trajectory
IDs, no labels/maps/paths) with temperature 0.0 and receives only text back.
No evaluator files are read at run time; slot-ID restoration and scoring happen
parent-side afterwards, exactly like the OpenCode batches.

Usage: python3 scripts/run_gemini_v2.py [--sizes "N1 N4 N8"] [--prefix C|D|*]
       [--workers 20] [--model gemini-2.5-flash-lite] [--results results_gemini]
       [--tier tw-detect]
Results: stage4_context_grid/<results>/<size>/<cluster>.json
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "stage4_context_grid"
SNAP = BASE / "agent_snapshots_v2"
OUT = BASE / "results_gemini"
LEDGER = BASE / "gemini_ledger"

JOB_INTEL_SCRIPTS = Path(os.environ.get(
    "JOB_INTEL_SCRIPTS", str(Path.home() / "job-intelligence" / "scripts")))
sys.path.insert(0, str(JOB_INTEL_SCRIPTS))
import gemini_client as g  # noqa: E402  (ADC + Vertex only; no job-intel pipeline)

MODEL = "gemini-2.5-flash-lite"
PROJECT = "gen-lang-client-0430700811"
TIER = "tw-detect"

_gemini_cfg = {
    "project": PROJECT,
    "location": "global",
    "models": {},
    "fallback_models": [],
    "generation": {"temperature": 0.0, "max_output_tokens": 8192},
    "tier_generation": {},
    "quotas": {},
}


def run_one(size: str, cluster_id: str, model: str, out: Path, tier: str) -> str:
    out_path = out / size / f"{cluster_id}.json"
    if out_path.exists():
        try:
            doc = json.loads(out_path.read_text())
            if isinstance(doc.get("trajectories"), list) and len(doc["trajectories"]) == int(size[1:]):
                return f"skip {cluster_id}"
        except Exception:
            pass
    prompt = (SNAP / cluster_id / "prompt.txt").read_text()
    text, meta = g.generate_with_metadata(
        prompt, tier=tier, cfg=_gemini_cfg, model_override=model)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "cluster_id": cluster_id,
        "n": int(size[1:]),
        "detector_model": f"vertex/{model}",
        "project": PROJECT,
        "model_version": meta.get("model_version"),
        "finish_reason": meta.get("finish_reason"),
        "raw_text": text,
        "usage": meta.get("usage"),
    }, indent=1))
    return f"done {cluster_id} ({meta.get('usage', {}).get('total_tokens')} tok)"


def main() -> None:
    args = sys.argv[1:]
    sizes = args[args.index("--sizes") + 1].split() if "--sizes" in args else ["N1", "N4", "N8"]
    prefix = args[args.index("--prefix") + 1] if "--prefix" in args else "*"
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 20
    model = args[args.index("--model") + 1] if "--model" in args else MODEL
    tier = args[args.index("--tier") + 1] if "--tier" in args else TIER
    out = OUT if "--results" not in args else BASE / args[args.index("--results") + 1]
    LEDGER.mkdir(parents=True, exist_ok=True)
    g.TOKEN_LEDGER_FILE = LEDGER / "token_usage.json"
    g.TOKEN_EVENTS_JSONL = LEDGER / "token_events.jsonl"
    jobs = []
    for size in sizes:
        for run_dir in sorted(SNAP.iterdir()):
            cid = run_dir.name
            if not run_dir.is_dir() or not cid.startswith(tuple([prefix]) if prefix != "*" else ("C", "D")):
                continue
            if not cid.startswith({"N1": ("C1", "D1"), "N4": ("C4", "D4"), "N8": ("C8", "D8")}[size]):
                continue
            jobs.append((size, cid))
    print(f" launching {len(jobs)} calls on vertex/{model} (workers={workers})")
    done = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(run_one, s, c, model, out, tier): (s, c) for s, c in jobs}
        for fut in as_completed(futs):
            try:
                print(" ", fut.result(), flush=True)
                done += 1
            except Exception as exc:
                print(f"  FAILED {futs[fut]}: {str(exc)[:200]}", flush=True)
                failed += 1
    print(f"finished: {done} ok, {failed} failed")


if __name__ == "__main__":
    main()
