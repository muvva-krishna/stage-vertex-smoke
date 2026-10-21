#!/bin/bash
set -euo pipefail

V1_CONFIG='{"name": "test_config", "items": [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]}'
EXPECTED_V2_CONFIG_PY=$(python -c 'import json; print(json.dumps({"name": "test_config", "version": 2, "entries": [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]}, indent=2))')

TEST_DIR="test_run"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo "--- Test 1: Fresh run ---"
CONFIG_FILE="fresh_run_config.json"
MARKER_FILE="${CONFIG_FILE}.migration.json"
echo "$V1_CONFIG" > "$CONFIG_FILE"
python ../cli.py --config "$CONFIG_FILE"
if ! diff -u <(echo -e "$EXPECTED_V2_CONFIG_PY") "$CONFIG_FILE"; then
    echo "FAIL: Fresh run config mismatch"
    diff -u <(echo -e "$EXPECTED_V2_CONFIG_PY") "$CONFIG_FILE"
    exit 1
fi
if ! grep -q '"done": \["add_version", "rename_items_to_entries", "remove_items"\]' "$MARKER_FILE"; then
    echo "FAIL: Fresh run marker file incomplete"
    exit 1
fi
echo "PASS: Fresh run"

echo "--- Test 2: Interrupted run + resume ---"
STEPS=$(python ../cli.py --steps)
for STEP in $STEPS; do
    echo "Testing interruption after step: $STEP"
    CONFIG_FILE="interrupted_config_${STEP}.json"
    MARKER_FILE="${CONFIG_FILE}.migration.json"
    echo "$V1_CONFIG" > "$CONFIG_FILE"

    # First run: interrupt
    MIGRATE_STOP_AFTER="$STEP" python ../cli.py --config "$CONFIG_FILE" || true # Allow exit 0
    
    # Second run: resume
    unset MIGRATE_STOP_AFTER
    python ../cli.py --config "$CONFIG_FILE"

    if ! diff -u <(echo -e "$EXPECTED_V2_CONFIG_PY") "$CONFIG_FILE"; then
        echo "FAIL: Interrupted run config mismatch for step $STEP"
        diff -u <(echo -e "$EXPECTED_V2_CONFIG_PY") "$CONFIG_FILE"
        exit 1
    fi
    if ! grep -q '"done": \["add_version", "rename_items_to_entries", "remove_items"\]' "$MARKER_FILE"; then
        echo "FAIL: Interrupted run marker file incomplete for step $STEP"
        exit 1
    fi
    echo "PASS: Interrupted run for step $STEP"
done

echo "--- Test 3: Rerun on already-migrated config ---"
CONFIG_FILE="already_migrated_config.json"
MARKER_FILE="${CONFIG_FILE}.migration.json"
echo "$V1_CONFIG" > "$CONFIG_FILE"
python ../cli.py --config "$CONFIG_FILE" # First run to migrate
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak" # Make a backup for byte-identical check

OUTPUT=$(python ../cli.py --config "$CONFIG_FILE" 2>&1)
if ! echo "$OUTPUT" | grep -q "Config already fully migrated. Exiting."; then
    echo "FAIL: Rerun did not report already-complete"
    echo "Output: $OUTPUT"
    exit 1
fi
if ! diff -q "$CONFIG_FILE" "${CONFIG_FILE}.bak"; then
    echo "FAIL: Rerun changed already-migrated config"
    exit 1
fi
echo "PASS: Rerun on already-migrated config"

echo "All tests passed!"
cd ..
rm -rf "$TEST_DIR"
