"""Translate a scanned signature number into (material, node count, confidence).

The scanner reports ``base_RS * node_count``. To invert it we try every material:
for material with base ``B`` the node count is ``n = round(S / B)``. The residual
``|S - n*B|`` measures how cleanly ``S`` divides by ``B`` -- the smaller it is, the
better the fit. Because bases are spaced ~15 apart and node counts are small, the
true material almost always has a near-zero residual while wrong guesses don't.

Confidence is ``1 - residual_fraction`` where ``residual_fraction = |S - n*B| / B``,
clamped to [0, 1]. A perfect divide gives 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

from .materials import MATERIALS, Material


@dataclass(frozen=True)
class Match:
    material: Material
    count: int
    confidence: float  # 0..1, 1.0 == exact multiple
    residual: int      # |scanned - count*base|

    @property
    def label(self) -> str:
        """Short overlay text, e.g. 'Stileron x2'."""
        return f"{self.material.name} x{self.count}"


def _evaluate(material: Material, scanned: int) -> Match | None:
    if scanned <= 0:
        return None
    count = round(scanned / material.base)
    if count < 1 or count > material.max_nodes:
        return None
    residual = abs(scanned - count * material.base)
    confidence = max(0.0, 1.0 - residual / material.base)
    return Match(material=material, count=count, confidence=confidence, residual=residual)


def translate(scanned: int) -> Match | None:
    """Best material match for a scanned signature, or None if nothing plausible."""
    best: Match | None = None
    for material in MATERIALS:
        m = _evaluate(material, scanned)
        if m is None:
            continue
        if best is None or m.residual < best.residual:
            best = m
    return best


def translate_all(scanned: int, limit: int = 3) -> list[Match]:
    """Top candidate matches, best (lowest residual) first."""
    matches = [m for material in MATERIALS if (m := _evaluate(material, scanned))]
    matches.sort(key=lambda m: m.residual)
    return matches[:limit]


def translate_matches(scanned: int, min_confidence: float = 0.985) -> list[Match]:
    """All equally-best matches for a signature, larger base first.

    Returns only readings tied at the *best* residual, so a clean number yields the
    single right material -- neighboring ores (bases just 15 apart) are NOT included
    as near-misses. The special tiers, however, share *exact* multiples
    (6000 = FPS x2 = Salvage x3), so those genuinely-ambiguous readings all come back.
    Empty if nothing matches confidently.
    """
    evaluated = [m for material in MATERIALS if (m := _evaluate(material, scanned))]
    if not evaluated:
        return []
    best = min(evaluated, key=lambda m: m.residual)
    if best.confidence < min_confidence:
        return []
    tied = [m for m in evaluated if m.residual == best.residual]
    tied.sort(key=lambda m: -m.material.base)
    return tied
