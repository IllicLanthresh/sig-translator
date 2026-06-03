"""Unit tests for the pure translation logic (runs anywhere, no Windows deps)."""

from sigtranslator.translate import translate, translate_all


def test_readme_examples():
    assert translate(3185).label == "Stileron x1"
    assert translate(6370).label == "Stileron x2"
    assert translate(19125).label == "Laranite x5"


def test_single_node_bases():
    assert translate(3170).label == "Quantainium x1"
    assert translate(4300).label == "Ice x1"
    assert translate(3600).label == "Bexalite x1"


def test_exact_multiples_are_full_confidence():
    m = translate(3185 * 2)
    assert m is not None
    assert m.count == 2
    assert m.confidence == 1.0
    assert m.residual == 0


def test_node_count_capped_by_tier():
    # Legendary caps at 2; 3x Stileron should NOT come back as Stileron x3.
    m = translate(3185 * 3)
    assert m is None or m.material.name != "Stileron" or m.count <= 2


def test_none_for_nonsense():
    assert translate(0) is None
    assert translate(-5) is None
    assert translate(50) is None  # below the smallest base, no plausible match


def test_translate_all_orders_by_residual():
    matches = translate_all(3185)
    assert matches[0].material.name == "Stileron"
    assert all(
        matches[i].residual <= matches[i + 1].residual for i in range(len(matches) - 1)
    )


def test_off_by_small_amount_still_matches():
    # OCR-exact HUD numbers are clean, but tolerate a tiny wobble.
    m = translate(3186)
    assert m is not None
    assert m.material.name == "Stileron"
    assert m.confidence < 1.0
