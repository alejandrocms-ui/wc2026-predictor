"""Probability calibration utilities: reliability tables + isotonic/Platt scaling.

A well-calibrated mediocre model beats a sharp over-confident one for this use case, so we
provide (a) a dependency-free **reliability table / ECE** to *measure* calibration, and
(b) optional isotonic/Platt **recalibration** (needs scikit-learn, install ``".[ml]"``).

The reliability machinery has no heavy dependencies and is unit-tested; the recalibrators
degrade to identity if scikit-learn is absent so the Tier-0 path never breaks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class ReliabilityTable:
    bin_edges: np.ndarray
    mean_predicted: np.ndarray
    empirical_rate: np.ndarray
    counts: np.ndarray
    ece: float  # expected calibration error (count-weighted mean gap)


def reliability_table(
    probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10
) -> ReliabilityTable:
    """Bin predicted probabilities and compare to empirical outcome rates.

    ``probs`` and ``outcomes`` (0/1) are 1-D arrays for a single binary event (e.g. P(home
    win) vs did-home-win). Returns per-bin mean predicted vs observed plus the ECE.
    """
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(probs, edges[1:-1]), 0, n_bins - 1)
    mean_pred = np.full(n_bins, np.nan)
    emp_rate = np.full(n_bins, np.nan)
    counts = np.zeros(n_bins, dtype=int)
    for b in range(n_bins):
        mask = idx == b
        counts[b] = int(mask.sum())
        if counts[b]:
            mean_pred[b] = probs[mask].mean()
            emp_rate[b] = outcomes[mask].mean()
    valid = counts > 0
    ece = float(
        np.sum(counts[valid] * np.abs(mean_pred[valid] - emp_rate[valid])) / counts.sum()
    ) if counts.sum() else 0.0
    return ReliabilityTable(edges, mean_pred, emp_rate, counts, ece)


class IsotonicCalibrator:
    """Monotonic isotonic recalibration of a probability column. Identity without sklearn."""

    def __init__(self) -> None:
        self._model = None

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> IsotonicCalibrator:
        try:
            from sklearn.isotonic import IsotonicRegression
        except Exception:
            self._model = None
            return self
        self._model = IsotonicRegression(out_of_bounds="clip")
        self._model.fit(np.asarray(probs), np.asarray(outcomes))
        return self

    def transform(self, probs: np.ndarray) -> np.ndarray:
        if self._model is None:
            return np.asarray(probs, dtype=float)
        return self._model.predict(np.asarray(probs))
