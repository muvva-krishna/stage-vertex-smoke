"""TRAIL-compatible trajectory export (isolated adapter, stdlib only).

Converts `trajectory.jsonl` + run metadata to OTLP JSON trace shape
(`resourceSpans`, opentelemetry-proto v1 JSON mapping — pinned here, no OTel
dependency). Each trajectory event becomes one span named `debev.<type>`.

Deliberately NOT using OpenTelemetry's GenAI/agent conventions: those are
marked development-status upstream, so this adapter uses plain `debev.*`
attribute keys and documents the exact shape. Re-check upstream status
before claiming conformance with any agent-convention version.

Observed events only — the same no-chain-of-thought rule applies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OTLP_SHAPE = "opentelemetry-proto/v1 trace JSON mapping"
ADAPTER_VERSION = "0.1.0"


def _attr(key: str, value: Any) -> dict:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, (int, float)):
        return {"key": key, "value": {"doubleValue": float(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def export_otlp(events: list[dict], meta: dict) -> dict:
    base_attrs = [
        _attr("debev.run_id", meta.get("run_id", "")),
        _attr("debev.task_id", meta.get("task_id", "")),
        _attr("debev.condition", meta.get("condition", "")),
        _attr("debev.replayed", bool(meta.get("replayed", False))),
        _attr("debev.harness", "debev-0.1.0"),
        _attr("debev.exporter", f"otel_export/{ADAPTER_VERSION}"),
        _attr("debev.otlp_shape", OTLP_SHAPE),
    ]
    spans = []
    for e in events:
        data = e.get("data", {})
        attrs = list(base_attrs) + [
            _attr(f"debev.{k}", v)
            for k, v in data.items()
            if isinstance(v, (str, int, float, bool))
        ][:30]
        # OTLP uses unix nanos as strings; t_wall_s is relative, so anchor
        # span 1 at 1_700_000_000_000_000_000 + offset to keep values valid.
        start_ns = 1_700_000_000_000_000_000 + int(e.get("t_wall_s", 0) * 1e9)
        spans.append(
            {
                "traceId": f"{abs(hash(meta.get('run_id', ''))) % 2**128:032x}",
                "spanId": f"{e.get('seq', 0):016x}",
                "name": f"debev.{e.get('type', 'unknown')}",
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(start_ns + 1_000_000),
                "attributes": attrs,
                "status": {"code": 1},
            }
        )
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": base_attrs},
                "scopeSpans": [
                    {"scope": {"name": "debev", "version": "0.1.0"}, "spans": spans}
                ],
            }
        ]
    }


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
