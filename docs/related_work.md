# Related work

Survey conducted 2026-10-21. All links below were fetched and verified on that
date. No benchmark tasks, prompts, hidden tests, datasets, or answer keys were
copied from any of these sources. This pilot reuses **patterns only**
(harness structure, oracle conventions, taxonomy ideas), with original code
throughout.

## 1. DDBench — Evaluating Agentic Code Repair Capabilities in Distributed Systems

- Paper (abstract): https://arxiv.org/abs/2608.14863
- Full text (HTML): https://arxiv.org/html/2608.14863
- Authors: Yan, Wang, He, Liang, Wang, Sun, Park (USC). Submitted 14 Aug 2026, under submission.
- What it is: 60 historical bugs from 13 open-source distributed systems
  (key-value stores, consensus libraries, messaging, service meshes, streaming,
  storage; Go/C++/Java/Erlang/Rust), partitioned into three difficulty tiers
  (31 / 15 / 14). Each case ships a pinned faulty git worktree, a
  symptom description (`SYMPTOM.md`), a hidden PASS/FAIL oracle, and a
  debug-context bundle (1–3 short Markdown files, median ~321 tokens).
- Experiment: every case run under two matched conditions — **symptom-only**
  vs **context-augmented** — isolating debugging context from model capability
  (agent mini-swe-agent, 10 LLMs, max 450 steps / $5 / 30 min per case).
- Headline results (theirs, not ours): +18.1 pp aggregate pass-rate lift from
  bounded context (32.6% → 50.6%); asymmetric — weaker models gain pass rate
  (e.g. GLM 4.7: 9.7% → 48.4%), stronger models gain efficiency (e.g. Opus 4.6:
  −69% tokens at flat pass rate); 61 pp cross-model spread on the hardest tier;
  faithful context can sometimes mislead (abstraction-distance hypothesis).
- Stated limitation driving this pilot (Section 4): *"The two-condition
  contrast treats the bundle as an atomic unit and so cannot tell us which
  component of the bundle (logs, traces, goroutine dumps, code-investigation
  notes) drives the gain."* This pilot's five-condition design (symptom only /
  repro log / state snapshot / code note / combined) is a small, original
  step toward that ablation. It is a pilot instrument, not a new benchmark
  claim.
- Code/data status: the paper says the codebase, dataset, infrastructure, and
  mining protocol are released alongside the paper, but **no canonical GitHub
  URL has been verified here**. The arXiv abstract page exposes no code link;
  web search surfaced no official DDBench repository (a similarly named
  `OrderLab/distdebug-bench` is a *different* project — code-level diagnosis
  labels, not repair — and is not DDBench). **No DDBench code or data is reused
  in this pilot; nothing was guessed or copied.** If the official repository
  is located later, record its URL and license here before reusing anything.
- Per-project licenses (DDBench Appendix B.2, for provenance reference):
  all 13 upstream systems are permissive (Apache-2.0, MPL-2.0, or BSL-1.1).
- Reuse in this pilot: **none** (no accessible, license-verifiable artifact).
  Influence only: matched symptom-only vs evidence-supplied design, bounded
  context budget, agent-agnostic oracle, PASS/FAIL-not-textual-match scoring.

## 2. TRAIL — Trace Reasoning and Agentic Issue Localization (Patronus AI)

- Paper: https://arxiv.org/abs/2505.08638 (Deshpande et al., May 2025)
- Code: https://github.com/patronus-ai/trail-benchmark — **MIT license** (verified via repo page).
- Data: https://huggingface.co/datasets/PatronusAI/TRAIL
- What it is: 148 human-annotated agent execution traces (GAIA + SWE-Bench
  derived, OpenTelemetry spans) with 841 errors; best model (Gemini-2.5-Pro)
  scores ~11% joint accuracy. It measures **diagnosis of errors in agent
  execution traces**, not code repair.
- Taxonomy (used as *inspiration only*): 3 high-level areas — reasoning,
  planning/coordination, system execution — refined into ~21 categories
  (hallucinations, tool-output misinterpretation, tool selection, formatting,
  instruction non-compliance, API/system errors, timeouts, context handling,
  goal deviation, task orchestration, …).
- Overlap/difference: TRAIL errors are about *agent behavior in traces*;
  this pilot's failure taxonomy is about *repair trajectories against an
  oracle* (missed/misread evidence, wrong causal hypothesis, incomplete
  repair, regression, constraint violation, inadequate verification,
  inaccurate final report). The pilot borrows the observed-vs-interpretation
  discipline, not the annotations. **No TRAIL annotations, traces, or code
  were copied.**
