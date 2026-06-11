"""Unit tests for the rock-breakability core (pure logic, runs anywhere)."""

import math

from sigtranslator.mining import (
    LASERS_BY_KEY,
    MODULES_BY_KEY,
    Turret,
    analyze,
    difficulty,
    parse_rock_stats,
    required_power,
    turret_verdict,
)


def _turret(laser_key, *module_keys):
    return Turret(LASERS_BY_KEY[laser_key], [MODULES_BY_KEY[k] for k in module_keys])


def test_parse_rock_stats():
    rs = parse_rock_stats("[CF] TITANIUM (ORE) MASS: 8600 RESISTANCE: 19% INSTABILITY: 14.73")
    assert rs is not None
    assert rs.mass == 8600
    assert rs.resistance == 19
    assert rs.instability == 14.73


def test_parse_rock_stats_comma_and_noise():
    rs = parse_rock_stats("MASS 1,570  RESISTANCE 19 %  INSTABILITY 14")
    assert rs.mass == 1570 and rs.resistance == 19


def test_parse_rock_stats_missing():
    assert parse_rock_stats("just some text") is None


def test_required_power_validated_points():
    # Helix built-in resistance -30 => factor 0.70: effRes = 0.19 * 0.70 = 0.133
    assert math.isclose(required_power(8600, 19, 0.70), 1983.85, rel_tol=1e-3)
    assert math.isclose(required_power(1570, 19, 0.70), 362.16, rel_tol=1e-3)


def test_required_power_impossible_at_full_resistance():
    assert required_power(1000, 100, 1.0) == float("inf")


def test_helix_breaks_8600_controllable():
    # validated in-game: broke, controllable (1020 <= 1984 <= 4080)
    rock = parse_rock_stats("MASS 8600 RESISTANCE 19%")
    v = turret_verdict(rock, _turret("helix_s2"))
    assert v.state == "ok"


def test_helix_overpowers_small_rock():
    # validated in-game: 1570/19% overshoots on bare Helix (min 1020 > req ~362)
    rock = parse_rock_stats("MASS 1570 RESISTANCE 19%")
    assert turret_verdict(rock, _turret("helix_s2")).state == "overpower"


def test_focus_hofstede_controls_small_rock():
    # same rock is controllable on a Focus-Hofstede (min ~303 < 362 < ~3032)
    rock = parse_rock_stats("MASS 1570 RESISTANCE 19%")
    hof = _turret("hofstede_s2", "focus_mk3", "focus_mk3")
    assert math.isclose(hof.power_max, 3360 * 0.9025, rel_tol=1e-6)
    assert math.isclose(hof.power_min, 336 * 0.9025, rel_tol=1e-6)
    assert turret_verdict(rock, hof).state == "ok"


def test_module_power_stacks_multiplicatively():
    # two Focus III at x0.95 each => 0.9025 multiplier (measured stacking rule)
    hof = _turret("hofstede_s2", "focus_mk3", "focus_mk3")
    assert math.isclose(hof.power_mult, 0.95 * 0.95, rel_tol=1e-9)


def test_resist_factors_stack_multiplicatively():
    # Mort13 ("The Break"): a 31% rock measured 13% with Klein+Rime — matches the
    # product (0.55 * 0.752 = 0.4136 -> 12.8%), refutes the additive sum (0.302 -> 9.4%).
    klein_rime = _turret("klein_s2", "rime")
    assert math.isclose(klein_rime.resist_factor, 0.55 * 0.752, rel_tol=1e-9)
    assert abs(31 * klein_rime.resist_factor - 13) < 1.0   # measured: 13
    assert abs(31 * 0.302 - 13) > 3.0                      # additive misses badly


def test_resistance_raising_gear_can_hit_unbreakable():
    # Arbor S2 (+25%) + Forel (+15.5%) => factor 1.44375: a 70% rock reaches
    # effective resistance >= 100% -> infinite requirement (never negative).
    arbor = _turret("arbor_s2", "forel")
    assert math.isclose(arbor.resist_factor, 1.25 * 1.155, rel_tol=1e-9)
    rock = parse_rock_stats("MASS 5000 RESISTANCE 70%")
    assert required_power(rock.mass, rock.resistance, arbor.resist_factor) == float("inf")
    assert turret_verdict(rock, arbor).state == "cant"
    p = analyze(rock, [arbor])
    assert p.kind == "impossible"
    assert p.stable_pct is None


