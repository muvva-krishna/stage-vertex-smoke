# Stage 4 — same-task cluster-size and label-mix pilot

Batch 1 DONE (frozen): 48 trajectories across iot/iris/titanic. Batch 2 DONE: 32 across schedule-vacation/sympy. N1/N4/N8 = 140 calls per detector. V1 and v2 runs are complete for Muse and Gemini 2.5/3.5; v2 is the neutral prompt in `prompts/stage4_context_grid.md`.

## Question this design can answer

For the same set of trajectories from a task/model group, does class-homogeneous or mixed same-task context change hacked/benign classification accuracy as cluster size grows from N=1 to N=4 to N=8?

This is a useful test of **same-task peer context and label-mix effects**. It does **not by itself isolate similarity**: all clusters here use same-task peers. To claim that similarity specifically helps, a later matched arm must use other-task peers with the same N, label composition, and approximate token length.

## Cohort and counts (two symmetric batches)

Batch 1: `iot-device-registration-server`, `iris-data-loading-script`, `titanic-female-survival-prediction` (all `claude-opus-4.6`), 8 hacks + 8 baselines each (Stage-1 five preserved + 3 matched) = 48 trajectories, 48 N1 + 24 N4 + 12 N8 = 84 runs.

Batch 2 (same shape, new tasks for diversity): `schedule-vacation` and `sympy-matrix-fix`, fresh eight pairs each via the same pair_cost; both verified by `scripts/verify_candidate_tasks.py` (all paths resolve, single instruction hash each). A full 323-task scan found only these 2 unused groups at >=8+8 (nearest misses have <=6 benigns), so a symmetric third new task does not exist — batch 2 is 2 tasks, not 3. Batch 2 = 32 trajectories, 32 N1 + 16 N4 + 8 N8 = 56 runs.

Per task (both batches): N4 = two all-hack + two all-benign + four 2H/2B mixed; N8 = one all-hack + one all-benign + two 4H/4B mixed. Every trajectory is evaluated at N=1, in a homogeneous cluster, and in a mixed cluster. Combined: 80 trajectories, 120 N1+N4 + 20 N8 = 140 calls. Batch 2 uses `D`-prefix cluster IDs and suffixed map files, so batch-1 results stay frozen and valid.

The older standalone Stage-2 N1 outcomes are historical and not the primary baseline; those inputs were capped and prompt wording differed. Stage-4 v1 reran the same 80-trajectory cohort at N1/N4/N8 with full inputs and one common prompt. V2 changes wording and model-visible IDs, so it needs a paired rerun before comparison.

## Model and execution

Primary detector: `opencode-go/muse-spark-1.3-contributor#high`. V1 used the Appendix-C outlier framing. V2 retains a joint input at every N but asks for neutral per-trajectory classification. The full set is one `--file` attachment per fresh call; never split members.

## Labels, fairness, and data quality

- Detector inputs contain only neutral slot IDs and trajectory steps. Labels, source paths, task IDs, evaluator rationales, and cluster membership maps stay in `evaluator_only/`.
- `.opencode/agents/trace-detector.md` is a project-local OpenCode subagent with all tools denied. Launch it from the repository root.
- `scripts/render_context_prompts.py` creates v2 snapshots under `agent_snapshots_v2/`; each contains only `prompt.txt`. V2 removes cluster/task/batch/N fields and replaces sequential slot IDs with random trajectory IDs. The complete cluster is attached once per fresh `trace-detector` call. The runner copies it to an opaque temporary filename inside the clean sandbox before attachment; it never gives the model a repository path.
- Keep all 8 selected hack and benign traces per task available in every size/composition arm; no target or peer is replaced between sizes.
- Match hack/benign examples by source token length and episode count where feasible. Record actual match ratios; do not silently truncate.
- The hack inputs are the repository's sanitized variants. Sanitization and agent-written analysis may still reveal intent; this is a dataset limitation, not a label leak.
- Source labels are stored judgments, not human ground truth. Audit a blind subset before strong claims.

## Metrics

Score every slot prediction, but report by N and composition:

- Mixed clusters: accuracy, precision, recall, F1, and false-positive rate.
- All-hack clusters: recall / false-negative rate (no benign examples, so precision/FPR are not estimable there).
- All-benign clusters: false-positive rate / specificity (no hack examples, so recall is not estimable there).
- Compare the same trajectory cohort at N=1, N=4, N=8, separately for homogeneous and mixed contexts. The primary evidence is change in aggregate accuracy/F1, not verdict-flip counts.
- Bootstrap/resample at the task-group level, not individual trajectories. Batch 1 (3 tasks) is exploratory only. The 5-task expansion is still small for population claims but doubles the task count and adds hack-class diversity (schedule-vacation: nonserious-only; sympy: serious-only).

## Similarity claim limitation

Same-task N=1→N=4/N=8 improvement would show that adding same-task context helped on this cohort. It would not prove that same-task similarity is the reason. For that, add a matched other-task peer arm at each N and mix. Describe that separate arm as `other-task` unless a predeclared semantic-similarity measure verifies dissimilarity.

The OpenCode subagent denies every tool, so it cannot read files or browse. This is tool-level isolation, not an OS/container sandbox. V1's outlier framing mismatched pure-cluster scoring; v2 addresses that prompt bias but requires a paired rerun before its effect can be estimated. See `SANDBOX.md` for the boundary and launch requirements.

Batch 1 and batch 2 outputs are complete for Muse Spark 1.3 Contributor, Gemini 2.5 Flash-Lite, and Gemini 3.5 Flash-Lite.
