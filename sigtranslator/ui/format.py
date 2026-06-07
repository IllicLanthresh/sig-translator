"""Pure (text, color) line builders for the signature and mining readouts.

Reused by both the in-game overlays and the GUI's live panel so the two never drift.
No Qt here.
"""

from __future__ import annotations

from ..materials import RARITY_TIERS, TIER_COLORS

_STATE_COLOR = {"ok": "#33dd66", "overpower": "#ffcc44", "cant": "#ff5555"}


def _fnum(x) -> str:
    return "∞" if x == float("inf") else f"{int(round(x)):,}"


def sig_lines(matches, number, config) -> list[tuple[str, str]]:
    """Signature readout. Empty list => nothing to show."""
    if not number or not matches:
        return []
    disabled = set(config.disabled_materials)
    active = [m for m in matches if m.material.name not in disabled]
    lines = [(f"[ {int(number):,} ]", config.accent_color)]
    for m in active:
        tier = m.material.tier
        suffix = f"  ({tier})" if (config.show_rarity and tier in RARITY_TIERS) else ""
        lines.append((f"{m.material.name} ×{m.count}{suffix}", TIER_COLORS.get(tier, "#ffffff")))
    return lines  # only the bracket remains if every match is disabled -> "sig only"


def mining_lines(plan, config) -> list[tuple[str, str]]:
    """Breakability readout for a Plan. Empty list => nothing to show."""
    if plan is None:
        return []
    rock = plan.rock
    f = _fnum
    lines = [(f"[ {f(rock.mass)} m · {rock.resistance:.0f}% ]", config.accent_color)]
    if plan.kind == "impossible":
        stats = "impossible — resistance too high"
    elif plan.kind == "combo":
        stats = f"req {f(plan.required)} · combined {f(plan.power)} · +{f(plan.headroom)}"
    elif plan.kind == "pulse":
        stats = f"req {f(plan.required)} · power {f(plan.power)} · overpowered"
    else:
        stats = f"req {f(plan.required)} · power {f(plan.power)} · +{f(plan.headroom)}"
    lines.append((stats, "#cfd3d6"))
    for r in plan.roles:
        txt = f"{r.name}  {f(r.power_max)}  {r.role}"
        if r.headroom is not None:
            txt += f"  (+{f(r.headroom)})"
        lines.append((txt, r.color))
    return lines
