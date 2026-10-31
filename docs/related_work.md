# Related work

This project asks a narrow follow-up question about evidence retrieval: does revision metadata help a file-localization method avoid stale debugging notes?

## ContextBench

[ContextBench: A Benchmark for Context Retrieval in Coding Agents](https://arxiv.org/abs/2602.05892) evaluates context retrieval across 1,136 issue-resolution tasks and tracks context recall, precision, and efficiency. Its process-oriented measurements motivate looking at intermediate localization behavior rather than only whether a final patch passes. This repository borrows that measurement focus, but uses eight synthetic cases and a hand-written lexical ranker; it does not reuse ContextBench tasks, code, or annotations.

## DDBench

[Evaluating Agentic Code Repair Capabilities in Distributed Systems](https://arxiv.org/abs/2608.14863) compares symptom-only runs with runs supplied bounded debugging context, and reports that context can sometimes mislead. That observation motivates making stale context a controlled variable here. This project does not reuse DDBench bugs, data, or code, and it does not reproduce DDBench's agent experiments.

## What this project adds

The toy probe tags evidence with a code revision and compares retrieval with no evidence, all evidence, and revision-matched evidence. Its result only demonstrates the mechanics of this controlled setup. It does not establish that revision filtering improves real coding agents; that would require repository-level tasks, actual agents, and broader evaluation.
