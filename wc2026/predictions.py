"""Turn per-fixture scoreline matrices into a tidy predictions table of derived markets."""

from __future__ import annotations

import pandas as pd

from .domain import TournamentSpec
from .models.scoreline import ScorelineMatrix


def predictions_frame(
    spec: TournamentSpec, matrices: list[ScorelineMatrix]
) -> pd.DataFrame:
    """One row per fixture with 1X2 / BTTS / O-U markets and the top scoreline."""
    rows = []
    for fx, sm in zip(spec.fixtures, matrices, strict=True):
        h, d, a = sm.one_x_two
        top = sm.most_likely_scores(1)[0]
        rows.append(
            {
                "match_id": fx.match_id,
                "group": fx.group,
                "matchday": fx.matchday,
                "date": fx.date,
                "venue_city": fx.venue_city,
                "home": fx.home,
                "away": fx.away,
                "p_home_win": h,
                "p_draw": d,
                "p_away_win": a,
                "p_btts": sm.prob_btts,
                "p_over_2_5": sm.prob_over(2.5),
                "p_under_2_5": sm.prob_under(2.5),
                "exp_home_goals": sm.expected_home_goals,
                "exp_away_goals": sm.expected_away_goals,
                "top_score": f"{top[0]}-{top[1]}",
                "top_score_prob": top[2],
                "data_tier": sm.data_tier,
            }
        )
    return pd.DataFrame(rows)
