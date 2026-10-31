"""Deterministic evidence-condition loader.

Five pilot conditions:
  1. symptom_only   -> symptom.md only
  2. repro_log      -> symptom.md + repro_log.md
  3. state_snapshot -> symptom.md + state_snapshot.md
  4. code_note      -> symptom.md + code_note.md
  5. combined       -> symptom.md + repro_log.md + state_snapshot.md + code_note.md

The loader exposes only the selected artifacts, counts evidence tokens with a
documented deterministic approximation (whitespace-separated words), and never
pads shorter conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CONDITIONS = (
    "symptom_only",
    "repro_log",
    "state_snapshot",
    "code_note",
    "combined",
)

CONDITION_FILES: dict[str, tuple[str, ...]] = {
    "symptom_only": ("symptom.md",),
    "repro_log": ("symptom.md", "repro_log.md"),
    "state_snapshot": ("symptom.md", "state_snapshot.md"),
    "code_note": ("symptom.md", "code_note.md"),
    "combined": ("symptom.md", "repro_log.md", "state_snapshot.md", "code_note.md"),
}


def count_tokens(text: str) -> int:
    """Deterministic evidence-token approximation: whitespace-separated words."""
    return len(text.split())


@dataclass
class EvidencePacket:
    condition: str
    artifacts: dict[str, str]  # filename -> text
    evidence_tokens: int
    token_counts: dict[str, int]
    budget: int

    def opened(self, filename: str) -> bool:
        return filename in self.artifacts


def load_condition(
    evidence_dir: str | Path, condition: str, budget: int
) -> EvidencePacket:
    if condition not in CONDITION_FILES:
        raise ValueError(f"unknown condition: {condition!r}")
    evidence_dir = Path(evidence_dir)
    artifacts: dict[str, str] = {}
    token_counts: dict[str, int] = {}
    for name in CONDITION_FILES[condition]:
        path = evidence_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing evidence artifact: {path}")
        text = path.read_text(encoding="utf-8")
        artifacts[name] = text
        token_counts[name] = count_tokens(text)
    total = sum(token_counts.values())
    if total > budget:
        raise ValueError(
            f"evidence budget exceeded for condition {condition!r}: "
            f"{total} tokens > budget {budget}"
        )
    return EvidencePacket(
        condition=condition,
        artifacts=artifacts,
        evidence_tokens=total,
        token_counts=token_counts,
        budget=budget,
    )
