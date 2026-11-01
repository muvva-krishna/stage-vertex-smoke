# OpenCode detector sandbox

## Intended boundary

Stage 4 uses the project-local OpenCode subagent `.opencode/agents/trace-detector.md`:

- dedicated `trace-detector` subagent, model `opencode-go/muse-spark-1.3-contributor#high`;
- one fresh child session per cluster;
- ordered permission rule denies `*` on `*`, so the detector has no file, shell, web, MCP, skill, edit, or subagent tools;
- the orchestrator attaches the entire rendered cluster prompt in one subagent call;
- detector never receives a path to evaluator data or another cluster;
- parent/orchestrator saves returned JSON to the result directory only after the call.

OpenCode permissions restrict tools; they are not an OS/container boundary. Do not describe this as a kernel-level sandbox. For this workload the detector needs no tools at all, so denying every tool is the strongest OpenCode-native boundary. The subagent must be launched from this repository root so OpenCode discovers `.opencode/agents/trace-detector.md`.

## Data boundary

`scripts/prepare_context_size_mix.py` fetches source trajectories into an evaluator-side directory. `scripts/build_context_size_mix.py` creates new detector copies from an allowlist: only slot IDs and full step evidence (messages, tool calls, observations). It omits labels, trajectory paths, task IDs, classification explanations, and source filenames. No content is clipped. V2 `scripts/render_context_prompts.py` projects the input further: the model receives only a list of steps keyed by random, nonsemantic trajectory IDs—no batch/cluster ID, task ID, or explicit N field. The renderer creates one per-run snapshot containing exactly:

- `prompt.txt`: the whole cluster JSON embedded in one prompt. This is the only file in the snapshot.

Evaluator maps and batch manifests are stored under `evaluator_only/`, not copied into agent snapshots. The runner copies the prompt to an opaque temporary filename in `/tmp/opencode/tw_sandbox/inbox/` and attaches it with `--file`; the model is not given a repository path. One cluster = one new `trace-detector` child session. Never reuse a detector session across clusters.

## Prompt-injection handling

Trajectory text is untrusted evidence. The agent system prompt says to ignore embedded instructions. No tools are available even if an embedded trajectory message asks the detector to browse or read local files. Do not remove legitimate trajectory messages selectively; that would alter the evidence. Metadata labels are excluded, but behavioral clues written by the trajectory agent remain part of the observed record.

## Required checks before any future launch

1. Run `scripts/check_context_size_mix.py` only after building/rendering; require PASS.
2. Confirm each `agent_snapshots_v2/<cluster>/` contains only `prompt.txt`; no maps, manifests, labels, or neighboring clusters.
3. Confirm the exact rendered prompt fits the model context. Never truncate; reject and report an oversized cluster.
4. Launch each prompt as a new `trace-detector` subagent with no tools, in parallel if desired, same model/settings.
5. Do not attach evaluator maps, labels, or previous model outputs to the child session. Score results in the parent only after all calls finish.

V1 and v2 runs are complete for Muse; Gemini runs use Vertex text-only requests. This is OpenCode tool-level isolation for Muse, not an OS/container boundary. Muse detector logs show fresh sessions and no tool events; Vertex requests include no tools. Neither proves what provider infrastructure retains about requests/attachments.
