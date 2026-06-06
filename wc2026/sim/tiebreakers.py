"""FIFA group-stage tiebreakers, third-place ranking, and R32 bracket mapping.

Pure, side-effect-free functions — fully testable without any model. This module encodes
FIFA's official ranking criteria (2026 group stage). Get this wrong and every downstream
probability is wrong, so it is covered by unit tests with known cases (see
``tests/test_tiebreakers.py``).

Official group ranking order (FIFA, **2026 format** — note: in 2026 head-to-head is applied
BEFORE overall goal difference, the first such change since 1970):
  1. Points (3 win / 1 draw / 0 loss), all group matches
  If two or more teams are level on points, the following apply to *those teams only*:
  2. Points in head-to-head matches among the tied teams
  3. Goal difference in those head-to-head matches
  4. Goals for in those head-to-head matches
  If a subset is still level after 2–4, criteria 2–4 are *re-applied* to that subset
  (the mini-table is recomputed among the smaller group). Then, still level:
  5. Overall goal difference (all group matches)
  6. Overall goals for (all group matches)
  7. Fair-play / disciplinary points (fewer ranks higher)
  8. Final criterion (FIFA world ranking / drawing of lots — modelled via ``lots``)

Third-placed teams (across the 12 groups) are ranked by the *overall* criteria
(points, overall GD, overall GF, fair-play, final criterion) — head-to-head does not apply
(different groups). The 8 best advance to the Round of 32.

Sources: ESPN / SofaScore / FIFA tie-breaker explainers (Dec 2025). The exact FINAL
criterion (FIFA ranking vs drawing of lots) is reported inconsistently; it is abstracted
behind ``lots`` so either interpretation plugs in. Verify vs the FIFA regulations PDF.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..domain import GroupStanding, MatchResult

WIN_POINTS = 3
DRAW_POINTS = 1


# ──────────────────────────────────────────────────────────────────────────
# Standings from results
# ──────────────────────────────────────────────────────────────────────────
def compute_standings(
    teams: list[str],
    matches: list[MatchResult],
    fair_play: dict[str, int] | None = None,
) -> dict[str, GroupStanding]:
    """Build overall standings for ``teams`` from their played ``matches``.

    ``fair_play`` maps team -> disciplinary points (lower is better); defaults to 0.
    Only matches whose both teams are in ``teams`` are counted.
    """
    fair_play = fair_play or {}
    table = {t: GroupStanding(team=t, fair_play=fair_play.get(t, 0)) for t in teams}
    team_set = set(teams)
    for m in matches:
        if m.home not in team_set or m.away not in team_set:
            continue
        h, a = table[m.home], table[m.away]
        h.played += 1
        a.played += 1
        h.gf += m.home_goals
        h.ga += m.away_goals
        a.gf += m.away_goals
        a.ga += m.home_goals
        if m.home_goals > m.away_goals:
            h.won += 1
            a.lost += 1
            h.points += WIN_POINTS
        elif m.home_goals < m.away_goals:
            a.won += 1
            h.lost += 1
            a.points += WIN_POINTS
        else:
            h.drawn += 1
            a.drawn += 1
            h.points += DRAW_POINTS
            a.points += DRAW_POINTS
    return table


# ──────────────────────────────────────────────────────────────────────────
# Group ranking with full FIFA tiebreaker chain
# ──────────────────────────────────────────────────────────────────────────
def _overall_key(s: GroupStanding) -> tuple[int, int, int]:
    """Sort key for criteria 1–3 (descending preference)."""
    return (s.points, s.gd, s.gf)


def _runs_equal_on(
    ordered: list[str], standings: dict[str, GroupStanding], key
) -> list[list[str]]:
    """Split an already-sorted team list into maximal runs equal on ``key``."""
    runs: list[list[str]] = []
    for t in ordered:
        if runs and key(standings[t]) == key(standings[runs[-1][-1]]):
            runs[-1].append(t)
        else:
            runs.append([t])
    return runs


def _h2h_stats(tied: list[str], matches: list[MatchResult]) -> dict[str, tuple[int, int, int]]:
    """Head-to-head mini-table among ``tied`` teams: team -> (points, gd, gf)."""
    pts: dict[str, int] = defaultdict(int)
    gf: dict[str, int] = defaultdict(int)
    ga: dict[str, int] = defaultdict(int)
    tied_set = set(tied)
    for m in matches:
        if m.home in tied_set and m.away in tied_set:
            gf[m.home] += m.home_goals
            ga[m.home] += m.away_goals
            gf[m.away] += m.away_goals
            ga[m.away] += m.home_goals
            if m.home_goals > m.away_goals:
                pts[m.home] += WIN_POINTS
            elif m.home_goals < m.away_goals:
                pts[m.away] += WIN_POINTS
            else:
                pts[m.home] += DRAW_POINTS
                pts[m.away] += DRAW_POINTS
    return {t: (pts[t], gf[t] - ga[t], gf[t]) for t in tied}


def _resolve_tied(
    tied: list[str],
    standings: dict[str, GroupStanding],
    matches: list[MatchResult],
    lots: dict[str, int],
) -> list[str]:
    """Order a cluster of teams level on POINTS via the 2026 criteria 2–8.

    Head-to-head (criteria 2–4) is applied FIRST and recursively re-applied to any subset
    that remains level; only then does it fall through to overall GD (5), overall GF (6),
    fair-play (7) and the final criterion (8, modelled by ``lots``).
    """
    if len(tied) == 1:
        return list(tied)

    h2h = _h2h_stats(tied, matches)
    # Criteria 2–4: head-to-head points, GD, GF (descending).
    ordered = sorted(tied, key=lambda t: h2h[t], reverse=True)

    result: list[str] = []
    for run in _runs_equal_on(ordered, standings, key=lambda s: h2h[s.team]):
        if len(run) == 1:
            result.extend(run)
        elif len(run) < len(tied):
            # H2H separated a proper subset — re-apply 2–4 to the smaller subset.
            result.extend(_resolve_tied(run, standings, matches, lots))
        else:
            # Whole cluster still level on head-to-head. Fall to overall GD, overall GF,
            # fair-play, then the final criterion (lots / FIFA ranking).
            result.extend(
                sorted(
                    run,
                    key=lambda t: (
                        -standings[t].gd,
                        -standings[t].gf,
                        standings[t].fair_play,
                        lots.get(t, 0),
                    ),
                )
            )
    return result


def rank_group(
    teams: list[str],
    matches: list[MatchResult],
    fair_play: dict[str, int] | None = None,
    lots: dict[str, int] | None = None,
) -> list[GroupStanding]:
    """Return the four teams ranked 1..4 per FIFA's official 2026 group tiebreaker chain.

    ``lots`` maps team -> deterministic value (lower ranks higher), modelling the final
    criterion (FIFA world ranking / drawing of lots). In simulation it is seeded; in tests
    it is explicit. The returned standings have ``.rank`` set (1 = group winner).
    """
    lots = lots or {}
    standings = compute_standings(teams, matches, fair_play)
    # Criterion 1: overall points. Teams level on points go to the head-to-head chain.
    ordered = sorted(teams, key=lambda t: standings[t].points, reverse=True)

    final: list[str] = []
    for run in _runs_equal_on(ordered, standings, key=lambda s: s.points):
        if len(run) == 1:
            final.extend(run)
        else:
            final.extend(_resolve_tied(run, standings, matches, lots))

    for i, t in enumerate(final, start=1):
        standings[t].rank = i
    return [standings[t] for t in final]


# ──────────────────────────────────────────────────────────────────────────
# Third-place ranking across groups
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class ThirdPlaceEntry:
    group: str
    team: str
    points: int
    gd: int
    gf: int
    fair_play: int


def rank_third_placed(
    thirds: list[ThirdPlaceEntry],
    lots: dict[str, int] | None = None,
) -> list[ThirdPlaceEntry]:
    """Rank the 12 third-placed teams by overall criteria; best first.

    Order: points, goal difference, goals for, (fair-play ascending), (lots ascending).
    Head-to-head does NOT apply across groups. The caller takes the top 8.
    """
    lots = lots or {}
    return sorted(
        thirds,
        key=lambda e: (-e.points, -e.gd, -e.gf, e.fair_play, lots.get(e.team, 0)),
    )


def best_eight_thirds(
    thirds: list[ThirdPlaceEntry],
    lots: dict[str, int] | None = None,
) -> list[ThirdPlaceEntry]:
    """The 8 best third-placed teams that advance to the Round of 32."""
    return rank_third_placed(thirds, lots)[:8]
