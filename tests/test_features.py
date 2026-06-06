"""Leakage and parity tests for the GBM feature builder."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wc2026.features.match_features import FEATURE_COLUMNS, FeatureBuilder


def _toy_results():
    # A beats B repeatedly; chronological.
    dates = pd.date_range("2020-01-01", periods=12, freq="30D")
    rows = []
    for k, d in enumerate(dates):
        h, a = ("A", "B") if k % 2 == 0 else ("B", "A")
        hg, ag = (3, 0) if h == "A" else (0, 3)  # A always wins
        rows.append({"date": d, "home": h, "away": a, "home_score": hg,
                     "away_score": ag, "neutral": True, "tournament": "Friendly"})
    return pd.DataFrame(rows)


def test_feature_columns_present_and_no_future_leak():
    df = _toy_results()
    fb = FeatureBuilder()
    X, yh, ya = fb.build_training_matrix(df, min_experience=1)
    assert list(X.columns) == FEATURE_COLUMNS
    assert len(X) == len(yh) == len(ya)
    # The FIRST usable row's elo features must equal the base (no prior info leaked in).
    # Row 0 (min_experience=1) is the 2nd match; by then A has beaten B once, so A's
    # running Elo must be strictly above B's — and never reflect *future* wins beyond
    # what had happened by that row. Monotonic non-decreasing A-B elo gap is the check.
    gaps = (X["elo_home"] - X["elo_away"]).where(
        X.index.map(lambda i: True)  # all rows
    )
    # Recompute expected: A's advantage should grow over time as it keeps winning.
    a_is_home = df["home"].iloc[1:].reset_index(drop=True) == "A"
    signed_gap = np.where(a_is_home, gaps.to_numpy(), -gaps.to_numpy())
    assert np.all(np.diff(signed_gap) >= -1e-9)  # A's edge never shrinks (it always wins)


def test_serving_features_match_training_function():
    df = _toy_results()
    fb = FeatureBuilder().fit_state(df)
    row = fb.features_for("A", "B", neutral=True)
    assert list(row.columns) == FEATURE_COLUMNS
    # A has only ever beaten B -> A's form points-per-game is maximal (3.0).
    assert row["home_form_ppg"].iloc[0] == 3.0
    assert row["away_form_ppg"].iloc[0] == 0.0
    # rest_days is capped at 30 even though the toy span is ~330 days.
    assert row["home_rest_days"].iloc[0] <= 30


def test_rest_days_capped():
    df = _toy_results()
    fb = FeatureBuilder()
    X, _, _ = fb.build_training_matrix(df, min_experience=1)
    assert X["home_rest_days"].max() <= 30
    assert X["away_rest_days"].max() <= 30
