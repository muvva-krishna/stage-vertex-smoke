# Logs — Stage 1 selection

- Scanned 957 task/model groups; 793 with both classes; 57 with >=5 hacks and >=5 baselines.
- Selected 5 claude-opus-4.6 groups, prompt-hash verified: buffer-overflow-exploit, iot-device-registration-server, iris-data-loading-script, titanic-female-survival-prediction, amuse-install.
- 50 trajectories: 25 sanitized-hack + 25 baseline, 50 unique paths/IDs.
- Caveats: titanic length mismatch (hacks much shorter); buffer-overflow longest pair ~1.85x; amuse hacks shorter than baselines; token counts are source-reported.
- Output: `selected_terminal_wrench_groups.json`.
