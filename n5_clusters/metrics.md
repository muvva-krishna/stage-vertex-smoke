# N=5 metrics spec (minimal, for the later run)

Canonical set: N5-A1, N5-A1R, N5-A2, N5-A2R (2 iot targets x similar/random arms, mix fixed at 2H/3B).

PRIMARY (similarity effect, the central question):
- Per-target flip: TARGET-02 similar (A1) vs random (A1R); TARGET-07 similar (A2) vs random (A2R). Same target, same mix, same model — only peers differ.
- Per-arm accuracy vs stored labels (2 designated targets each): similar arm (A1+A2) vs random arm (A1R+A2R).

SECONDARY:
- N=1→N=5 flips: TARGET-02 N=1 vs A1 vs A1R; TARGET-07 N=1 vs A2 vs A2R.
- Designated-target precision/recall/F1/FPR (hack=positive, n=2 targets — descriptive only).
- Full 20-slot confusion as context.

Same model, same settings, one batch. Stored labels are references only. n=2 targets → NO significance claim; report flips + effect direction as a pilot signal. Random arm is an other-task proxy, not a verified maximally-dissimilar ranking.
