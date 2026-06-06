"""Unit tests for the backtest scoring metrics (known values)."""

from __future__ import annotations

import numpy as np

from wc2026.backtest import brier, log_loss, outcome_index, rps


def test_outcome_index():
    assert outcome_index(2, 0) == 0  # home
    assert outcome_index(1, 1) == 1  # draw
    assert outcome_index(0, 3) == 2  # away


def test_rps_perfect_prediction_is_zero():
    assert rps(np.array([1.0, 0.0, 0.0]), 0) == 0.0


def test_rps_rewards_ordinal_closeness():
    # True outcome = home. Putting mass on draw (adjacent) beats putting it on away (far).
    near = rps(np.array([0.5, 0.5, 0.0]), 0)
    far = rps(np.array([0.5, 0.0, 0.5]), 0)
    assert near < far


def test_rps_worst_case():
    # Predict away with certainty, home happens -> maximal RPS of 1.0.
    assert abs(rps(np.array([0.0, 0.0, 1.0]), 0) - 1.0) < 1e-12


def test_brier_and_logloss_basic():
    p = np.array([0.7, 0.2, 0.1])
    assert abs(brier(p, 0) - ((0.3) ** 2 + 0.2**2 + 0.1**2)) < 1e-12
    assert log_loss(p, 0) > 0
    assert log_loss(np.array([1.0, 0.0, 0.0]), 0) < 1e-9
