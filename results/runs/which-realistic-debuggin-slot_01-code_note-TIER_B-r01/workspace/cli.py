import sys
import os
import json

# This file is part of cfgmigrate.
# It is intended to be run as a module, e.g.
#   python -m cfgmigrate

# Add the current directory to sys.path to allow importing state module
sys.path.insert(0, os.path.dirname(__file__))

from state import migrate, MIGRATION_STEPS

def main():
    import argparse

    parser = argparse.ArgumentParser(description="cfgmigrate: safe resume after an interrupted migration.")
    parser.add_argument("--steps", action="store_true", help="List all migration steps and exit.")
    args = parser.parse_args()

    if args.steps:
        for step in MIGRATION_STEPS:
            print(step.__name__)
        exit(0)

    # Default behavior: migrate the config file
    # The config file name is hardcoded in state.py as CONFIG_FILE
    migrate(os.path.join(os.path.dirname(__file__), "config.json"))

if __name__ == "__main__":
    main()
