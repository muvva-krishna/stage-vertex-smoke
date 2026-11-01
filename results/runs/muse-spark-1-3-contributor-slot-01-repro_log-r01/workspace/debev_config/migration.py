"""Upgrade settings from schema 1 to schema 2."""
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
    if config.get("schema_version") == 2:
        service = config.get("service")
        if not isinstance(service, dict):
            service = {}
        retry = config.get("retry")
        if not isinstance(retry, dict):
            retry = {}
        extensions = config.get("extensions")
        if not isinstance(extensions, dict):
            preferences = config.get("preferences", {})
            extensions = preferences if isinstance(preferences, dict) else {}
        endpoint = service.get("endpoint", config.get("endpoint", ""))
        max_attempts = retry.get("max_attempts", config.get("retries", 3))
        return {
            "schema_version": 2,
            "service": {"endpoint": endpoint},
            "retry": {"max_attempts": max_attempts},
            "extensions": extensions,
        }
    if config.get("schema_version") != 1:
        raise MigrationError("only schema versions 1 and 2 are supported")
    return {
        "schema_version": 2,
        "service": {"endpoint": config.get("endpoint", config.get("service", {}).get("endpoint", ""))},
        "retry": {"max_attempts": config.get("retries", config.get("retry", {}).get("max_attempts", 3))},
        "extensions": config.get("preferences", {}),
    }


def _is_valid_v2(config: dict) -> bool:
    return (
        isinstance(config, dict)
        and config.get("schema_version") == 2
        and isinstance(config.get("service"), dict)
        and isinstance(config.get("retry"), dict)
        and isinstance(config.get("extensions"), dict)
    )


def migrate_file(path: str | Path) -> dict:
    """Migrate a config file, tracking a backup and progress sidecar."""
    path = Path(path)
    marker_path = _sidecar(path, ".migration.json")
    backup_path = _sidecar(path, ".migration.bak")
    if marker_path.exists():
        try:
            marker = _read_json(marker_path)
        except MigrationError:
            marker = {}
    else:
        marker = {}
    if not isinstance(marker, dict):
        marker = {}
    status = marker.get("status")
    backup = None
    if backup_path.exists():
        try:
            candidate = _read_json(backup_path)
        except MigrationError:
            candidate = None
        if isinstance(candidate, dict):
            backup = candidate
    try:
        current = _read_json(path)
    except MigrationError as exc:
        if status == "in_progress" and isinstance(backup, dict):
            recovered = _upgrade_v1(backup)
            _atomic_write(path, recovered)
            _atomic_write(marker_path, {"status": "complete"})
            return recovered
        raise
    if current.get("schema_version") == 2:
        if status == "complete":
            return current
        if status == "in_progress":
            if _is_valid_v2(current):
                _atomic_write(marker_path, {"status": "complete"})
                return current
            if isinstance(backup, dict):
                recovered = _upgrade_v1(backup)
                _atomic_write(path, recovered)
                _atomic_write(marker_path, {"status": "complete"})
                return recovered
            raise MigrationError(f"incomplete configuration in {path.name}; no backup available")
        return current
    if current.get("schema_version") != 1:
        if status == "in_progress" and isinstance(backup, dict):
            recovered = _upgrade_v1(backup)
            _atomic_write(path, recovered)
            _atomic_write(marker_path, {"status": "complete"})
            return recovered
        raise MigrationError(f"unsupported schema version: {current.get('schema_version')!r}")
    if backup is None:
        _atomic_write(backup_path, current)
    if status != "in_progress":
        _atomic_write(marker_path, {"status": "in_progress"})
    upgraded = _upgrade_v1(current)
    _atomic_write(path, upgraded)
    _atomic_write(marker_path, {"status": "complete"})
    return upgraded
