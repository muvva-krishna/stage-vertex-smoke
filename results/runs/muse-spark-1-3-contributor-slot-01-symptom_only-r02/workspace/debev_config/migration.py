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


def _is_valid_v2(config: dict) -> bool:
    if config.get("schema_version") != 2:
        return False
    service = config.get("service")
    retry = config.get("retry")
    extensions = config.get("extensions")
    return isinstance(service, dict) and isinstance(retry, dict) and isinstance(extensions, dict)


def _upgrade_v1(config: dict) -> dict:
    version = config.get("schema_version")
    if version == 2:
        if _is_valid_v2(config):
            return dict(config)
        service = config.get("service")
        if not isinstance(service, dict):
            service = {"endpoint": config.get("endpoint", "")}
        retry = config.get("retry")
        if not isinstance(retry, dict):
            retry = {"max_attempts": config.get("retries", 3)}
        extensions = config.get("extensions")
        if not isinstance(extensions, dict):
            prefs = config.get("preferences")
            extensions = prefs if isinstance(prefs, dict) else {}
        return {
            "schema_version": 2,
            "service": service,
            "retry": retry,
            "extensions": extensions,
        }
    if version != 1:
        raise MigrationError("only schema versions 1 and 2 are supported")
    prefs = config.get("preferences", {})
    if not isinstance(prefs, dict):
        prefs = {}
    ext_fallback = config.get("extensions", {})
    if "preferences" not in config and isinstance(ext_fallback, dict):
        prefs = ext_fallback
    return {
        "schema_version": 2,
        "service": {"endpoint": config.get("endpoint", config.get("service", {}).get("endpoint", "")) if isinstance(config.get("service", {}), dict) else config.get("endpoint", "")},
        "retry": {"max_attempts": config.get("retries", config.get("retry", {}).get("max_attempts", 3)) if isinstance(config.get("retry", {}), dict) else config.get("retries", 3)},
        "extensions": prefs,
    }


def _migrate_backup_source(backup: dict) -> dict:
    if _is_valid_v2(backup):
        return dict(backup)
    if backup.get("schema_version") == 1:
        return _upgrade_v1(backup)
    if backup.get("schema_version") == 2:
        return _upgrade_v1(backup)
    raise MigrationError(f"unsupported schema version: {backup.get('schema_version')!r}")


def migrate_file(path: str | Path) -> dict:
    """Migrate a config file, tracking a backup and progress sidecar."""
    path = Path(path)
    marker_path = _sidecar(path, ".migration.json")
    backup_path = _sidecar(path, ".migration.bak")
    try:
        marker = _read_json(marker_path) if marker_path.exists() else {}
    except MigrationError:
        marker = {}
    if not isinstance(marker, dict):
        marker = {}

    try:
        current = _read_json(path)
    except MigrationError as exc:
        if backup_path.exists():
            try:
                backup = _read_json(backup_path)
            except MigrationError:
                raise exc from None
            upgraded = _migrate_backup_source(backup)
            _atomic_write(path, upgraded)
            _atomic_write(marker_path, {"status": "complete"})
            return upgraded
        raise

    if _is_valid_v2(current):
        if marker.get("status") != "complete":
            _atomic_write(marker_path, {"status": "complete"})
        return current

    if current.get("schema_version") == 1:
        if not backup_path.exists():
            _atomic_write(backup_path, current)
        if marker.get("status") != "in_progress":
            _atomic_write(marker_path, {"status": "in_progress"})
        upgraded = _upgrade_v1(current)
        _atomic_write(path, upgraded)
        _atomic_write(marker_path, {"status": "complete"})
        return upgraded

    if marker.get("status") == "in_progress" and backup_path.exists():
        backup = _read_json(backup_path)
        upgraded = _migrate_backup_source(backup)
        _atomic_write(path, upgraded)
        _atomic_write(marker_path, {"status": "complete"})
        return upgraded

    if current.get("schema_version") != 1:
        raise MigrationError(f"unsupported schema version: {current.get('schema_version')!r}")
    raise MigrationError("incomplete configuration, no backup available")
