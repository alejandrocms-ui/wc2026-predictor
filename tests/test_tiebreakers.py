"""Known-case unit tests for the FIFA tiebreaker chain and third-place ranking.

Each test encodes a hand-computed scenario so a regression is unambiguous.
"""

from __future__ import annotations

from wc2026.domain import MatchResult
from wc2026.sim.tiebreakers import (
    ThirdPlaceEntry,
    _resolve_tied,
    best_eight_thirds,
    compute_standings,
    rank_group,
    rank_third_placed,
)


def M(home, away, hg, ag) -> MatchResult:
    return MatchResult(home=home, away=away, home_goals=hg, away_goals=ag)


def ranked_names(standings):
    return [s.team for s in standings]


# ── Criterion 1: points ────────────────────────────────────────────────────
def test_clear_points_ordering():
    teams = ["A", "B", "C", "D"]
    matches = [
        M("A", "B", 1, 0),
        M("A", "C", 2, 0),
        M("A", "D", 3, 0),
        M("B", "C", 1, 0),
        M("B", "D", 2, 0),
        M("C", "D", 1, 0),
    ]
    res = rank_group(teams, matches)
    assert ranked_names(res) == ["A", "B", "C", "D"]
    assert [s.points for s in res] == [9, 6, 3, 0]
    assert [s.rank for s in res] == [1, 2, 3, 4]


# ── Overall GD breaks teams level on points whose head-to-head was a draw ───
def test_goal_difference_tiebreak():
    teams = ["A", "B", "C", "D"]
    # A and B both beat C and D, draw each other -> equal points (7 each) AND a drawn
    # head-to-head, so the chain falls through H2H to overall GD; A's bigger margins win.
    matches = [
        M("A", "B", 0, 0),
        M("A", "C", 5, 0),
        M("A", "D", 5, 0),
        M("B", "C", 1, 0),
        M("B", "D", 1, 0),
        M("C", "D", 0, 0),
    ]
    res = rank_group(teams, matches)
    assert res[0].team == "A" and res[1].team == "B"
    assert res[0].gd > res[1].gd


# ── Overall GF breaks teams level on points/GD with a drawn head-to-head ────
def test_goals_for_tiebreak():
    teams = ["A", "B", "C", "D"]
    # A and B level on points with a drawn H2H and equal overall GD; A scores more.
    matches = [
        M("A", "B", 1, 1),
        M("A", "C", 3, 1),
        M("A", "D", 3, 1),
        M("B", "C", 2, 0),
        M("B", "D", 2, 0),
        M("C", "D", 0, 0),
    ]
    res = rank_group(teams, matches)
    a = next(s for s in res if s.team == "A")
    b = next(s for s in res if s.team == "B")
    assert a.points == b.points and a.gd == b.gd
    assert a.gf > b.gf
    assert ranked_names(res).index("A") < ranked_names(res).index("B")


# ── 2026 RULE CHANGE: head-to-head is applied BEFORE overall goal difference ─
def test_2026_head_to_head_beats_overall_goal_difference():
    teams = ["A", "B", "C", "D"]
    # A and B finish level on points (4 each, and nobody else on 4). A beat B head-to-head
    # but B has a far better OVERALL goal difference (+4 vs -1). Under the pre-2026 order
    # B would rank above A on GD; under the 2026 order head-to-head wins, so A ranks above B.
    matches = [
        M("A", "B", 1, 0),  # A wins the head-to-head
        M("A", "C", 0, 0),
        M("A", "D", 0, 2),
        M("B", "C", 5, 0),  # B racks up a big overall GD
        M("B", "D", 1, 1),
        M("C", "D", 0, 2),
    ]
    st = compute_standings(teams, matches)
    assert st["A"].points == st["B"].points == 4
    assert st["A"].gd == -1 and st["B"].gd == 4  # B has the better overall GD
    res = rank_group(teams, matches)
    names = ranked_names(res)
    assert names.index("A") < names.index("B"), names  # H2H wins -> A above B (2026 rule)
    assert names == ["D", "A", "B", "C"], names


# ── Head-to-head between two teams level on points ─────────────────────────
def test_head_to_head_two_teams():
    teams = ["A", "B", "C", "D"]
    # Hand-constructed so A and B finish level on overall (pts=3, GD=-1, GF=1)
    # and A beat B head-to-head, so A must rank above B.
    matches = [
        M("A", "B", 1, 0),  # head-to-head: A beats B
        M("A", "C", 0, 1),  # C beats A
        M("A", "D", 0, 1),  # D beats A
        M("B", "C", 1, 0),  # B beats C
        M("B", "D", 0, 1),  # D beats B
        M("C", "D", 0, 0),
    ]
    sa = compute_standings(teams, matches)
    # Confirm A and B are level on overall before H2H applies.
    assert (sa["A"].points, sa["A"].gd, sa["A"].gf) == (3, -1, 1)
    assert (sa["B"].points, sa["B"].gd, sa["B"].gf) == (3, -1, 1)
    res = rank_group(teams, matches)
    assert ranked_names(res).index("A") < ranked_names(res).index("B")


