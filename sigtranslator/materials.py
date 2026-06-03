"""Baked-in radar-signature (RS) base values.

These are compiled into the binary on purpose: the game stores the same numbers
in ``Data.p4k`` (verified byte-for-byte against the StarCitizenWiki data dump),
but the on-disk DataForge format can change between patches. Baking the table in
makes the app immune to that and removes every external/file/network dependency.

The in-game scanner shows ``base_RS * node_count``. Each material's *base* is the
1-node signature of its deposit; the rarity *tier* caps how many nodes a cluster
can hold.

Values reflect the Star Citizen 4.x chart, confirmed against the live data dump.
If a patch ever shifts a value, edit this one file and cut a new release.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    name: str
    base: int       # 1-node radar signature
    tier: str       # rarity tier label
    max_nodes: int  # cluster cap for this tier


# Max nodes per rarity tier.
TIER_MAX_NODES = {
    "Legendary": 2,
    "Epic": 3,
    "Rare": 4,
    "Uncommon": 5,
    "Common": 6,
    "ROC Mineables": 7,
    "FPS Mineables": 10,
    "Salvage": 15,
}

# Overlay colors per tier, matching the scmdb signature chart.
TIER_COLORS = {
    "Legendary": "#f0a83c",      # orange
    "Epic": "#bf5bd6",           # magenta/purple
    "Rare": "#5b8def",           # blue
    "Uncommon": "#3fb96b",       # green
    "Common": "#b8bcc2",         # grey
    "ROC Mineables": "#2bbf8a",  # teal-green
    "FPS Mineables": "#6aa6e0",  # light blue
    "Salvage": "#c9b27c",        # tan
}

# The "true" rarity tiers (everything else is a special deposit type).
RARITY_TIERS = {"Legendary", "Epic", "Rare", "Uncommon", "Common"}


def _m(name: str, base: int, tier: str) -> Material:
    return Material(name=name, base=base, tier=tier, max_nodes=TIER_MAX_NODES[tier])


MATERIALS: list[Material] = [
    # Legendary (max x2)
    _m("Quantainium", 3170, "Legendary"),
    _m("Stileron", 3185, "Legendary"),
    _m("Savrilium", 3200, "Legendary"),
    # Epic (max x3)
    _m("Ouratite", 3370, "Epic"),
    _m("Riccite", 3385, "Epic"),
    _m("Lindinium", 3400, "Epic"),
    # Rare (max x4)
    _m("Beryl", 3540, "Rare"),
    _m("Taranite", 3555, "Rare"),
    _m("Borase", 3570, "Rare"),
    _m("Gold", 3585, "Rare"),
    _m("Bexalite", 3600, "Rare"),
    # Uncommon (max x5)
    _m("Laranite", 3825, "Uncommon"),
    _m("Aslarite", 3840, "Uncommon"),
    _m("Titanium", 3855, "Uncommon"),
    _m("Tungsten", 3870, "Uncommon"),
    _m("Agricium", 3885, "Uncommon"),
    _m("Torite", 3900, "Uncommon"),
    # Common (max x6)
    _m("Hephaestanite", 4180, "Common"),
    _m("Tin", 4195, "Common"),
    _m("Quartz", 4210, "Common"),
    _m("Corundum", 4225, "Common"),
    _m("Copper", 4240, "Common"),
    _m("Silicon", 4255, "Common"),
    _m("Iron", 4270, "Common"),
    _m("Aluminium", 4285, "Common"),
    _m("Ice", 4300, "Common"),
    # Special tiers (generic deposits)
    _m("ROC Mineable", 4000, "ROC Mineables"),
    _m("FPS Mineable", 3000, "FPS Mineables"),
    _m("Salvage", 2000, "Salvage"),
]
