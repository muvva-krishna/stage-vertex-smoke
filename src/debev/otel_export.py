"""OTLP JSON trace export (isolated adapter, stdlib only).

Converts `trajectory.jsonl` + run metadata to the OTLP JSON trace shape
(`resourceSpans`; field mapping follows opentelemetry-proto v1 — pinned in
OTLP_SHAPE below, no OTel dependency). Each trajectory event becomes one
span named `debev.<type>`.

Deliberately NOT using OpenTelemetry's GenAI/agent conventions: those are
marked development-status upstream, so this adapter uses plain `debev.*`
attribute keys. Do not claim conformance with any agent-convention version,
and do not claim validated interop with TRAIL tooling or any OTel consumer
unless tested against that consumer.

Stability rules:
- IDs are SHA-256 digests (trace = run_id; span = run_id + seq) — stable
  across processes. Python's salted `hash()` is never used.
- Timestamps: if the trajectory's run_start carries `t_epoch` (unix seconds,
  recorded by current harness runs), event times are absolute
  (t_epoch + t_wall_s) and the export is marked time_basis=absolute.
  Otherwise times are relative offsets and marked time_basis=relative —
  never a fabricated calendar date.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

OTLP_SHAPE = "opentelemetry-proto/v1 trace JSON mapping"
ADAPTER_VERSION = "0.2.0"


def _attr(key: str, value: Any) -> dict:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, (int, float)):
        return {"key": key, "value": {"doubleValue": float(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _trace_id(run_id: str) -> str:
    return hashlib.sha256(f"trace:{run_id}".encode()).hexdigest()[:32]


def _span_id(run_id: str, seq: int) -> str:
    return hashlib.sha256(f"span:{run_id}:{seq}".encode()).hexdigest()[:16]


def export_otlp(events: list[dict], meta: dict) -> dict:
    run_id = meta.get("run_id", "")
    start_epoch = None
    for e in events:
        if e.get("type") == "run_start" and isinstance(
            e.get("data", {}).get("t_epoch"), (int, float)
        ):
            start_epoch = float(e["data"]["t_epoch"])
            break
    time_basis = "absolute" if start_epoch is not None else "relative"
    base_attrs = [
        _attr("debev.run_id", run_id),
        _attr("debev.task_id", meta.get("task_id", "")),
        _attr("debev.condition", meta.get("condition", "")),
        _attr("debev.replayed", bool(meta.get("replayed", False))),
        _attr("debev.harness", "debev-0.1.0"),
        _attr("debev.exporter", f"otel_export/{ADAPTER_VERSION}"),
        _attr("debev.otlp_shape", OTLP_SHAPE),
        _attr("debev.time_basis", time_basis),
    ]
    trace_id = _trace_id(run_id)
    spans = []
    for e in events:
        data = e.get("data", {})
        attrs = list(base_attrs) + [
            _attr(f"debev.{k}", v)
            for k, v in data.items()
            if isinstance(v, (str, int, float, bool))
        ][:30]
        offset_ns = int(e.get("t_wall_s", 0) * 1e9)
        if start_epoch is not None:
            start_ns = int(start_epoch * 1e9) + offset_ns
        else:
            start_ns = offset_ns  # relative offset; see debev.time_basis
        spans.append(
            {
                "traceId": trace_id,
                "spanId": _span_id(run_id, int(e.get("seq", 0))),
                "name": f"debev.{e.get('type', 'unknown')}",
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(start_ns + 1_000_000),
                "attributes": attrs,
                "status": {"code": 1},
            }
        )
    doc = {
        "resourceSpans": [
            {
                "resource": {"attributes": base_attrs},
                "scopeSpans": [
                    {"scope": {"name": "debev", "version": "0.1.0"}, "spans": spans}
                ],
            }
        ]
    }
    validate_otlp(doc)
    return doc


def validate_otlp(doc: dict) -> None:
    """Minimal structural check of the emitted OTLP JSON shape."""
    rs = doc.get("resourceSpans")
    assert isinstance(rs, list) and len(rs) == 1, "one resourceSpans entry"
    scopes = rs[0].get("scopeSpans")
    assert isinstance(scopes, list) and len(scopes) == 1, "one scopeSpans entry"
    spans = scopes[0].get("spans")
    assert isinstance(spans, list), "spans must be a list"
    import re

    for s in spans:
        assert re.fullmatch(r"[0-9a-f]{32}", s.get("traceId", "")), "traceId 32 hex"
        assert re.fullmatch(r"[0-9a-f]{16}", s.get("spanId", "")), "spanId 16 hex"
        assert s.get("name", "").startswith("debev."), "span name prefix"
        assert str(s.get("startTimeUnixNano", "")).isdigit(), "start time nanos"
        assert str(s.get("endTimeUnixNano", "")).isdigit(), "end time nanos"
        assert isinstance(s.get("attributes"), list), "attributes list"


def export_file(run_dir: Path, out_path: Path) -> Path:
    events = [
        json.loads(line)
        for line in (run_dir / "trajectory.jsonl").read_text().splitlines()
        if line.strip()
    ]
    meta = json.loads((run_dir / "run_meta.json").read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(export_otlp(events, meta), indent=2) + "\n")
    return out_path
