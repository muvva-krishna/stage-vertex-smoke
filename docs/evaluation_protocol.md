# Experiment protocol

## Question

On a small synthetic file-localization task, does filtering debugging artifacts to the current code revision prevent stale notes from lowering localization accuracy?

## Cases and conditions

`experiments/staleness_probe.py` defines eight synthetic cases. Each has four candidate file summaries, a symptom, a target file, a current-revision trace pointing to the target, and a previous-revision note pointing to a distractor. Every case runs under three evidence conditions:

1. `clean`: the current-revision trace is available.
2. `stale_only`: only the previous-revision note is available.
3. `fresh_plus_stale`: both artifacts are available.

Each condition is scored by three methods: issue-only lexical ranking, unfiltered evidence ranking, and revision-gated evidence ranking. Revision gating compares an artifact's revision tag to the task's current revision. The lexical scorer counts term overlap in the issue once per distinct term and in evidence once per occurrence; score ties are broken by candidate path. All inputs and ranking outcomes are saved in `results/staleness_probe.json`.

## Outcomes

Top-1 accuracy is the primary outcome. Mean reciprocal rank is secondary. There are eight trials per condition/method cell (72 total). These are deterministic, paired cases, not independent samples for statistical inference. There are no confidence intervals or significance tests.

## Reproduction

Run `python3 experiments/staleness_probe.py` from the repository root. The script uses only the Python standard library and overwrites the JSON results file with the current run. The cases are embedded in the script, so the JSON records the full ranked file order for every trial.

## Limits

The cases, evidence, and file summaries are synthetic. The retrieval method is a hand-written lexical baseline, not a language model or autonomous software agent. Evidence freshness is represented by an idealized revision tag, and filtering trusts that tag. The experiment measures file localization only, not code changes, test outcomes, repair quality, or real-world prevalence. Results are a reproducible demonstration and should not be generalized beyond this setup.