# ── Criterion 7: fair-play points when fully level ─────────────────────────
def test_fair_play_breaks_full_tie():
    teams = ["A", "B"]
    # Only A vs B played, a draw -> fully level. Fewer disciplinary points wins.
    matches = [M("A", "B", 1, 1)]
    res = rank_group(teams, matches, fair_play={"A": 2, "B": 5})
    assert res[0].team == "A"  # A has fewer fair-play (disciplinary) points
    res2 = rank_group(teams, matches, fair_play={"A": 9, "B": 1})
    assert res2[0].team == "B"


# ── Criterion 8: drawing of lots as final, deterministic resort ────────────
def test_drawing_of_lots_final():
    teams = ["A", "B"]
    matches = [M("A", "B", 0, 0)]  # fully level, equal fair play
    res = rank_group(teams, matches, fair_play={"A": 3, "B": 3}, lots={"A": 1, "B": 0})
    assert res[0].team == "B"  # lower lot value ranks higher


# ── Perfectly symmetric three-way tie falls through H2H to lots ────────────
def test_symmetric_three_way_tie_falls_to_lots():
    teams = ["A", "B", "C", "D"]
    # A, B, C in a perfect 1-0 cycle and each beats D 1-0 -> all level on overall
    # (pts=6, GD=+1, GF=2) AND level head-to-head (each 3 pts, GD 0, GF 1).
    # The chain must fall all the way through to drawing of lots.
    matches = [
        M("A", "B", 1, 0),
        M("B", "C", 1, 0),
        M("C", "A", 1, 0),
        M("A", "D", 1, 0),
        M("B", "D", 1, 0),
        M("C", "D", 1, 0),
    ]
    st = compute_standings(teams, matches)
    for t in ("A", "B", "C"):
        assert (st[t].points, st[t].gd, st[t].gf) == (6, 1, 2), (t, st[t])
    res = rank_group(teams, matches, lots={"A": 0, "B": 1, "C": 2})
    assert res[-1].team == "D"
    assert ranked_names(res)[:3] == ["A", "B", "C"]  # decided purely by lots


# ── Re-application of H2H to a remaining subset, then lots (unit-level) ─────
def test_resolve_tied_reapplies_then_falls_to_lots():
    # Direct test of the recursive criteria-4-6 re-application. Among {A,B,C}:
    # A beats both -> separates at top; B and C drew -> remain level -> recurse on
    # {B,C}; their only H2H is a draw -> still level -> fall through to lots.
    tied = ["A", "B", "C"]
    matches = [
        M("A", "B", 1, 0),
        M("A", "C", 1, 0),
        M("B", "C", 0, 0),
    ]
    standings = compute_standings(tied, matches)  # fair_play all 0
    order = _resolve_tied(tied, standings, matches, lots={"A": 0, "B": 0, "C": 1})
    assert order[0] == "A"            # separated by H2H points
    assert order[1:] == ["B", "C"]   # level subset resolved by lots (B<C)
    # Swap the lots and the level subset flips, confirming lots actually decides.
    order2 = _resolve_tied(tied, standings, matches, lots={"A": 0, "B": 1, "C": 0})
    assert order2 == ["A", "C", "B"]


# ── Third-place ranking across groups ──────────────────────────────────────
def test_third_place_ranking_and_top8():
    thirds = [
        ThirdPlaceEntry("A", "ta", points=4, gd=1, gf=3, fair_play=0),
        ThirdPlaceEntry("B", "tb", points=4, gd=2, gf=4, fair_play=0),  # better GD
        ThirdPlaceEntry("C", "tc", points=3, gd=0, gf=2, fair_play=0),
        ThirdPlaceEntry("D", "td", points=3, gd=0, gf=2, fair_play=1),  # worse fair play
        ThirdPlaceEntry("E", "te", points=6, gd=3, gf=5, fair_play=0),  # best
        ThirdPlaceEntry("F", "tf", points=1, gd=-2, gf=1, fair_play=0),
        ThirdPlaceEntry("G", "tg", points=2, gd=-1, gf=1, fair_play=0),
        ThirdPlaceEntry("H", "th", points=0, gd=-5, gf=0, fair_play=0),
        ThirdPlaceEntry("I", "ti", points=4, gd=1, gf=2, fair_play=0),
        ThirdPlaceEntry("J", "tj", points=3, gd=1, gf=3, fair_play=0),
        ThirdPlaceEntry("K", "tk", points=5, gd=2, gf=4, fair_play=0),
        ThirdPlaceEntry("L", "tl", points=1, gd=-3, gf=0, fair_play=0),
    ]
    ranked = rank_third_placed(thirds)
    assert ranked[0].team == "te"  # 6 pts is best
    assert ranked[1].team == "tk"  # 5 pts next
    # B before A (same pts, better GD); D before... C before D (same pts/gd/gf, C cleaner)
    names = [e.team for e in ranked]
    assert names.index("tb") < names.index("ta")
    assert names.index("tc") < names.index("td")
    top8 = best_eight_thirds(thirds)
    assert len(top8) == 8
    assert {"th", "tl"}.isdisjoint({e.team for e in top8})  # worst two excluded
