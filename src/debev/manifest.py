"""Versioned task manifest schema and validation (stdlib only)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
RUBRIC_VERSION = "1.0.0"

VALID_CONDITIONS = (
    "symptom_only",
    "repro_log",
    "state_snapshot",
    "code_note",
    "combined",
)

REQUIRED_TOP_LEVEL = (
    "schema_version",
    "task_id",
    "title",
    "repo_snapshot",
    "task_instructions_ref",
    "allowed_tools",
    "conditions",
    "resource_limits",
    "oracle",
    "rubric_version",
    "provenance",
)


@dataclass
class ValidationIssue:
    level: str  # "error" or "warning"
    message: str


def load_manifest(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_manifest(data: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            issues.append(ValidationIssue("error", f"missing required key: {key}"))
    if issues:
        return issues
    if data.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "error",
                f"unsupported schema_version {data.get('schema_version')!r}, "
                f"expected {SCHEMA_VERSION!r}",
            )
        )
    if data.get("rubric_version") != RUBRIC_VERSION:
        issues.append(
            ValidationIssue(
                "error",
                f"unsupported rubric_version {data.get('rubric_version')!r}, "
                f"expected {RUBRIC_VERSION!r}",
            )
        )
    if not isinstance(data.get("task_id"), str) or not data["task_id"]:
        issues.append(ValidationIssue("error", "task_id must be a non-empty string"))
    rs = data.get("repo_snapshot", {})
    for k in ("kind", "ref", "provenance"):
        if k not in rs:
            issues.append(ValidationIssue("error", f"repo_snapshot missing key: {k}"))
    if not isinstance(data.get("allowed_tools"), list) or not data["allowed_tools"]:
        issues.append(ValidationIssue("error", "allowed_tools must be a non-empty list"))
    conds = data.get("conditions", [])
    if not isinstance(conds, list) or not conds:
        issues.append(ValidationIssue("error", "conditions must be a non-empty list"))
    else:
        for c in conds:
            if c not in VALID_CONDITIONS:
                issues.append(ValidationIssue("error", f"unknown condition: {c!r}"))
        for required in VALID_CONDITIONS:
            if required not in conds:
                issues.append(
                    ValidationIssue(
                        "warning",
                        f"condition {required!r} not listed; pilot expects all five "
                        "conditions per task",
                    )
                )
    limits = data.get("resource_limits", {})
    for k in ("max_tool_calls", "max_wall_seconds", "max_evidence_tokens"):
        if k not in limits:
            issues.append(ValidationIssue("error", f"resource_limits missing key: {k}"))
    oracle = data.get("oracle", {})
    for k in ("entry_point", "type"):
        if k not in oracle:
            issues.append(ValidationIssue("error", f"oracle missing key: {k}"))
    prov = data.get("provenance", {})
    for k in ("author", "created", "source"):
        if k not in prov:
            issues.append(ValidationIssue("error", f"provenance missing key: {k}"))
    # Human-authorship guardrails: instruction/patch/answer content must not live here.
    for banned in ("reference_patch", "hidden_tests", "accepted_diagnosis", "solution"):
        if banned in data:
            issues.append(
                ValidationIssue(
                    "error",
                    f"manifest must not contain {banned!r}; keep evaluator answers "
                    "out of the manifest (see docs/task_authoring_spec.md)",
                )
            )
    return issues


def is_valid(data: dict) -> bool:
    return not any(i.level == "error" for i in validate_manifest(data))
