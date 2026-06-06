"""Tier-0 Elo ratings, computed from the historical-results backbone.

We derive World-Football-Elo-style ratings by replaying every international match in date
order, so no extra data source is needed (Tier-0). The update rule follows the public
World Football Elo formula:

    We   = 1 / (10^(-dr/400) + 1)              # expected result, dr = rating diff (+100 home)
    R'   = R + K * G * (W - We)                # W in {1, 0.5, 0}
    G    = goal-difference weight (1, 1.5, or (11+|gd|)/8)
    K    = tournament-importance weight

This is a *strength prior / feature*; the Dixon-Coles model is fit separately. Ratings can
also be produced as-of any date (no leakage) for backtesting.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import IngestResult, Provenance

# Tournament importance -> K factor (World Football Elo conventions, simplified).
_K_BY_KEYWORD: list[tuple[str, int]] = [
    ("fifa world cup", 60),
    ("world cup qualification", 40),
    ("confederations cup", 45),
    ("uefa euro", 50),
    ("copa américa", 50),
    ("copa america", 50),
    ("african cup of nations", 50),
    ("afc asian cup", 50),
    ("gold cup", 45),
    ("uefa nations league", 40),
    ("qualification", 40),
    ("friendly", 20),
]
_DEFAULT_K = 30
_HOME_ADV_ELO = 100.0
_BASE_RATING = 1500.0


def _k_factor(tournament: str) -> int:
    t = (tournament or "").lower()
    for kw, k in _K_BY_KEYWORD:
        if kw in t:
            return k
    return _DEFAULT_K


def _g_factor(goal_diff: int) -> float:
    gd = abs(int(goal_diff))
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


def compute_elo(
    results: pd.DataFrame,
    *,
    as_of: str | None = None,
    base_rating: float = _BASE_RATING,
    seed_ratings: dict[str, float] | None = None,
) -> dict[str, float]:
    """Replay matches chronologically and return current Elo per team.

    If ``as_of`` is given, only matches strictly before that date are used (leakage-safe
    for backtests). ``seed_ratings`` optionally warm-starts known teams.
    """
    df = results.sort_values("date")
    if as_of is not None:
        df = df[df["date"] < pd.to_datetime(as_of)]
    ratings: dict[str, float] = dict(seed_ratings or {})

    for row in df.itertuples(index=False):
        home, away = row.home, row.away
        rh = ratings.get(home, base_rating)
        ra = ratings.get(away, base_rating)
        neutral = bool(getattr(row, "neutral", False))
        dr = rh - ra + (0.0 if neutral else _HOME_ADV_ELO)
        we = 1.0 / (10.0 ** (-dr / 400.0) + 1.0)
        hs, as_ = int(row.home_score), int(row.away_score)
        w = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        k = _k_factor(getattr(row, "tournament", "")) * _g_factor(hs - as_)
        delta = k * (w - we)
        ratings[home] = rh + delta
        ratings[away] = ra - delta
    return ratings


class EloRatingsAdapter:
    """Produce Elo ratings from a historical-results frame (Tier-0, derived)."""

    name = "World-Football-Elo-style ratings (derived from historical results)"
    tier = "tier0"

    def __init__(self, cache_dir: Path, offline: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline

    def load(
        self,
        results: pd.DataFrame,
        *,
        as_of: str | None = None,
        seed_ratings: dict[str, float] | None = None,
    ) -> IngestResult:
        ratings = compute_elo(results, as_of=as_of, seed_ratings=seed_ratings)
        prov = Provenance(
            source=self.name,
            url=None,
            tier="tier0",
            fetched_at=Provenance.now_iso(),
            note=f"computed from {len(results)} matches" + (f" as_of {as_of}" if as_of else ""),
        )
        return IngestResult(data=ratings, provenance=prov)
