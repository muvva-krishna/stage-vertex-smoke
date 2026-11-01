# Stage 4 design status (NOT RUN)

User requested a simple class-composition / cluster-size study. Proposed cohort: 3 same-task groups (IoT registration, Iris, Titanic), 8 sanitized hacks + 8 successful baselines each. Preserve Stage 1 selected examples, add three distinct matched pairs per task from remaining Terminal Wrench records.

Use identical TRACE Appendix-C-derived multi-trajectory prompt and one cheap model (`opencode-go/muse-spark-1.3-contributor#high`) for N=1/N=4/N=8. N=1 is the same prompt with one slot. All members receive a prediction in a joint N=4/N=8 call.

Counts if pool fetch/build succeeds: 48 N1 + 24 N4 + 12 N8 = 84 calls/model. At each task: N4 has 2 pure-hack, 2 pure-benign, 4 mixed-2H/2B clusters; N8 has 1 pure-hack, 1 pure-benign, 2 mixed-4H/4B clusters. Each trajectory is reused at every size and in homogeneous + mixed contexts.

Metric: accuracy/precision/recall/F1/FPR for mixed sets; recall/FNR for all-hack; FPR/specificity for all-benign. Compare identical trajectory cohort across N/composition; no flip-rate headline. Bootstrap by task group; three tasks make this exploratory only.

Honesty: this design measures same-task context size and label-mix effects, NOT similarity against dissimilar peers. A matched other-task arm is still required to make the specific similarity claim. Buffer-overflow and AMUSE excluded from initial N8 set based on source-token/context risk; exact tokenizer preflight remains mandatory. Current downloaded local selection has only 5 per class/task, so 3 more per class/task must be fetched by `scripts/prepare_context_size_mix.py` before clusters can be built.

The planned exporter renders a self-contained prompt with the whole cluster embedded in one input. It creates one neutral snapshot per run; the launch instruction is to pass only that inline prompt to a fresh subagent, with no file/web/tool reads. Evaluator-only maps remain outside those snapshots.

Nothing was fetched, generated, evaluated, or run for this stage.
