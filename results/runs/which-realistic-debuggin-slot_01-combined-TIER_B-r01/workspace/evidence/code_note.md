# Code-path note

The resume loop lives in `run_migration` in `migrate.py`; step completion
is tracked by `mark_done` / `load_marker` in `state.py`, and the steps
themselves (`add_version`, `rename_items`) only transform an in-memory
dict. Compare when a step is recorded done against when its effect reaches
the config file on disk — in particular what survives if the process stops
between those two points.
(This note narrows the search region; it does not state the fix.)
