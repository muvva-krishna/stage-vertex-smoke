"""Plausible partial fix: preserve v2 extension keys during re-normalization."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class MigrationError(RuntimeError):
    pass


def _sidecar(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"{path.name} must contain a JSON object")
    return value


def _atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _upgrade_v1(config: dict) -> dict:
    if config.get("schema_version") not in (1, 2):
        raise MigrationError("only schema versions 1 and 2 are supported")
    return {
        "schema_version": 2,
        "service": {"endpoint": config.get("endpoint", config.get("service", {}).get("endpoint", ""))},
        "retry": {"max_attempts": config.get("retries", config.get("retry", {}).get("max_attempts", 3))},
        "extensions": config.get("extensions", config.get("preferences", {})),
    }


def migrate_file(path: str | Path) -> dict:
    path = Path(path)
    marker_path = _sidecar(path, ".migration.json")
    backup_path = _sidecar(path, ".migration.bak")
    current = _read_json(path)
    marker = _read_json(marker_path) if marker_path.exists() else {}
    if current.get("schema_version") == 2 and marker.get("status") == "complete":
        return current
    if current.get("schema_version") == 2 and marker.get("status") == "in_progress":
        upgraded = _upgrade_v1(current)
    else:
        if current.get("schema_version") != 1:
            raise MigrationError(f"unsupported schema version: {current.get('schema_version')!r}")
        if not backup_path.exists():
            _atomic_write(backup_path, current)
        _atomic_write(marker_path, {"status": "in_progress"})
        upgraded = _upgrade_v1(current)
    _atomic_write(path, upgraded)
    _atomic_write(marker_path, {"status": "complete"})
    return upgraded
