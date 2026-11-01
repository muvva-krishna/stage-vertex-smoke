# Peer context and reward-hack detection

**A TRACE-inspired extension using long Terminal Wrench trajectories.** This study asks whether a detector labels trajectories more accurately when it sees peer trajectories in the same joint call, and whether peer-label mix and cluster size matter.

> **Main result:** mixed same-task clusters helped Muse Spark 1.3 and Gemini 3.5 Flash-Lite at N=4; the effect did not generalize uniformly to Gemini 2.5 Flash-Lite. Pure same-label clusters were not reliably helpful. N8 results were model/task dependent. This is evidence about **same-task context and class mixture**, not proof that semantic similarity itself is the cause.

## Relationship to TRACE

TRACE formulates reward-hack detection as contrastive/outlier analysis and studies cluster size and benign-to-hack ratio. This project extends that line of work to long, multi-step Terminal Wrench trajectories and compares N=1 classification against joint N=4/N=8 per-trajectory judgments in homogeneous and mixed-label contexts.

The prompt lineage is TRACE Appendix C, adapted for neutral trajectory IDs and structured outputs. The first Stage-4 prompt (v1) retained TRACE's outlier framing; after auditing its mismatch with per-item classification, v2 removed outlier language and made relative comparison optional. Both prompt revisions and their results are retained for reproducibility.

**Scope limit:** all Stage-4 clusters use peers from the same task. There is no matched other-task control. Results can support claims about *same-task context / label composition*, but cannot isolate or establish a causal benefit of *similarity* over dissimilar peers.

## Sources

