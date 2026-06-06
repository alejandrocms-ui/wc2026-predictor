"""Structural tests for the tournament spec and fixture generation."""

from __future__ import annotations

from wc2026.tournament import load_spec


def test_spec_has_48_teams_12_groups():
    spec = load_spec()
    assert len(spec.groups) == 12
    assert len(spec.teams) == 48
    for label, members in spec.groups.items():
        assert len(members) == 4, label


def test_fixtures_round_robin_complete():
    spec = load_spec()
    assert len(spec.fixtures) == 72  # 6 per group x 12
    # Each team plays exactly 3 matches; each group has all 6 distinct pairings.
    from collections import Counter

    appearances: Counter[str] = Counter()
    for f in spec.fixtures:
        appearances[f.home] += 1
        appearances[f.away] += 1
    assert all(v == 3 for v in appearances.values()), appearances
    assert len(appearances) == 48

    for label in spec.groups:
        pairs = {
            frozenset((f.home, f.away)) for f in spec.fixtures if f.group == label
        }
        assert len(pairs) == 6  # C(4,2)


def test_every_team_in_exactly_one_group():
    spec = load_spec()
    seen = set()
    for members in spec.groups.values():
        for m in members:
            assert m not in seen
            seen.add(m)
    assert len(seen) == 48