def test_mixed_combo_pools_rock_side_factors():
    # Factors pool ON THE ROCK (multiple lasers share the rock's modifier state).
    # Helix (0.7) + Arbor (1.25) on 23000/40%: pooled factor 0.875 -> eff res 35%
    # -> req 4600/0.65 = 7077 > 6480 total -> NOT breakable. The old min-factor
    # rule borrowed the Helix's 0.7 alone and wrongly said yes (req 6389).
    rock = parse_rock_stats("MASS 23000 RESISTANCE 40%")
    p = analyze(rock, [_turret("helix_s2"), _turret("arbor_s2")])
    assert p.kind == "impossible"
    assert math.isclose(p.required, 23000 * 0.2 / (1 - 0.40 * 0.875), rel_tol=1e-9)


def test_matched_combo_pools_factors_too():
    # Two Hofstede-Focus heads on one rock: pooled factor 0.7 * 0.7 = 0.49
    # (each head's -30% applies to the shared rock state, not just its own beam).
    rock = parse_rock_stats("MASS 30000 RESISTANCE 40%")
    hof = lambda: _turret("hofstede_s2", "focus_mk3", "focus_mk3")  # noqa: E731
    p = analyze(rock, [hof(), hof()])
    assert math.isclose(p.required, 30000 * 0.2 / (1 - 0.40 * 0.49), rel_tol=1e-9)


def test_combo_lasers_not_all_red():
    # a heavy rock no single turret can crack, but the MOLE trio can: the combo
    # turrets must be green (@100%) / yellow (control), NOT red "can't break".
    rock = parse_rock_stats("MASS 40000 RESISTANCE 19%")
    turrets = [
        _turret("helix_s2"),
        _turret("hofstede_s2", "focus_mk3", "focus_mk3"),
        _turret("hofstede_s2", "focus_mk3", "focus_mk3"),
    ]
    p = analyze(rock, turrets)
    assert p.kind == "combo"
    roles = [r.role for r in p.roles]
    assert "@100%" in roles and "control" in roles
    assert all(r.role != "can't break" for r in p.roles)  # the bug we fixed
    # control is the lowest-floor laser (a Focus-Hofstede, not the Helix)
    ctrl = next(r for r in p.roles if r.role == "control")
    assert "Hofstede" in ctrl.name
    assert p.power >= p.required and p.headroom >= 0


def test_single_plan_marks_use_with_headroom():
    rock = parse_rock_stats("MASS 8600 RESISTANCE 19%")
    p = analyze(rock, [_turret("helix_s2")])
    assert p.kind == "single"
    assert p.roles[0].role == "use"
    assert p.roles[0].headroom is not None and p.roles[0].headroom > 0


def test_pulse_plan_when_only_overpowered():
    rock = parse_rock_stats("MASS 1570 RESISTANCE 19%")
    p = analyze(rock, [_turret("helix_s2")])
    assert p.kind == "pulse"
    assert "too much power" in p.roles[0].role


def test_impossible_all_red():
    rock = parse_rock_stats("MASS 9999 RESISTANCE 99%")
    p = analyze(rock, [_turret("hofstede_s2")])
    assert p.kind == "impossible"
    assert all(r.role == "can't break" for r in p.roles)


def test_plan_carries_min_power_and_headroom():
    rock = parse_rock_stats("MASS 8600 RESISTANCE 19%")
    p = analyze(rock, [_turret("helix_s2")])
    assert p.power_max == 4080 and p.power_min == 1020
    assert math.isclose(p.headroom, 4080 - p.required, rel_tol=1e-9)


def test_stable_pct_holdable():
    rock = parse_rock_stats("MASS 8600 RESISTANCE 19%")
    p = analyze(rock, [_turret("helix_s2")])  # req ~1984, max 4080 -> ~48.6%
    assert 45 <= p.stable_pct <= 52
    assert not p.stable_clamped


def test_stable_pct_clamped_to_floor_when_overpowered():
    rock = parse_rock_stats("MASS 1570 RESISTANCE 19%")
    p = analyze(rock, [_turret("helix_s2")])  # req 362 < min 1020 -> clamps to floor 25%
    assert p.stable_clamped
    assert math.isclose(p.stable_pct, 25.0, abs_tol=0.5)


def test_difficulty_pills():
    mole = [_turret("helix_s2"),
            _turret("hofstede_s2", "focus_mk3", "focus_mk3"),
            _turret("hofstede_s2", "focus_mk3", "focus_mk3")]
    assert difficulty(analyze(parse_rock_stats("MASS 4000 RESISTANCE 19%"), mole))[0] == "EASY"
    assert difficulty(analyze(parse_rock_stats("MASS 40000 RESISTANCE 19%"), mole))[0].startswith("NEEDS")
    assert difficulty(analyze(parse_rock_stats("MASS 90000 RESISTANCE 19%"), mole))[0] == "IMPOSSIBLE"
    # a lone overpowered laser -> OVERPOWERED
    assert difficulty(analyze(parse_rock_stats("MASS 1570 RESISTANCE 19%"), [_turret("helix_s2")]))[0] == "OVERPOWERED"