- Reuse in this pilot: none beyond taxonomy influence, attributed here.

## 3. SWT-Bench — Testing and Validating Real-World Bug-Fixes with Code Agents

- Paper: https://arxiv.org/abs/2406.12952 (Mündler et al., NeurIPS 2024)
- Code: https://github.com/logic-star-ai/SWT-Bench — **MIT license** (verified via repo page).
- What it is: benchmark + Docker evaluation harness for LLM test generation
  on real GitHub issues; unit-test mode and reproduction-script mode; reports
  fail-to-pass / pass-to-pass transitions and coverage deltas; gold-patch
  validation runs.
- Influence on this pilot: reproducible execution pattern (containerized,
  pinned environment), oracle pattern (FAIL-on-buggy / PASS-on-fixed,
  accept-any-passing-patch rather than textual match), and the
  `run_instance`-style logging discipline.
- Reuse in this pilot: **patterns only; no SWT-Bench code vendored.**
  The pilot's `GROUP <name> PASS|FAIL` oracle protocol and evaluator-outside-
  workspace rule follow the same idea with an original implementation. If
  SWT-Bench code is vendored later, record the MIT attribution and pin the
  commit here first.

## 4. ConcurBugBench (Columbia DAPLab)

- Page: https://daplab.cs.columbia.edu/benchmarks/concurbugbench/
- Status (verified 2026-10-21): **in development, not released** (~200
  real-world Go/Rust/C/C++ concurrency bugs planned; discovery / reproduction /
  repair stages with per-bug oracles; counts and procedures subject to change).
- Why it rules out a generic concurrency/event-order benchmark here: a
  duplicate/out-of-order-event repair benchmark would overlap this upcoming
  work (and the RGA CRDT task in coding-agent-bench below). This pilot
  therefore scopes to **which debugging evidence helps repair**, a question
  ConcurBugBench does not currently pose, and uses an original deterministic
  CLI-maintenance task domain instead of mined concurrency bugs.
- Reuse: none (nothing released to reuse).

## 5. coding-agent-bench (sipratt-p)

- Code: https://github.com/sipratt-p/coding-agent-bench — **MIT license** (verified via repo page).
- What it is: 9 Python implementation tasks (LRU, rate limiter, expression
  evaluator, trie, event emitter, regex engine, **RGA text CRDT under
  out-of-order and duplicate delivery**, async DAG orchestrator, streaming
  JSON parser) with hidden-test scoring and harness-effect analysis.
- Overlap note: its tiebreaker task 7 already covers duplicate/out-of-order
  RGA CRDT delivery — further confirmation that a generic event-order
  benchmark would duplicate existing work.
- Reuse: none; its harness lessons (extractor bugs, temperature defaults,
  INCONCLUSIVE vs failure, multi-run reporting) informed the pilot's
  evaluation-protocol rules, attributed here.

## 6. Patronus research + role context

- Research page: https://www.patronus.ai/research (lists TRAIL, FinanceBench,
  Lynx, Glider, and agent-simulation work).
- Role posting (boarding): https://www.patronus.ai/job-detail?gh_jid=4455311009&role=software-engineer-ai-evaluation-expert-contractual
- Official board entry: https://job-boards.greenhouse.io/patronusaiinc/jobs/4455311009
- Positioning: this pilot demonstrates realistic-task authoring, executable
  ground truth, trajectory capture, and failure analysis — the skills the
  role asks for. It connects to Patronus's trajectory-evaluation line
  (TRAIL) without claiming any Patronus flaw and without presenting the
  pilot as novel research.

## Reuse and attribution summary

| Source | License / status | Reused here |
|---|---|---|
| DDBench paper | CC BY 4.0 (arXiv); code URL unverified | Design influence only; no code/data |
| TRAIL benchmark | MIT; data on HuggingFace | Taxonomy-discipline influence only; no annotations/code |
| SWT-Bench | MIT | Oracle/execution patterns only; no vendored code |
| ConcurBugBench | Unreleased (in development) | Nothing to reuse; scope-avoidance rationale |
| coding-agent-bench | MIT | Harness-lesson influence only; no code |
| DistDebug-Bench (OrderLab) | Separate project, not DDBench | Not used; noted to avoid confusion |
