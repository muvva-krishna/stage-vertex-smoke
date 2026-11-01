# Logs — N=5 cluster build v2 (stored only, NOT run)

Correction: v1 had 4 similar-only clusters (no random arm), so it could show N=1→N=5 contrast but NOT the similarity effect. v2 backtraced to the central question.

Canonical 4 (report set):
- N5-A1 (iot, similar, 2H/3B): target hack TARGET-02 v5_14 @ SLOT-5. Peers: hack v5_3 + benign b:8/6/2. ~153k src tokens.
- N5-A1R (iot target, random-other-task peers, 2H/3B): same target v5_14 @ SLOT-5. Peers: iris hack v5_14 + titanic benign b:5/9/11. ~138k src tokens.
- N5-A2 (iot, similar, 2H/3B): target benign TARGET-07 b:7 @ SLOT-3. Peers: hacks v5_7/v5_3 + benign b:8/6. ~164k src tokens.
- N5-A2R (iot target, random-other-task peers, 2H/3B): same target b:7 @ SLOT-2. Peers: iris hacks v5_13/v5_16 + titanic benign b:5/11. ~129k src tokens.

Why iot targets: both were correct at N=1 (02 hack-hit, 07 benign-hit), giving clean baselines for flip measurement. Iris TARGET-03 was already a miss at N=1, which would confound flips.
Why these peers: similar arms length-matched (~21-37k); random arms token-matched (~20-28k peers) from iris+titanic. Slot seeds 42 (similar) / 43 (random); target slots evaluator-side only; leakage grep 0 on all 4 detector files.
Retired: superseded/N5-B1 + N5-B2 (iris similar-only, no random counterpart in budget). Kept on disk, NOT for report.
Limitation: random arm = other-task proxy, not embedding-ranked dissimilarity. Mix-variation question (2H/3B vs 3H/2B) dropped from this batch to hold mix fixed.
