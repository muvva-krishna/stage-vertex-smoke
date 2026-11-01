"""Render one self-contained, label-free prompt per Stage-4 cluster.

Usage: python3 scripts/render_context_prompts.py [--spec SPEC] [--tag TAG]
Only renders clusters whose ID starts with the spec's prefix, so batch-2
rendering never touches batch-1 snapshots. NOT RUN: no model calls.
Reads only stage4_context_grid/detector_inputs/{N1,N4,N8}/*.json,
embeds the full cluster JSON in one prompt.txt, and places only that prompt in
the per-run snapshot. It never reads evaluator-only maps or source metadata.
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "stage4_context_grid"
INPUTS = BASE / "detector_inputs"
SNAPSHOTS = BASE / "agent_snapshots_v2"
EVALUATOR = BASE / "evaluator_only"
PROMPT_PATH = ROOT / "prompts" / "stage4_context_grid.md"
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
SUFFIX = "_v2" + (f"_{TAG}" if TAG else "")
SPEC = Path(sys.argv[sys.argv.index("--spec") + 1]) if "--spec" in sys.argv else (
    BASE / "pool_spec.json")
PREFIX = json.loads(SPEC.read_text()).get("cluster_id_prefix", "C")
MODEL = "opencode-go/muse-spark-1.3-contributor#high"


def prompt_template() -> str:
    text = PROMPT_PATH.read_text()
    start = text.find("```text\n")
    end = text.find("\n```", start + 8)
    if start < 0 or end < 0:
        raise ValueError("Could not find the prompt text block")
    return text[start + len("```text\n"):end]


def model_payload(cluster: dict) -> tuple[dict, list[dict]]:
    """Return only trajectories + a parent-only ID map; drop run metadata."""
    trajectories = []
    trajectory_map = []
    for slot in cluster["slots"]:
        trajectory_id = "T-" + secrets.token_hex(6)
        trajectories.append({"trajectory_id": trajectory_id,
                             "steps": slot["steps"]})
        trajectory_map.append({"trajectory_id": trajectory_id,
                               "slot_id": slot["slot_id"]})
    return {"trajectories": trajectories}, trajectory_map


def main() -> None:
    template = prompt_template()
    runs = []
    id_maps = []
    for size in ("N1", "N4", "N8"):
        for source in sorted((INPUTS / size).glob("*.json")):
            cluster = json.loads(source.read_text())
            if not cluster.get("cluster_id", "").startswith(PREFIX):
                continue
            if len(cluster.get("slots", [])) != int(size[1:]):
                raise ValueError(f"{source}: N does not match its directory")
            # Project to the strict model-visible allowlist. Omit cluster_id,
            # N, task, batch, label maps, and predictable SLOT-1..N IDs.
            payload, trajectory_map = model_payload(cluster)
            cluster_text = json.dumps(payload,
                                      ensure_ascii=False, separators=(",", ":"))
            rendered = template.replace("{{CLUSTER_JSON}}", cluster_text)
            if "{{CLUSTER_JSON}}" in rendered:
                raise ValueError(f"{source}: cluster placeholder was not substituted")
            run_dir = SNAPSHOTS / cluster["cluster_id"]
            run_dir.mkdir(parents=True, exist_ok=False)
            (run_dir / "prompt.txt").write_text(rendered)
            runs.append({"cluster_id": cluster["cluster_id"], "n": len(cluster["slots"]),
                         "prompt_file": f"agent_snapshots_v2/{cluster['cluster_id']}/prompt.txt",
                         "agent": "trace-detector", "model": MODEL,
                         "submission": "copy prompt to opaque temp filename in clean sandbox; --file attach with fixed wrapper; one fresh call",
                         "tools": "deny all"})
            id_maps.append({"cluster_id": cluster["cluster_id"],
                            "trajectory_map": trajectory_map})
    (EVALUATOR / f"rendered_prompt_manifest{SUFFIX}_EVALUATOR_ONLY.json").write_text(json.dumps(
        {"note": "Evaluator-side launch ledger; do not include in agent snapshots.",
         "status": "PROMPTS RENDERED, NOT RUN", "model": MODEL,
         "runs": runs, "trajectory_id_maps": id_maps}, indent=1))
    print(f"Rendered {len(runs)} single-message prompts; no model calls made.")


if __name__ == "__main__":
    main()
