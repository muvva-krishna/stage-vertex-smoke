"""AI-generated reference solution overlay for slot_01 (evaluator-only).

Fix: record a step done only AFTER its work is applied AND persisted.
Both the config and the marker are saved after every step, so a kill at
any point resumes exactly where the persisted state says.
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
    """Run pending steps, resuming from the marker file.

    MIGRATE_STOP_AFTER=<step> stops right after that step to simulate the
    process being killed mid-migration (used to reproduce interruption
    reports deterministically).
    """
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
        _save_config(config_path, cfg)
        mark_done(state_path, step)
        marker["done"].append(step)
        if stop_after == step:
            return "interrupted"
    return "complete"
