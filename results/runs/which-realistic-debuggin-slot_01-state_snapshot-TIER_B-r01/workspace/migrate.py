import json
import os

from state import State, load_config, save_config, migrate_v1_to_v2, migrate_v2_to_v3, migrate_config, get_migration_steps

def migrate(config_path: str, stop_after: str | None = None) -> None:
    state = State(config_path)
    config = load_config(config_path)

    migration_steps = get_migration_steps()

    # Check if migration is already complete
    if state.is_done(migration_steps[-1]):
        print("already-complete")
        return

    # Iterate through steps and apply them if not done
    for step in migration_steps:
        if state.is_done(step):
            continue

        if stop_after == step:
            print("migration complete")
            return

        if step == "add_version":
            config = migrate_v1_to_v2(config)
        elif step == "rename_items_to_entries":
            # This step should rename 'items' to 'entries' if version is 2
            # The migrate_v1_to_v2 function already handles this by creating 'entries'
            # and we assume the input config is already v2 if we reach this step.
            # However, to be safe, we can ensure 'items' is removed if it exists.
            if 'items' in config:
                del config['items']
            # Ensure version is set to 2 if it was not already
            if 'version' not in config:
                config['version'] = 2

        state.mark_done(step)

    save_config(config_path, config)
    print("migration complete")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="cfgmigrate")
    parser.add_argument("config_path", help="Path to the config file.")
    parser.add_argument("--steps", action="store_true", help="List migration steps.")
    parser.add_argument("--stop-after", help="Stop after this step.")

    args = parser.parse_args()

    if args.steps:
        for step in get_migration_steps():
            print(step)
    else:
        migrate(args.config_path, args.stop_after)


if __name__ == "__main__":
    main()
