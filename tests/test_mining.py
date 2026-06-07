"""Unit tests for the rock-breakability core (pure logic, runs anywhere)."""

import math

from sigtranslator.mining import (
    LASERS_BY_KEY,
    MODULES_BY_KEY,
    Turret,
    analyze,
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
    # Helix built-in resistance -30: effRes = 0.19 * 0.70 = 0.133
    assert math.isclose(required_power(8600, 19, -30), 1983.85, rel_tol=1e-3)
    assert math.isclose(required_power(1570, 19, -30), 362.16, rel_tol=1e-3)


def test_required_power_impossible_at_full_resistance():
    assert required_power(1000, 100, 0) == float("inf")


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
    # same rock is controllable on a Focus-Hofstede (min 302 < 362 < 3024)
    rock = parse_rock_stats("MASS 1570 RESISTANCE 19%")
    hof = _turret("hofstede_s2", "focus_mk3", "focus_mk3")
    assert math.isclose(hof.power_max, 3024, rel_tol=1e-6)
    assert math.isclose(hof.power_min, 302.4, rel_tol=1e-6)
    assert turret_verdict(rock, hof).state == "ok"


def test_module_power_stacks_additively():
    # two Focus III at -5% each => 0.90 multiplier
    hof = _turret("hofstede_s2", "focus_mk3", "focus_mk3")
    assert math.isclose(hof.power_mult, 0.90, rel_tol=1e-9)


def test_min_combo_needs_multiple_lasers():
    # a heavy rock no single turret can crack, but the MOLE trio can
    rock = parse_rock_stats("MASS 40000 RESISTANCE 19%")
    turrets = [
        _turret("helix_s2"),
        _turret("hofstede_s2", "focus_mk3", "focus_mk3"),
        _turret("hofstede_s2", "focus_mk3", "focus_mk3"),
    ]
    res = analyze(rock, turrets)
    assert all(v.state == "cant" for v in res.verdicts)  # none solo
    assert res.combo is not None
    assert len(res.combo.turrets) >= 2
    # control laser is the lowest-floor one (a Focus-Hofstede, not the Helix)
    ctrl = res.combo.turrets[res.combo.control_index]
    assert ctrl.laser.key == "hofstede_s2"


def test_recommendation_strings():
    rock = parse_rock_stats("MASS 8600 RESISTANCE 19%")
    res = analyze(rock, [_turret("helix_s2")])
    assert "Helix" in res.recommendation
