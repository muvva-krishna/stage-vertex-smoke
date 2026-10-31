"""Observable trajectory recorder. No private chain-of-thought is collected.

Captured event types (see docs/trajectory_schema.md):
  run_start, evidence_access, file_read, file_write, command, test_run,
  verification, agent_note (short user-visible diagnosis/verification summary only),
  diff, run_end
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_EVENT_TYPES = (
    "run_start",
    "evidence_access",
    "file_read",
    "file_write",
    "command",
    "test_run",
    "verification",
    "agent_note",
    "diff",
    "run_end",
)

BANNED_NOTE_KEYS = ("chain_of_thought", "cot", "hidden_reasoning", "system_prompt")


@dataclass
class TrajectoryRecorder:
    run_id: str
    task_id: str
    condition: str
    _events: list[dict[str, Any]] = field(default_factory=list)
    _seq: int = 0
    _t0: float = field(default_factory=time.time)

    def record(self, event_type: str, data: dict[str, Any] | None = None) -> dict:
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"unknown event type: {event_type!r}")
        data = dict(data or {})
        for banned in BANNED_NOTE_KEYS:
            if banned in data:
                raise ValueError(
                    f"refusing to record private reasoning field {banned!r}; "
                    "only observable tool activity and short user-visible summaries"
                )
        self._seq += 1
        event = {
            "seq": self._seq,
            "t_wall_s": round(time.time() - self._t0, 3),
            "type": event_type,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "condition": self.condition,
            "data": data,
        }
        self._events.append(event)
        return event

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def write_jsonl(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for e in self._events:
                f.write(json.dumps(e) + "\n")
        return path


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
