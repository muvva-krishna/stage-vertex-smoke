"""Run configuration: model, harness, sampling, limits, environment hash."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunConfig:
    model: str = "not-configured"
    model_version: str = "not-configured"
    harness: str = "debev-0.1.0"
    temperature: float | None = None
    seed: int | None = None
    max_tool_calls: int = 60
    max_wall_seconds: int = 1800
    max_evidence_tokens: int = 2000
    repetitions: int = 1
    randomize_order: bool = True
    dependency_versions: dict = field(default_factory=dict)
    environment_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "RunConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def compute_environment_hash(extra: str = "") -> str:
    """Hash of interpreter/platform info. Never includes env vars or secrets."""
    payload = json.dumps(
        {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "extra": extra,
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def default_config() -> RunConfig:
    cfg = RunConfig()
    cfg.environment_hash = compute_environment_hash()
    return cfg
