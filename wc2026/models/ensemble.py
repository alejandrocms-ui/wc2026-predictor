"""Ensemble / stacking of scoreline models.

Combines several models' scoreline matrices into one. Weights are **fit by minimising
out-of-sample RPS/log-loss** on historical tournaments (not hand-picked) — the optimiser
lives in ``fit_weights``. With a single model it is a pass-through, so the pipeline can adopt
it now and gain the GBM/Bayesian members as they come online.
"""

from __future__ import annotations

import numpy as np

from ..domain import MatchContext
from .calibration import IsotonicCalibrator
from .scoreline import ScorelineMatrix


class EnsembleModel:
    """Probability-space mixture of member models sharing the predict_match contract."""

    def __init__(self, members: list, weights: list[float] | None = None):
        if not members:
            raise ValueError("ensemble needs at least one member model")
        self.members = members
        w = np.array(weights if weights is not None else [1.0] * len(members), dtype=float)
        self.weights = w / w.sum()

    def predict_match(
        self, home: str, away: str, context: MatchContext | None = None
    ) -> ScorelineMatrix:
        mats = [m.predict_match(home, away, context).matrix for m in self.members]
        n = min(x.shape[0] for x in mats)
        blended = sum(w * x[:n, :n] for w, x in zip(self.weights, mats, strict=True))
        return ScorelineMatrix(matrix=blended, home=home, away=away,
                               data_tier=(context or MatchContext()).data_tier)

    @staticmethod
    def fit_weights(member_probs: list[np.ndarray], outcomes: np.ndarray) -> np.ndarray:
        """Fit non-negative simplex weights minimising mean RPS on 1X2 (ordered H/D/A).

        ``member_probs[k]`` is an (N, 3) array of each member's 1X2 predictions;
        ``outcomes`` is an (N,) int array in {0,1,2}. Returns weights summing to 1.
        """
        from scipy.optimize import minimize

        stack = np.stack(member_probs, axis=0)  # (M, N, 3)
        obs = np.eye(3)[outcomes]  # (N, 3)

        def mean_rps(w):
            w = np.clip(w, 0, None)
            w = w / (w.sum() + 1e-12)
            blended = np.tensordot(w, stack, axes=(0, 0))  # (N, 3)
            cp = np.cumsum(blended, axis=1)
            co = np.cumsum(obs, axis=1)
            return np.mean(np.sum((cp - co) ** 2, axis=1) / 2)

        m = len(member_probs)
        res = minimize(mean_rps, np.ones(m) / m, method="Nelder-Mead")
        w = np.clip(res.x, 0, None)
        return w / (w.sum() + 1e-12)


class CalibratedEnsembleModel:
    """Weighted ensemble whose 1X2 output is post-hoc isotonic-calibrated.

    The blended scoreline matrix is the primary object; calibration rescales its three
    outcome regions (home-win / draw / away-win cells) to match the calibrated 1X2
    probabilities, then renormalises — so the exact-score *shape* is preserved while the
    1X2 marginals become better calibrated. Calibrators are fit on out-of-sample
    predictions (see ``models/train.py``); without them this is a plain ensemble.
    """

    def __init__(
        self,
        members: list,
        weights: list[float] | None = None,
        calibrators: dict[str, IsotonicCalibrator] | None = None,
    ):
        self.ensemble = EnsembleModel(members, weights)
        self.calibrators = calibrators or {}

    @property
    def weights(self) -> np.ndarray:
        return self.ensemble.weights

    def predict_match(
        self, home: str, away: str, context: MatchContext | None = None
    ) -> ScorelineMatrix:
        sm = self.ensemble.predict_match(home, away, context)
        if not self.calibrators:
            return sm
        raw = np.array(sm.one_x_two)  # (P_home, P_draw, P_away)
        cal = np.array(
            [
                float(self.calibrators[k].transform([raw[i]])[0])
                for i, k in enumerate(("home", "draw", "away"))
            ]
        )
        cal = np.clip(cal, 1e-6, None)
        cal = cal / cal.sum()
        # Rescale the three regions of the matrix to hit the calibrated marginals.
        mat = sm.matrix.copy()
        n = mat.shape[0]
        i = np.arange(n)[:, None]
        j = np.arange(n)[None, :]
        regions = {"home": i > j, "draw": i == j, "away": i < j}
        for idx, key in enumerate(("home", "draw", "away")):
            mask = regions[key]
            cur = mat[mask].sum()
            if cur > 0:
                mat[mask] *= cal[idx] / cur
        return ScorelineMatrix(matrix=mat, home=home, away=away,
                               data_tier=(context or MatchContext()).data_tier)
