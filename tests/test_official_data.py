"""Tests for the verified official 2026 fixtures, venues, host advantage, and R32 bracket."""

from __future__ import annotations

from wc2026.config import get_settings
from wc2026.features import build_context
from wc2026.sim.bracket import load_r32_ties
from wc2026.tournament import load_spec


def test_official_fixtures_loaded_and_consistent():
    spec = load_spec()
    fixtures = spec.fixtures
    assert len(fixtures) == 72
    # Each fixture's two teams share a group; venue exists; date is in the group-stage window.
    for f in fixtures:
        assert spec.group_of(f.home) == spec.group_of(f.away) == f.group
        assert f.venue_city in spec.venues, f.venue_city
        assert f.date.startswith("2026-06"), f.date
        assert f.matchday in (1, 2, 3)


def test_every_team_plays_three_official_matches():
    spec = load_spec()
    from collections import Counter

    c: Counter[str] = Counter()
    for f in spec.fixtures:
        c[f.home] += 1
        c[f.away] += 1
    assert len(c) == 48
    assert all(v == 3 for v in c.values())


def test_host_advantage_applied_in_own_country():
    spec = load_spec()
    # Mexico v South Africa is played in Mexico City (MEX) -> Mexico gets the host boost.
    mex = next(f for f in spec.fixtures if f.home == "Mexico" and f.matchday == 1)
    ctx = build_context(mex, spec)
    assert ctx.home_logit_adj > 0  # host boost to Mexico
    # A host can be the nominal AWAY team in its own country and still get the boost:
    # Switzerland v Canada (match 49) is in Vancouver (CAN).
    swi_can = next(
        f for f in spec.fixtures if f.home == "Switzerland" and f.away == "Canada"
    )
    ctx2 = build_context(swi_can, spec)
    assert ctx2.away_logit_adj > 0  # Canada (away) gets the host boost
    assert ctx2.home_logit_adj == 0


def test_non_host_neutral_match_has_no_host_boost():
    spec = load_spec()
    # Brazil v Morocco (no host nation involved) -> no host boost either way.
    bra = next(f for f in spec.fixtures if f.home == "Brazil" and f.away == "Morocco")
    ctx = build_context(bra, spec)
    assert ctx.home_logit_adj == 0 and ctx.away_logit_adj == 0


def test_r32_bracket_structure():
    ties = load_r32_ties(get_settings().seed_dir)
    assert ties is not None and len(ties) == 16
    third_slots = sum(1 for t in ties if "3rd" in t["a"] or "3rd" in t["b"])
    assert third_slots == 8  # exactly 8 best-third slots in the bracket
    # Slot tokens are well-formed: winner/runner-up reference a real group, or a 3rd pool.
    for t in ties:
        for slot in (t["a"], t["b"]):
            if slot.startswith("3rd"):
                assert slot.startswith("3rd:")
            else:
                assert slot[0] in "12" and slot[1] in "ABCDEFGHIJKL", slot
