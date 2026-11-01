# Investigation note

The restart path in `debev_config/migration.py` routes an in-progress migration through the same conversion helper used for the original version 1 input. Check whether that helper preserves fields from an already-converted configuration and what happens if the target cannot be parsed after an interrupted write.
