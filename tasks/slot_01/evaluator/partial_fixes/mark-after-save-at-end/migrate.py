"""Partial-fix probe for slot_01 (evaluator-only): mark-after-work, save-at-end.

Fixes the ordering smell (marker now written after the transform) but still
persists nothing until the end, so an interruption still loses the step's
work while the marker claims it is done. Must still FAIL the oracle.
"""
import json
import os

STEPS = ["add_version", "rename_items"]


def add_version(cfg):
    cfg = dict(cfg)
    cfg["version"] = 2
    return cfg


def rename_items(cfg):
    cfg = dict(cfg)
    if "items" in cfg:
        cfg["entries"] = cfg.pop("items")
    return cfg


APPLY = {"add_version": add_version, "rename_items": rename_items}


def _load_config(path):
    with open(path) as f:
        return json.load(f)


def _save_config(path, cfg):
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


def _is_migrated(cfg):
    return cfg.get("version") == 2 and "entries" in cfg and "items" not in cfg


def run_migration(config_path, state_path):
    from state import load_marker, mark_done

    cfg = _load_config(config_path)
    if _is_migrated(cfg):
        return "already-complete"
    marker = load_marker(state_path)
    stop_after = os.environ.get("MIGRATE_STOP_AFTER")
    for step in STEPS:
        if step in marker["done"]:
            continue
        cfg = APPLY[step](cfg)
        mark_done(state_path, step)
        if stop_after == step:
            return "interrupted"
    _save_config(config_path, cfg)
    return "complete"
