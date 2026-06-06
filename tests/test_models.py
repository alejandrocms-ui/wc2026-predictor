"""Sanity and behavioural tests for the scoreline matrix and Dixon-Coles model."""

from __future__ import annotations

import numpy as np

from wc2026.domain import MatchContext
from wc2026.models.dixon_coles import DixonColesModel
from wc2026.models.scoreline import ScorelineMatrix


def test_scoreline_markets_are_consistent():
    rng = np.random.default_rng(0)
    raw = rng.random((8, 8))
    sm = ScorelineMatrix(matrix=raw)
    h, d, a = sm.one_x_two
    assert abs((h + d + a) - 1.0) < 1e-9
    assert 0.0 <= sm.prob_btts <= 1.0
    assert abs(sm.prob_over(2.5) + sm.prob_under(2.5) - 1.0) < 1e-9
    assert abs(sm.matrix.sum() - 1.0) < 1e-9
    top = sm.most_likely_scores(3)
    assert len(top) == 3
    assert top[0][2] >= top[1][2] >= top[2][2]  # sorted descending


def test_from_elo_favours_stronger_team():
    elo = {"Strong": 2000.0, "Weak": 1500.0}
    model = DixonColesModel.from_elo(elo)
    ctx = MatchContext(neutral=True)
    sm = model.predict_match("Strong", "Weak", ctx)
    assert sm.prob_home_win > sm.prob_away_win
    assert sm.expected_home_goals > sm.expected_away_goals


def test_neutral_equal_teams_symmetric():
    elo = {"X": 1800.0, "Y": 1800.0}
    model = DixonColesModel.from_elo(elo)
    sm = model.predict_match("X", "Y", MatchContext(neutral=True))
    # Equal strength on neutral ground -> home/away win probs essentially equal.
    assert abs(sm.prob_home_win - sm.prob_away_win) < 1e-6


def test_home_advantage_shifts_probability():
    elo = {"X": 1800.0, "Y": 1800.0}
    model = DixonColesModel.from_elo(elo)
    neutral = model.predict_match("X", "Y", MatchContext(neutral=True))
    at_home = model.predict_match("X", "Y", MatchContext(neutral=False))
    assert at_home.prob_home_win > neutral.prob_home_win


def test_dixon_coles_tau_changes_low_scores():
    elo = {"X": 1800.0, "Y": 1800.0}
    corrected = DixonColesModel.from_elo(elo, rho=-0.1)
    plain = DixonColesModel.from_elo(elo, rho=0.0)
    c = corrected.predict_match("X", "Y", MatchContext(neutral=True))
    p = plain.predict_match("X", "Y", MatchContext(neutral=True))
    # With rho != 0 the 1-1 cell mass differs from the independent-Poisson baseline.
    assert abs(c.matrix[1, 1] - p.matrix[1, 1]) > 1e-4


def test_logit_adjustments_apply():
    elo = {"X": 1800.0, "Y": 1800.0}
    model = DixonColesModel.from_elo(elo)
    base_h, base_a = model.expected_goals("X", "Y", MatchContext(neutral=True))
    adj_h, adj_a = model.expected_goals(
        "X", "Y", MatchContext(neutral=True, home_logit_adj=0.2, away_logit_adj=-0.1)
    )
    assert adj_h > base_h and adj_a < base_a


def test_fit_recovers_strength_ordering():
    # Synthetic league: A strong, C weak. Fit must rank attack A > B > C-ish.
    import pandas as pd

    rng = np.random.default_rng(42)
    strengths = {"A": 1.6, "B": 1.3, "C": 0.8}
    teams = list(strengths)
    rows = []
    base = pd.Timestamp("2024-01-01")
    for k in range(1500):
        h, a = rng.choice(teams, size=2, replace=False)
        lh = strengths[h] / strengths[a] * 1.3
        la = strengths[a] / strengths[h] * 1.1
        rows.append(
            {
                "date": base + pd.Timedelta(days=int(k % 700)),
                "home": h,
                "away": a,
                "home_score": rng.poisson(lh),
                "away_score": rng.poisson(la),
                "neutral": True,
            }
        )
    df = pd.DataFrame(rows)
    model = DixonColesModel().fit(df, halflife_days=3650)
    # Net strength = attack + defense; A should outrank C.
    net = {t: model.attack[t] + model.defense[t] for t in teams}
    assert net["A"] > net["C"]
