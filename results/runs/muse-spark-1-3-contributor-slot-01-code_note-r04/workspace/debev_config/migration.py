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
    if config.get("schema_version") not in (1, 2):
        raise MigrationError("only schema versions 1 and 2 are supported")
    service = config.get("service") if isinstance(config.get("service"), dict) else {}
    retry = config.get("retry") if isinstance(config.get("retry"), dict) else {}
    preferences = config.get("preferences")
    if isinstance(preferences, dict):
        extensions = preferences
    else:
        ext = config.get("extensions")
        extensions = ext if isinstance(ext, dict) else {}
    return {
        "schema_version": 2,
        "service": {"endpoint": config.get("endpoint", service.get("endpoint", ""))},
        "retry": {"max_attempts": config.get("retries", retry.get("max_attempts", 3))},
        "extensions": extensions,
    }


def migrate_file(path: str | Path) -> dict:
    """Migrate a config file, tracking a backup and progress sidecar."""
    path = Path(path)
    marker_path = _sidecar(path, ".migration.json")
    backup_path = _sidecar(path, ".migration.bak")
    try:
        current = _read_json(path)
    except MigrationError as read_exc:
        if not backup_path.exists():
            raise
        try:
            backup_data = _read_json(backup_path)
        except MigrationError:
            raise read_exc from None
        if backup_data.get("schema_version") not in (1, 2):
            raise read_exc from None
        upgraded = _upgrade_v1(backup_data)
        _atomic_write(path, upgraded)
        _atomic_write(marker_path, {"status": "complete"})
        return upgraded
    try:
        marker = _read_json(marker_path) if marker_path.exists() else {}
    except MigrationError:
        marker = {}
    if current.get("schema_version") == 2:
        if marker.get("status") == "complete":
            return current
        needs_fix = not isinstance(current.get("extensions"), dict) or current.get("extensions") == {}
        if needs_fix and backup_path.exists():
            try:
                backup_data = _read_json(backup_path)
            except MigrationError:
                backup_data = None
            if isinstance(backup_data, dict):
                cand = backup_data.get("preferences", backup_data.get("extensions"))
                if isinstance(cand, dict) and cand and current.get("extensions") != cand:
                    current = {**current, "extensions": cand}
                    _atomic_write(path, current)
        if marker.get("status") != "complete":
            _atomic_write(marker_path, {"status": "complete"})
        return current
    if current.get("schema_version") != 1:
        raise MigrationError(f"unsupported schema version: {current.get('schema_version')!r}")
    if not backup_path.exists():
        _atomic_write(backup_path, current)
    _atomic_write(marker_path, {"status": "in_progress"})
    upgraded = _upgrade_v1(current)
    _atomic_write(path, upgraded)
    _atomic_write(marker_path, {"status": "complete"})
    return upgraded
