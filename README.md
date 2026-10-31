# Can stale debugging notes misdirect code localization?

This repository is a small, reproducible experiment about **debugging evidence freshness**. It checks whether a simple file-localization baseline is misled by notes from an older code revision, and whether filtering evidence by revision metadata avoids that error.

The experiment is intentionally narrow: eight synthetic Python debugging cases, three evidence conditions, three transparent retrieval strategies, and 72 deterministic trials. It needs only Python 3.10+ and makes no model/API calls.

## Run it

```bash
python3 experiments/staleness_probe.py
```

The script writes the complete trial data and summary to [`results/staleness_probe.json`](results/staleness_probe.json); a readable summary is in [`results/RESULTS.md`](results/RESULTS.md). The method, case definitions, scoring rule, and output are all in the repository; no credentials or external dataset are needed.

## What it measures

Each case has four candidate files and one known target file. The experiment compares:

- `issue_only`: rank files using words in the symptom alone.
- `all_evidence`: add every supplied debugging artifact, regardless of the code revision it describes.
- `revision_gated`: add only artifacts tagged with the current code revision.

The conditions provide a current trace, an older note that points at a distractor file, or both. The ranker counts lexical overlap between the issue/evidence text and short candidate-file summaries. The primary metric is top-1 target-file accuracy; mean reciprocal rank is also reported. This is a controlled probe of one failure mode, not a model benchmark or a test of code repair.

## Result

In this constructed sample, the unfiltered evidence ranker localized **3/8** targets with stale notes alone, compared with **6/8** for the issue-only baseline. With both current and stale evidence it reached **7/8**. Revision-gated evidence scored **6/8** with stale notes alone and **8/8** when current evidence was available, with or without the stale note. These counts are descriptive results for these eight toy cases; they do not estimate real-world agent performance.

## Motivation and limits

Recent coding-agent research measures which context agents retrieve and how debugging context changes repair outcomes. This probe takes a small adjacent step: it makes artifact revision provenance an explicit variable and measures the effect on a lexical file ranker. See [`docs/related_work.md`](docs/related_work.md) and [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md) for the paper links, design, and limitations.

The prior repository version was an unrun task-harness scaffold with empty task slots. Its scaffold files have been removed from the active project so the code, description, and reported result now describe the same experiment.
