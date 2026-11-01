"""Reference implementation for safe, restartable settings migration."""
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
    if config.get("schema_version") != 1:
        raise MigrationError("only schema version 1 can be upgraded")
    preferences = config.get("preferences", {})
    if not isinstance(preferences, dict):
        raise MigrationError("preferences must be a JSON object")
    return {
        "schema_version": 2,
        "service": {"endpoint": config.get("endpoint", "")},
        "retry": {"max_attempts": config.get("retries", 3)},
        "extensions": preferences,
    }


def _is_v2(config: dict) -> bool:
    return (
        config.get("schema_version") == 2
        and isinstance(config.get("service"), dict)
        and isinstance(config.get("retry"), dict)
        and isinstance(config.get("extensions"), dict)
    )


def migrate_file(path: str | Path) -> dict:
    """Upgrade settings and recover safely from an interrupted invocation."""
    path = Path(path)
    marker_path = _sidecar(path, ".migration.json")
    backup_path = _sidecar(path, ".migration.bak")
    marker = _read_json(marker_path) if marker_path.exists() else {}

    try:
        current = _read_json(path)
    except MigrationError:
        if marker.get("status") != "in_progress" or not backup_path.is_file():
            raise
        # A failed atomic write may leave an unreadable target; restore the
        # saved source before resuming the conversion.
        current = _read_json(backup_path)

    if marker.get("status") == "complete" and _is_v2(current):
        return current

    if marker.get("status") == "in_progress" and _is_v2(current):
        # The v2 target was committed; only the completion marker was lost.
        # Mark it complete without re-converting or overwriting user fields.
        _atomic_write(marker_path, {"status": "complete"})
        return current

    if marker.get("status") == "in_progress" and backup_path.is_file():
        current = _read_json(backup_path)

    if current.get("schema_version") != 1:
        raise MigrationError(f"unsupported schema version: {current.get('schema_version')!r}")
    if not backup_path.exists():
        _atomic_write(backup_path, current)
    _atomic_write(marker_path, {"status": "in_progress"})
    upgraded = _upgrade_v1(current)
    _atomic_write(path, upgraded)
    _atomic_write(marker_path, {"status": "complete"})
    return upgraded
