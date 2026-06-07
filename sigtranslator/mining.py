"""Rock breakability: can a laser + module loadout fracture a scanned rock?

Pure logic + baked-in Star Citizen 4.8.1 mining-laser/module data. No I/O, fully
unit-testable. See mining-breakability-research.md for the derivation and the
in-game validations.

The model (community-reverse-engineered, validated in 4.8.1):
    RequiredPower = Mass * DecayPerMass / (1 - effResistance)      # DecayPerMass = 0.2
    effResistance = (Resistance% / 100) * (1 + resistMod/100)      # clamped to [0, 1)
    effPower(max|min) = laser.power(max|min) * (1 + sum(module power deltas))   # additive
    resistMod = laser built-in + sum(module resistance mods)                    # additive
A single turret:
    power_max < required        -> can't break
    power_min > required        -> too much power (overshoots; must pulse)
    min <= required <= max      -> controllable
Instability is NOT part of this (it governs overcharge controllability only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DECAY_PER_MASS = 0.2  # uniform on all 4.8.1 rocks; the community "÷5"


# --------------------------------------------------------------------------- data
@dataclass(frozen=True)
class Laser:
    key: str
    name: str
    power_max: float
    power_min: float
    slots: int
    resist_mod: float = 0.0  # built-in resistance modifier (%)


@dataclass(frozen=True)
class Module:
    key: str
    name: str
    kind: str          # "Active" | "Passive"
    power: float = 0.0    # DamageMultiplierChange (additive fraction, e.g. +0.5 / -0.15)
    resist: float = 0.0   # resistance modifier (%)


# Mining lasers (4.8.1). power_max = PowerTransfer, power_min = MinPowerTransfer.
LASERS: list[Laser] = [
    Laser("helix_s2", "Helix S2", 4080, 1020, 3, -30),
    Laser("lancet_s2", "Lancet S2", 3600, 900, 2, 0),
    Laser("klein_s2", "Klein S2", 3600, 720, 1, -45),
    Laser("hofstede_s2", "Hofstede S2", 3360, 336, 2, -30),
    Laser("impact_s2", "Impact S2", 3360, 840, 3, 10),
    Laser("golem_s1", "Golem S1", 3150, 630, 2, 25),
    Laser("helix_s1", "Helix S1", 3150, 630, 2, -30),
    Laser("lancet_s1", "Lancet S1", 2520, 504, 1, 0),
    Laser("klein_s1", "Klein S1", 2520, 378, 1, -45),
    Laser("arbor_s2", "Arbor S2", 2400, 120, 2, 25),
    Laser("hofstede_s1", "Hofstede S1", 2100, 105, 1, -30),
    Laser("impact_s1", "Impact S1", 2100, 420, 2, 10),
    Laser("arbor_s1", "Arbor S1", 1890, 94.5, 1, 25),
    Laser("mpuv_arm", "MPUV Arm", 1850, 1.85, 1, 0),
]

# Mining modules (4.8.1). Only `power` and `resist` affect breakability; the rest of a
# module's effects (window/overcharge/yield) are out of scope for the break verdict.
MODULES: list[Module] = [
    # active
    Module("forel", "Forel", "Active", 0.5, 15.5),
    Module("surge", "Surge", "Active", 0.5, -15.5),
    Module("brandt", "Brandt", "Active", 0.35, 15.5),
    Module("stampede", "Stampede", "Active", 0.35, 0),
    Module("optimum", "Optimum", "Active", -0.15, 0),
    Module("rime", "Rime", "Active", -0.15, -24.8),
    Module("lifeline", "Lifeline", "Active", 0, -15.5),
    Module("torpid", "Torpid", "Active", 0, 0),
    # passive
    Module("focus_mk1", "Focus mk1", "Passive", -0.15, 0),
    Module("focus_mk2", "Focus mk2", "Passive", -0.10, 0),
    Module("focus_mk3", "Focus mk3", "Passive", -0.05, 0),
    Module("rieger_mk1", "Rieger mk1", "Passive", 0.15, 0),
    Module("rieger_mk2", "Rieger mk2", "Passive", 0.20, 0),
    Module("rieger_mk3", "Rieger mk3", "Passive", 0.25, 0),
    Module("vaux_mk1", "Vaux mk1", "Passive", 0.15, 0),
    Module("vaux_mk2", "Vaux mk2", "Passive", 0.20, 0),
    Module("vaux_mk3", "Vaux mk3", "Passive", 0.25, 0),
    Module("fltr_mk1", "Filter mk1", "Passive", -0.15, 0),
    Module("fltr_mk2", "Filter mk2", "Passive", -0.10, 0),
    Module("fltr_mk3", "Filter mk3", "Passive", -0.05, 0),
    Module("xtr_mk1", "Extraction mk1", "Passive", -0.15, 0),
    Module("xtr_mk2", "Extraction mk2", "Passive", -0.10, 0),
    Module("xtr_mk3", "Extraction mk3", "Passive", -0.05, 0),
    Module("torrent_mk1", "Torrent mk1", "Passive", 0, 0),
    Module("torrent_mk2", "Torrent mk2", "Passive", 0, 0),
    Module("torrent_mk3", "Torrent mk3", "Passive", 0, 0),
]

LASERS_BY_KEY = {l.key: l for l in LASERS}
MODULES_BY_KEY = {m.key: m for m in MODULES}


# ------------------------------------------------------------------------ scanning
@dataclass(frozen=True)
class RockStats:
    mass: float
    resistance: float          # percent, e.g. 19.0
    instability: float | None = None


_RE_MASS = re.compile(r"MASS\D{0,4}([\d.,]+)", re.I)
_RE_RES = re.compile(r"RESIST\w*\D{0,4}([\d.,]+)\s*%?", re.I)
_RE_INST = re.compile(r"INSTAB\w*\D{0,4}([\d.,]+)", re.I)


def _num(s: str) -> float:
    return float(s.replace(",", "").replace(" ", ""))


def parse_rock_stats(text: str) -> RockStats | None:
    """Parse a scan-panel OCR blob into Mass / Resistance / Instability.

    Tolerant of OCR noise: looks for the labels and the first number after each.
    Returns None if Mass or Resistance can't be found.
    """
    m = _RE_MASS.search(text)
    r = _RE_RES.search(text)
    if not m or not r:
        return None
    try:
        mass = _num(m.group(1))
        resistance = _num(r.group(1))
    except ValueError:
        return None
    inst = None
    im = _RE_INST.search(text)
    if im:
        try:
            inst = _num(im.group(1))
        except ValueError:
            inst = None
    return RockStats(mass=mass, resistance=resistance, instability=inst)


# --------------------------------------------------------------------------- math
@dataclass
class Turret:
    laser: Laser
    modules: list[Module] = field(default_factory=list)

    @property
    def power_mult(self) -> float:
        return 1 + sum(m.power for m in self.modules)

    @property
    def power_max(self) -> float:
        return self.laser.power_max * self.power_mult

    @property
    def power_min(self) -> float:
        return self.laser.power_min * self.power_mult

    @property
    def resist_mod(self) -> float:
        return self.laser.resist_mod + sum(m.resist for m in self.modules)


def turrets_from_loadout(loadout: list) -> list["Turret"]:
    """Build Turret objects from a config loadout (list of {laser, modules})."""
    turrets = []
    for entry in loadout or []:
        laser = LASERS_BY_KEY.get((entry or {}).get("laser"))
        if not laser:
            continue
        mods = [MODULES_BY_KEY[k] for k in entry.get("modules", []) if k in MODULES_BY_KEY]
        turrets.append(Turret(laser, mods))
    return turrets


def required_power(mass: float, resistance_pct: float, resist_mod: float) -> float:
    """Minimum laser power to fracture. inf == impossible (effective resistance >= 100%)."""
    eff_res = (resistance_pct / 100.0) * (1 + resist_mod / 100.0)
    eff_res = max(0.0, eff_res)
    if eff_res >= 1.0:
        return float("inf")
    return mass * DECAY_PER_MASS / (1 - eff_res)


@dataclass
class TurretVerdict:
    turret: Turret
    required: float
    state: str  # "ok" | "overpower" | "cant"

    @property
    def name(self) -> str:
        return self.turret.laser.name


def turret_verdict(rock: RockStats, t: Turret) -> TurretVerdict:
    req = required_power(rock.mass, rock.resistance, t.resist_mod)
    if t.power_max < req:
        state = "cant"
    elif t.power_min > req:
        state = "overpower"
    else:
        state = "ok"
    return TurretVerdict(turret=t, required=req, state=state)


# Role colors (kept with the logic so the overlay stays a dumb renderer).
GREEN = "#33dd66"   # use / part of the breaking combo
YELLOW = "#ffe24d"  # the control laser in a combo
AMBER = "#ffcc44"   # too much power (overshoots, must pulse)
GREY = "#9aa0a6"    # not needed for the plan
RED = "#ff5555"     # can't break, even combined


@dataclass
class TurretRole:
    name: str
    power_max: float
    role: str         # short word for the line ("use", "@100%", "control", ...)
    color: str
    headroom: float | None = None  # power - required, for "use" lines


@dataclass
class Plan:
    rock: RockStats
    kind: str            # "single" | "pulse" | "combo" | "impossible"
    required: float      # operative requirement for the chosen plan
    power: float         # operative available power for the chosen plan
    roles: list[TurretRole]

    @property
    def headroom(self) -> float:
        return self.power - self.required


def _best_subset_indices(rock: RockStats, turrets: list[Turret], min_size: int):
    """Smallest subset (>= min_size) whose combined max power breaks the rock.

    Conservative cross-laser resistance: use the single best (most negative) resistance
    reduction in the subset, not multiplicative stacking (the pre-4.7 uncertain bit).
    Returns (indices, required, total) or None.
    """
    from itertools import combinations

    idxs = list(range(len(turrets)))
    for size in range(max(1, min_size), len(turrets) + 1):
        best = None
        for subset in combinations(idxs, size):
            sub = [turrets[i] for i in subset]
            req = required_power(rock.mass, rock.resistance, min(t.resist_mod for t in sub))
            total = sum(t.power_max for t in sub)
            if total < req:
                continue
            margin = total - req
            if best is None or margin > best[2]:
                best = (list(subset), req, margin, total)
        if best is not None:
            return best[0], best[1], best[3]
    return None


def plan(rock: RockStats, turrets: list[Turret]) -> Plan:
    """Assign each turret a role (and color) for breaking this rock.

    Order of preference: a controllable single, else a single that breaks but
    overpowers (pulse), else the smallest multi-laser combo (pin the strong lasers,
    use the lowest-floor one as control), else impossible.
    """
    verdicts = [turret_verdict(rock, t) for t in turrets]
    roles = [TurretRole(v.name, v.turret.power_max, "", GREY) for v in verdicts]

    ok = [i for i, v in enumerate(verdicts) if v.state == "ok"]
    over = [i for i, v in enumerate(verdicts) if v.state == "overpower"]

    if ok:  # at least one turret breaks it controllably on its own
        for i, v in enumerate(verdicts):
            if v.state == "ok":
                roles[i] = TurretRole(v.name, v.turret.power_max, "use", GREEN,
                                      v.turret.power_max - v.required)
            elif v.state == "overpower":
                roles[i] = TurretRole(v.name, v.turret.power_max, "too much power", AMBER)
            else:
                roles[i] = TurretRole(v.name, v.turret.power_max, "not needed", GREY)
        best = max(ok, key=lambda i: verdicts[i].turret.power_max - verdicts[i].required)
        return Plan(rock, "single", verdicts[best].required, verdicts[best].turret.power_max, roles)

    if over:  # breaks alone but overshoots -> pulse the weakest one
        for i, v in enumerate(verdicts):
            if v.state == "overpower":
                roles[i] = TurretRole(v.name, v.turret.power_max, "too much power (pulse)", AMBER)
            else:
                roles[i] = TurretRole(v.name, v.turret.power_max, "not needed", GREY)
        weakest = min(over, key=lambda i: verdicts[i].turret.power_min)
        return Plan(rock, "pulse", verdicts[weakest].required, verdicts[weakest].turret.power_max, roles)

    combo = _best_subset_indices(rock, turrets, min_size=2)
    if combo:
        indices, req, total = combo
        ctrl = min(indices, key=lambda i: turrets[i].power_min)  # lowest floor = control
        for i in range(len(turrets)):
            if i == ctrl:
                roles[i] = TurretRole(verdicts[i].name, turrets[i].power_max, "control", YELLOW)
            elif i in indices:
                roles[i] = TurretRole(verdicts[i].name, turrets[i].power_max, "@100%", GREEN)
            else:
                roles[i] = TurretRole(verdicts[i].name, turrets[i].power_max, "spare", GREY)
        return Plan(rock, "combo", req, total, roles)

    for i, v in enumerate(verdicts):  # nothing, even combined, can break it
        roles[i] = TurretRole(v.name, v.turret.power_max, "can't break", RED)
    return Plan(rock, "impossible", float("inf"), sum(t.power_max for t in turrets), roles)


# Back-compat alias for older callers/tests.
analyze = plan