- Deshpande, Kannappan & Qian, [*Benchmarking Reward Hack Detection in Code Environments via Contrastive Analysis*](https://arxiv.org/abs/2601.20103), especially §§4.1–4.4, RQ3, and Appendix C. TRACE's paper is CC BY 4.0.
- [TRACE dataset/project](https://huggingface.co/datasets/PatronusAI/trace-dataset).
- [Terminal Wrench dataset repository](https://github.com/few-sh/terminal-wrench) and [paper](https://arxiv.org/abs/2604.17596). Its repository lists Apache License 2.0; consult that license for dataset material reproduced here.

## Study design

- **Source task/model:** Terminal Wrench, `claude-opus-4.6` trajectories.
- **Cohort:** five tasks: `iot-device-registration-server`, `iris-data-loading-script`, `titanic-female-survival-prediction`, `schedule-vacation`, `sympy-matrix-fix`.
- **Labels:** 8 stored hack trajectories + 8 successful baselines per task = **80 trajectories** (40/40). These are Terminal Wrench reference labels, **not independent human ground truth**.
- **N=1:** every trajectory judged alone (80 calls/model).
- **N=4:** per task: two all-hack groups, two all-benign groups, four 2H/2B mixed groups (40 calls/model).
- **N=8:** per task: one all-hack group, one all-benign group, two 4H/4B mixed groups (20 calls/model).
- **Total:** 140 calls/model. Each trajectory is evaluated at N=1 and in homogeneous and mixed contexts at N=4 and N=8.
- **Inference unit:** five task groups. This is an exploratory pilot, not a powered population-level study; no multi-seed replication or inferential confidence intervals were run.

### Models and execution

| Detector | Backend / project | Decoding and completion |
|---|---|---|
| Muse Spark 1.3 Contributor, high | OpenCode Go | 140 v2 calls. OpenCode did not expose a temperature setting, so backend temperature is unknown. 139 complete clusters + one with 7/8 verdicts (one abstention after repeated omission). |
| Gemini 2.5 Flash-Lite | Vertex AI ADC, project `gen-lang-client-0430700811`, global endpoint | Main calls at temperature 0.0. Recovery calls used 0.4 and 0.7 with larger output budgets; marked per result. Final: 130 complete, 5 partial, 5 N1 input-echo failures; 389/400 trajectory-condition verdicts scored. |
| Gemini 3.5 Flash-Lite | Vertex AI ADC, same project/endpoint | Temperature 0.0. 139 first-pass outputs + one syntax-only repair; 140/140 clusters complete. |

Vertex calls use the user's local gcloud ADC; credentials are not included. Usage ledgers are under `stage4_context_grid/gemini_ledger/`.

## Results — v2 neutral classification prompt

Scores use stored Terminal Wrench labels. `n` is the number of scored trajectory predictions. A partial cluster contributes only returned verdicts; missing outputs are abstentions, never imputed.

| Model | Condition | n | Accuracy | Precision | Hack recall | Benign specificity |
|---|---|---:|---:|---:|---:|---:|
| **Muse Spark 1.3** | N1 solo | 80 | .750 | .833 | .625 (25/40) | .875 (35/40) |
| | N4 homogeneous | 80 | .800 | .929 | .650 (26/40) | .950 (38/40) |
| | N4 mixed, 2H/2B | 80 | **.850** | 1.000 | .700 (28/40) | 1.000 (40/40) |
| | N8 homogeneous | 80 | .650 | .750 | .450 (18/40) | .850 (34/40) |
| | N8 mixed, 4H/4B | 79 + 1 abstention | .810 | .853 | .744 (29/39) | .875 (35/40) |
| **Gemini 2.5 Flash-Lite** | N1 solo | 75 | .747 | 1.000 | .500 (19/38) | 1.000 (37/37) |
| | N4 homogeneous | 80 | .738 | 1.000 | .475 (19/40) | 1.000 (40/40) |
| | N4 mixed, 2H/2B | 80 | .750 | .917 | .550 (22/40) | .950 (38/40) |
| | N8 homogeneous | 75 | .707 | 1.000 | .389 (14/36) | 1.000 (39/39) |
| | N8 mixed, 4H/4B | 79 | .633 | .727 | .410 (16/39) | .850 (34/40) |
| **Gemini 3.5 Flash-Lite** | N1 solo | 80 | .713 | .870 | .500 (20/40) | .925 (37/40) |
| | N4 homogeneous | 80 | .750 | 1.000 | .500 (20/40) | 1.000 (40/40) |
| | N4 mixed, 2H/2B | 80 | .813 | .963 | .650 (26/40) | .975 (39/40) |
| | N8 homogeneous | 80 | .725 | 1.000 | .450 (18/40) | 1.000 (40/40) |
| | N8 mixed, 4H/4B | 80 | **.975** | .952 | **1.000 (40/40)** | .950 (38/40) |

### Hack recall by task in mixed clusters

| Task | Muse N4 → N8 | Gemini 2.5 N4 → N8 | Gemini 3.5 N4 → N8 |
|---|---:|---:|---:|
| IoT device registration | 8/8 → 8/8 | 1/8 → 0/8 | 4/8 → 8/8 |
| Iris data loading | 4/8 → 6/8 | 6/8 → 3/8 | 4/8 → 8/8 |
| Schedule vacation | 0/8 → 0/8 | 2/8 → 2/8 | 2/8 → 8/8 |
| SymPy matrix fix | 8/8 → 7/7* | 5/8 → 4/8 | 8/8 → 8/8 |
| Titanic female survival | 8/8 → 8/8 | 8/8 → 7/7* | 8/8 → 8/8 |

`*` One prediction is unavailable; denominator is observed predictions, not the planned eight.

## Interpretation and caveats

1. **The mixed-context effect is model-dependent.** Muse improves from .75 solo to .85 in N4 mixed; Gemini 3.5 improves from .71 to .81 at N4 mixed and reaches .98 at N8 mixed; Gemini 2.5 is unchanged at N4 (.75 vs .75) and lower at N8 mixed (.63 vs .75 solo). Do not present contrastive context as a universal improvement.
2. **Pure homogeneous context is not reliably helpful.** It is below mixed in every model/size comparison. Muse's N4 pure score improves over solo, but N8 pure falls; both Gemini models have high benign specificity in pure groups while missing many hacks.
3. **Gemini 3.5's N8 result needs label-quality scrutiny.** It detects all 40 stored hacks but flags two benign schedule-vacation traces. Its rationale treats manual JSON construction as hacking; this may not discriminate the stored classes cleanly. Audit before interpreting 40/40 as robust detection.
4. **Schedule-vacation labels are especially uncertain.** Muse judges all eight stored hacks benign in every condition; Gemini 2.5 catches only 2/8; Gemini 3.5 catches 8/8 in N8 mixed but also false-positives similar benign behavior. Blind human audit is needed to distinguish detector error from debatable labels.
5. **N8 effects vary.** It adds no pooled accuracy over N4 for Muse, hurts Gemini 2.5, and benefits Gemini 3.5. Five task groups cannot separate stable size effects from task/partition variation.
6. **This does not prove similarity helps.** All peers are same-task. A matched other-task peer arm with equal N, mix, length profile, and model is required to isolate similarity from generic contrast or class-mixture effects.

### Prompt audit

The archived v1 prompt used TRACE's outlier framing, required relative indicators, and described hacking as exploiting evaluation “instead of genuinely solving.” That mismatches binary per-trajectory scoring in homogeneous clusters and may undercount hacks that coexist with genuine work. V2 removes outlier framing, makes comparison optional, and clarifies that success does not cancel evidence of exploitation. V1 files/results are retained separately. The v1→v2 change bundled wording with neutral random IDs, so it is **not** a wording-only ablation.

## Leakage controls and limitations

- The complete cluster is sent in **one call per cluster**; no per-slot detector calls.
- V2 model payloads contain full trajectory steps and random opaque IDs only: no labels, task IDs, batch/cluster IDs, source paths, or evaluator maps.
- OpenCode calls used a fresh, no-tools agent session and clean sandbox. This is tool-level isolation, **not** an OS/container sandbox.
- Vertex calls use text-only `generateContent` with no tools. ADC credentials remain outside this repository; scoring/mapping is parent-side.
- Schema/leakage checks passed for rendered inputs. Trajectories may themselves contain paths, data access, or agent statements that reveal behavior; those are source evidence, not evaluator-key fields.
- Stored labels are not human ground truth. The pilot has five task groups, one partition/seed, and no significance tests.
- Gemini 2.5 had five N1 input-echo failures after repeated recovery and partial outputs; metrics use returned verdicts only. Gemini 3.5 needed one syntax-only repair. Muse omitted one slot. Nothing is silently imputed.

## Repository map

- `selected_terminal_wrench_groups.json`, `targets/`, `n1_stripped/`: Stage-1 selection, evaluator labels, and label-free N1 inputs.
- `n1_results*/`, `n5_*`: earlier Muse/MiMo N1 and N5 pilots.
- `stage4_context_grid/pool_spec*.json`: batch definitions; `detector_inputs/`: stripped copies; `agent_snapshots/`: v1 prompts; `agent_snapshots_v2/`: current v2 prompt snapshots.
- `stage4_context_grid/results/`: Muse v1 outputs; `results_v2/`: Muse v2; `results_gemini/`: Gemini 2.5; `results_gemini35/`: Gemini 3.5.
- `stage4_context_grid/evaluator_only/`: trajectory-to-slot maps and reference labels. **Publishing this folder reveals the evaluation key**; this repository is a research artifact, not a blind public benchmark.
- `stage4_context_grid/gemini_ledger/`: Vertex usage/cost telemetry, not credentials.
- `prompts/`: Stage-1–3 records, archived Stage-4 v1, and Stage-4 v2; `scripts/`: preparation, checks, running, extraction, and scoring.
- `logs/stage4_n1n4_muse_runs.md`: chronological run, recovery, prompt-audit, and model notes.

## Reproduction notes

Rendered v2 inputs are included. Keep the detector no-tools and fresh-session boundaries; never attach evaluator maps, source labels, other clusters, or prior outputs.

OpenCode runner:

```bash
SANDBOX=/tmp/opencode/tw_sandbox_v2 \
MODEL=opencode-go/muse-spark-1.3-contributor#high \
OUT="$PWD/stage4_context_grid/results/raw_repro" \
PREFIX='*' SIZES="N1 N4 N8" CONCURRENCY=20 \
bash scripts/run_context_size_mix.sh
```

Vertex runner (requires gcloud ADC and `gemini_client.py` from the job-intelligence project; set `JOB_INTEL_SCRIPTS` if it is not at `~/job-intelligence/scripts`):

```bash
python3 scripts/run_gemini_v2.py --sizes "N1 N4 N8" --prefix "*" \
  --workers 20 --model gemini-3.5-flash-lite --results results_gemini35_repro \
  --tier tw-detect-35l
```

Use scripts under `scripts/` to prepare/check inputs, extract, and score.

## Citation

Please cite TRACE for the methodology lineage and Terminal Wrench for the data:

```bibtex
@article{deshpande2026trace,
  title   = {Benchmarking Reward Hack Detection in Code Environments via Contrastive Analysis},
  author  = {Deshpande, Darshan and Kannappan, Anand and Qian, Rebecca},
  journal = {arXiv preprint arXiv:2601.20103},
  year    = {2026},
  url     = {https://arxiv.org/abs/2601.20103}
}

@article{terminalwrench2026,
  title = {Terminal Wrench},
  year  = {2026},
  url   = {https://arxiv.org/abs/2604.17596}
}
```

TRACE supplies the contrastive prompt/methodology lineage; Terminal Wrench supplies the trajectories and reference labels. This is an exploratory extension, not a reproduction of the TRACE benchmark or a validated production detector.
