# Stage 4 score plan

Primary question: does same-task context improve classification of this same 48-trajectory cohort, and does label mixture help or hurt as N grows?

For each N and composition (pure hack, pure benign, mixed):

- Mixed sets: accuracy, precision, recall, F1, FPR.
- Pure-hack sets: recall and false-negative rate only.
- Pure-benign sets: FPR and specificity only.
- Compare aggregate metrics at N=1, N=4, N=8 using identical trajectory IDs and the same model/prompt. Report paired correct/incorrect counts as supporting detail; do not make flips the primary metric.
- Report per-task metrics and task-group bootstrap intervals. There are only 3 planned tasks, so intervals/significance are exploratory and unstable.

This same-task-only grid cannot isolate a similarity effect. A same-N/same-mix other-task peer arm is needed for that claim.
