"""Calibration sanity: reliability table + ECE behave correctly, ensemble blends."""

from __future__ import annotations

import numpy as np

from wc2026.models.calibration import reliability_table
from wc2026.models.dixon_coles import DixonColesModel
from wc2026.models.ensemble import EnsembleModel


def test_perfectly_calibrated_predictions_have_low_ece():
    rng = np.random.default_rng(0)
    # Predicted probs uniform in [0,1]; outcomes drawn with exactly that probability.
    p = rng.random(20000)
    y = (rng.random(20000) < p).astype(int)
    rt = reliability_table(p, y, n_bins=10)
    assert rt.ece < 0.02  # well calibrated by construction


def test_miscalibrated_predictions_have_high_ece():
    rng = np.random.default_rng(1)
    p = np.full(5000, 0.9)          # always claims 90%
    y = (rng.random(5000) < 0.5).astype(int)  # but truth is 50%
    rt = reliability_table(p, y, n_bins=10)
    assert rt.ece > 0.3


def test_ensemble_single_member_is_passthrough():
    elo = {"X": 1900.0, "Y": 1600.0}
    base = DixonColesModel.from_elo(elo)
    ens = EnsembleModel([base])
    a = base.predict_match("X", "Y")
    b = ens.predict_match("X", "Y")
    assert np.allclose(a.matrix, b.matrix)


def test_ensemble_weight_fitting_prefers_better_member():
    # Member 0 is confidently correct; member 1 is uniform. Weights should favour member 0.
    n = 400
    outcomes = np.zeros(n, dtype=int)  # all home wins
    good = np.tile([0.8, 0.1, 0.1], (n, 1))
    bad = np.tile([1 / 3, 1 / 3, 1 / 3], (n, 1))
    w = EnsembleModel.fit_weights([good, bad], outcomes)
    assert w[0] > w[1]
