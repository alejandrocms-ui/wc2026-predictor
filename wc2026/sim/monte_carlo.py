"""Vectorised Monte Carlo simulation of the group stage + Round-of-32 qualification.

For each of ``n_sims`` independent tournaments we sample a scoreline for every group
fixture from its predicted matrix (not the modal score — the full distribution), build the
12 group tables, rank them, rank the third-placed teams, and tally who advances.

Performance: group tables and the dominant ranking path are vectorised in numpy. The exact
FIFA head-to-head tiebreaker (``rank_group``) is invoked **only** for the small fraction of
simulated groups where two or more teams are exactly level on points, goal difference and
goals for — the only case where head-to-head can change the order. Third-place ranking uses
a per-simulation 'drawing of lots' random as the final tiebreak, exactly matching
``rank_third_placed`` (all seed fair-play points are 0).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..domain import GROUP_LABELS, MatchResult, TournamentSpec
from ..models.scoreline import ScorelineMatrix
from .tiebreakers import rank_group

WIN, DRAW = 3, 1
N_QUALIFY_THIRDS = 8


@dataclass(slots=True)
class TeamSimSummary:
    team: str
    group: str
    p_win_group: float = 0.0
    p_runner_up: float = 0.0
    p_top2: float = 0.0
    p_best_third: float = 0.0
    p_third_overall: float = 0.0  # finishes 3rd in group (qualified or not)
    p_reach_r32: float = 0.0
    exp_points: float = 0.0
    exp_gd: float = 0.0
    exp_gf: float = 0.0
    # Finishing position distribution within the group: P(1st..4th).
    finish_dist: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass(slots=True)
class SimulationResult:
    n_sims: int
    seed: int
    teams: dict[str, TeamSimSummary] = field(default_factory=dict)

    def group_table(self, label: str) -> list[TeamSimSummary]:
        rows = [t for t in self.teams.values() if t.group == label]
        return sorted(rows, key=lambda r: (-r.p_reach_r32, -r.p_win_group, -r.exp_points))


def _composite_key(points: np.ndarray, gd: np.ndarray, gf: np.ndarray) -> np.ndarray:
    """Lexicographic (points, GD, GF) packed into one sortable integer per (sim, team).

    Bounds for a 3-match group: points 0..9, GD in [-21, 21], GF in [0, ~30]. The offsets
    keep the lexicographic order intact (higher = better).
    """
    return points.astype(np.int64) * 100_000 + (gd.astype(np.int64) + 100) * 1_000 + gf.astype(np.int64)


def simulate(
    spec: TournamentSpec,
    matrices: list[ScorelineMatrix],
    *,
    n_sims: int = 50_000,
    seed: int = 20260611,
) -> SimulationResult:
    """Run the Monte Carlo. ``matrices`` aligns 1:1 with ``spec.fixtures``."""
    if len(matrices) != len(spec.fixtures):
        raise ValueError("matrices must align 1:1 with spec.fixtures")
    rng = np.random.default_rng(seed)

    fixtures = spec.fixtures
    n_fix = len(fixtures)
    # Sample all fixtures' scorelines: hg[f], ag[f] are (n_sims,) arrays.
    hg = np.empty((n_fix, n_sims), dtype=np.int16)
    ag = np.empty((n_fix, n_sims), dtype=np.int16)
    for f, sm in enumerate(matrices):
        draws = sm.sample(rng, size=n_sims)  # (n_sims, 2)
        hg[f] = draws[:, 0]
        ag[f] = draws[:, 1]

    # Index fixtures by group.
    fix_by_group: dict[str, list[int]] = {g: [] for g in GROUP_LABELS}
    for f, fx in enumerate(fixtures):
        fix_by_group[fx.group].append(f)

    # Per-group, per-sim ranking. Collect rank arrays and stats per team.
    team_rank: dict[str, np.ndarray] = {}  # team -> (n_sims,) rank 1..4
    team_pts: dict[str, np.ndarray] = {}
    team_gd: dict[str, np.ndarray] = {}
    team_gf: dict[str, np.ndarray] = {}

    for label in GROUP_LABELS:
        members = spec.groups[label]
        tidx = {t: k for k, t in enumerate(members)}
        pts = np.zeros((n_sims, 4), dtype=np.int32)
        gf = np.zeros((n_sims, 4), dtype=np.int32)
        ga = np.zeros((n_sims, 4), dtype=np.int32)

        group_fix = fix_by_group[label]
        for f in group_fix:
            fx = fixtures[f]
            hi, ai = tidx[fx.home], tidx[fx.away]
            h, a = hg[f].astype(np.int32), ag[f].astype(np.int32)
            gf[:, hi] += h
            ga[:, hi] += a
            gf[:, ai] += a
            ga[:, ai] += h
            home_win = h > a
            away_win = h < a
            draw = ~(home_win | away_win)
            pts[:, hi] += np.where(home_win, WIN, 0) + np.where(draw, DRAW, 0)
            pts[:, ai] += np.where(away_win, WIN, 0) + np.where(draw, DRAW, 0)

        gd = gf - ga

        # Fast path orders by overall (pts, GD, GF) — CORRECT only when no two teams are
        # level on POINTS. Under the 2026 rules head-to-head precedes overall GD, so ANY
        # equal-points pair must be resolved by the tested FIFA engine (slow path).
        key = _composite_key(pts, gd, gf)  # (n_sims, 4)
        lots = rng.random((n_sims, 4))
        order = np.lexsort((lots, -key), axis=1)  # (n_sims,4): team indices best->worst
        ranks = np.empty((n_sims, 4), dtype=np.int8)
        rows = np.arange(n_sims)[:, None]
        ranks[rows, order] = np.arange(1, 5, dtype=np.int8)

        # Slow path for any simulation where two teams share points (head-to-head matters).
        sorted_pts = np.sort(pts, axis=1)
        tie_mask = np.any(sorted_pts[:, 1:] == sorted_pts[:, :-1], axis=1)
        tie_sims = np.nonzero(tie_mask)[0]
        if tie_sims.size:
            _resolve_tied_sims(
                tie_sims, members, tidx, group_fix, fixtures, hg, ag, ranks, rng
            )

        for t, k in tidx.items():
            team_rank[t] = ranks[:, k]
            team_pts[t] = pts[:, k]
            team_gd[t] = gd[:, k]
            team_gf[t] = gf[:, k]

    # ── Third-place qualification across the 12 groups ──────────────────────
    third_keys = np.empty((n_sims, 12), dtype=np.int64)
    third_team_by_group = {}
    for gi, label in enumerate(GROUP_LABELS):
        members = spec.groups[label]
        # Which team is 3rd in each sim?
        rank_mat = np.stack([team_rank[t] for t in members], axis=1)  # (n_sims,4)
        is_third = rank_mat == 3
        # team index (0..3) that is third per sim
        third_idx = np.argmax(is_third, axis=1)
        third_team_by_group[label] = (members, third_idx)
        # Build the third team's (pts,gd,gf) key per sim.
        pts_t = np.choose(third_idx, [team_pts[t] for t in members])
        gd_t = np.choose(third_idx, [team_gd[t] for t in members])
        gf_t = np.choose(third_idx, [team_gf[t] for t in members])
        third_keys[:, gi] = _composite_key(pts_t, gd_t, gf_t)

    # Rank the 12 thirds; top 8 qualify. Lots random breaks any remaining tie exactly
    # like rank_third_placed (fair-play seed = 0 for all teams).
    lots_third = rng.random((n_sims, 12))
    # lexsort: best (highest key) first. Sort ascending of (-key) with lots tiebreak.
    third_order = np.lexsort((lots_third, -third_keys), axis=1)  # (n_sims,12)
    qualifies_third = np.zeros((n_sims, 12), dtype=bool)
    top8 = third_order[:, :N_QUALIFY_THIRDS]
    np.put_along_axis(qualifies_third, top8, True, axis=1)

    # Map third-qualification back to teams.
    best_third_flag: dict[str, np.ndarray] = {}
    for gi, label in enumerate(GROUP_LABELS):
        members, third_idx = third_team_by_group[label]
        group_qual = qualifies_third[:, gi]  # (n_sims,)
        for t in members:
            is_this_third = (team_rank[t] == 3)
            best_third_flag[t] = is_this_third & group_qual

    # ── Aggregate per-team summaries ────────────────────────────────────────
    result = SimulationResult(n_sims=n_sims, seed=seed)
    for label in GROUP_LABELS:
        for t in spec.groups[label]:
            r = team_rank[t]
            finish = tuple(float(np.mean(r == k)) for k in (1, 2, 3, 4))
            p_top2 = float(np.mean(r <= 2))
            p_best_third = float(np.mean(best_third_flag[t]))
            result.teams[t] = TeamSimSummary(
                team=t,
                group=label,
                p_win_group=finish[0],
                p_runner_up=finish[1],
                p_top2=p_top2,
                p_third_overall=finish[2],
                p_best_third=p_best_third,
                p_reach_r32=p_top2 + p_best_third,
                exp_points=float(np.mean(team_pts[t])),
                exp_gd=float(np.mean(team_gd[t])),
                exp_gf=float(np.mean(team_gf[t])),
                finish_dist=finish,
            )
    return result


def _resolve_tied_sims(
    tie_sims: np.ndarray,
    members: list[str],
    tidx: dict[str, int],
    group_fix: list[int],
    fixtures,
    hg: np.ndarray,
    ag: np.ndarray,
    ranks: np.ndarray,
    rng: np.random.Generator,
) -> None:
    """In-place fix the rank rows for sims with an exact (pts,GD,GF) tie via FIFA H2H."""
    for s in tie_sims:
        matches = [
            MatchResult(
                home=fixtures[f].home,
                away=fixtures[f].away,
                home_goals=int(hg[f, s]),
                away_goals=int(ag[f, s]),
            )
            for f in group_fix
        ]
        lots = {t: float(rng.random()) for t in members}
        ordered = rank_group(members, matches, lots=lots)
        for standing in ordered:
            ranks[s, tidx[standing.team]] = standing.rank
