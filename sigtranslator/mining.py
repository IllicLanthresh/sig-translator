"""Rock breakability: can a laser + module loadout fracture a scanned rock?

Pure logic + baked-in Star Citizen 4.8.1 mining-laser/module data. No I/O, fully
unit-testable. See mining-breakability-research.md for the derivation and the
in-game validations.

The model (community-reverse-engineered, validated in 4.8.1):
    RequiredPower = Mass * DecayPerMass / (1 - effResistance)      # DecayPerMass = 0.2
    effResistance = (Resistance% / 100) * resistFactor             # clamped to [0, 1)
    resistFactor  = (1 + laser.resist/100) * prod(1 + module.resist/100)
    effPower(max|min) = laser.power(max|min) * prod(1 + module power deltas)
Modifier stacking is MULTIPLICATIVE everywhere — within a loadout (laser x modules
x gadgets, measured by Mort13 "The Break" 2026: a 31% rock with stacked resistance
modifiers matches the product exactly where the additive sum fails) AND across
heads on the same rock (the modifiers are rock-side state: multiple lasers on one
rock share the same accumulated modifiers and one charge bar — observed in-game).
Resistance enters the threshold LINEARLY — the datamined ResistanceCurveFactor
(0.6) does not appear in powerbreak measurements (fitted exponent ~1.0 over his
63-rock dataset), so it is not part of this gate.
A single turret:
    power_max < required        -> can't break
    power_min > required        -> too much power (overshoots; must pulse)
    min <= required <= max      -> controllable
Instability is NOT part of this (it governs overcharge controllability only;
confirmed by Mort13's instability sweep). Distance matters but is not modeled:
verdicts assume you are within the laser's optimal range.
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
    power: float = 0.0    # power delta as a fraction (+0.5 => x1.5); stacks multiplicatively
    resist: float = 0.0   # resistance modifier (%); stacks multiplicatively


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
        # multiplicative across modules (the measured stacking rule for this game's
        # mining modifiers; identical to additive when <= 1 power module is fitted)
        mult = 1.0
        for m in self.modules:
            mult *= 1 + m.power
        return mult

    @property
    def power_max(self) -> float:
        return self.laser.power_max * self.power_mult

    @property
    def power_min(self) -> float:
        return self.laser.power_min * self.power_mult

    @property
    def resist_factor(self) -> float:
        """Combined resistance multiplier: laser x modules (measured: multiplicative).
        <1 reduces the rock's effective resistance, >1 raises it."""
        f = 1 + self.laser.resist_mod / 100.0
        for m in self.modules:
            f *= 1 + m.resist / 100.0
        return f


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


def required_power(mass: float, resistance_pct: float, resist_factor: float = 1.0) -> float:
    """Minimum laser power to fracture. inf == impossible (effective resistance >= 100%).

    resist_factor is the combined multiplier from the loadout (Turret.resist_factor),
    e.g. 0.7 for a bare Helix, 0.55 * 0.752 for Klein + Rime.
    """
    eff_res = (resistance_pct / 100.0) * resist_factor
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
    req = required_power(rock.mass, rock.resistance, t.resist_factor)
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
    power_max: float     # operative available power (full throttle)
    power_min: float     # operative throttle floor
    roles: list[TurretRole]

    @property
    def power(self) -> float:  # back-compat
        return self.power_max

    @property
    def headroom(self) -> float:
        return self.power_max - self.required

    @property
    def stable_pct(self) -> float | None:
        """Throttle (% of max power) where the charge holds steady — the equilibrium
        where input == decay, i.e. RequiredPower as a fraction of max, clamped to the
        throttle floor. None if it can't break (required is infinite)."""
        if self.power_max <= 0 or self.required == float("inf"):
            return None
        floor = self.power_min / self.power_max
        return max(floor, min(1.0, self.required / self.power_max)) * 100

    @property
    def stable_clamped(self) -> bool:
        """True when stable sits below the throttle floor (overshoots even at minimum)."""
        return self.power_max > 0 and self.required < self.power_min


def combo_required(rock: RockStats, turrets: list[Turret]) -> float:
    """Combined power needed for a set of heads working the same rock.

    The modifiers are ROCK-SIDE state: every laser on the rock applies its factor
    to the rock itself, shared by all beams (observed in-game: two ships on one
    rock both see the same accumulated modifiers and one shared charge bar; same
    rule as Mort13's calculator). So the pool is the product of every
    participating head's factor, and the threshold uses the combined power:
        required = mass * 0.2 / (1 - R * prod(f_i))
    Exactly equals required_power for a single turret. inf == can't rise.
    """
    if not turrets:
        return float("inf")
    factor = 1.0
    for t in turrets:
        factor *= t.resist_factor
    return required_power(rock.mass, rock.resistance, factor)


def _best_subset_indices(rock: RockStats, turrets: list[Turret], min_size: int):
    """Smallest subset (>= min_size) whose combined max power breaks the rock.

    Uses the pooled rock-side modifier rule (see combo_required).
    Returns (indices, required, total) or None.
    """
    from itertools import combinations

    idxs = list(range(len(turrets)))
    for size in range(max(1, min_size), len(turrets) + 1):
        best = None
        for subset in combinations(idxs, size):
            sub = [turrets[i] for i in subset]
            req = combo_required(rock, sub)
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
        t = verdicts[best].turret
        return Plan(rock, "single", verdicts[best].required, t.power_max, t.power_min, roles)

    if over:  # breaks alone but overshoots -> pulse the weakest one
        for i, v in enumerate(verdicts):
            if v.state == "overpower":
                roles[i] = TurretRole(v.name, v.turret.power_max, "too much power (pulse)", AMBER)
            else:
                roles[i] = TurretRole(v.name, v.turret.power_max, "not needed", GREY)
        weakest = min(over, key=lambda i: verdicts[i].turret.power_min)
        t = verdicts[weakest].turret
        return Plan(rock, "pulse", verdicts[weakest].required, t.power_max, t.power_min, roles)

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
        # throttle floor of the combo: strong lasers pinned at max + control at its min
        band_min = (total - turrets[ctrl].power_max) + turrets[ctrl].power_min
        return Plan(rock, "combo", req, total, band_min, roles)

    for i, v in enumerate(verdicts):  # nothing, even combined, can break it
        roles[i] = TurretRole(v.name, v.turret.power_max, "can't break", RED)
    req = combo_required(rock, turrets) if turrets else float("inf")
    return Plan(rock, "impossible", req, sum(t.power_max for t in turrets),
                sum(t.power_min for t in turrets), roles)


def difficulty(plan: "Plan") -> tuple[str, str]:
    """SC-style verdict pill (label, color) derived from the plan."""
    if plan.kind == "impossible":
        return ("IMPOSSIBLE", RED)
    if plan.kind == "pulse":
        return ("OVERPOWERED", AMBER)
    if plan.kind == "combo":
        n = sum(1 for r in plan.roles if r.role in ("@100%", "control"))
        return (f"NEEDS {n}", YELLOW)
    ratio = plan.required / plan.power_max if plan.power_max else 1.0  # single
    if ratio < 0.5:
        return ("EASY", GREEN)
    if ratio < 0.8:
        return ("MODERATE", GREEN)
    return ("TIGHT", AMBER)


def eval_config(rock: RockStats, turrets: list[Turret]) -> Plan:
    """Evaluate ONE user-chosen config (the manual path — no optimizer).

    `turrets` is exactly the heads the user has firing, each already carrying the
    modules currently active on it. Power adds across heads; resistance factors pool
    multiplicatively on the rock (combo_required). Returns a Plan whose gauge/pill
    the overlay renders as-is. Each head gets a simple on-state role (no use/control).
    """
    if not turrets:
        return Plan(rock, "impossible", float("inf"), 0.0, 0.0, [])
    req = combo_required(rock, turrets)
    pmax = sum(t.power_max for t in turrets)
    pmin = sum(t.power_min for t in turrets)
    if pmax < req:
        kind, color = "impossible", RED
    elif pmin > req:
        kind, color = "pulse", AMBER
    else:
        # manual mode: no "needs N combo" concept — any breakable pick reads by
        # headroom (EASY/MODERATE/TIGHT), so keep kind "single" regardless of head count.
        kind, color = "single", GREEN
    roles = [TurretRole(t.laser.name, t.power_max, "on", color) for t in turrets]
    return Plan(rock, kind, req, pmax, pmin, roles)


# Back-compat alias for older callers/tests.
analyze = plan
