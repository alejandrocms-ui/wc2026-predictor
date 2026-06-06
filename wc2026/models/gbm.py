"""Tertiary model — LightGBM Poisson regressors on leakage-safe features.

Two gradient-boosted regressors predict the home and away expected goals from the as-of
feature matrix (``features/match_features.py``); those means are turned into a Dixon-Coles
scoreline matrix so the GBM obeys the same ``predict_match -> ScorelineMatrix`` contract as
every other model and can be ensembled directly.

Requires the ML extra (``pip install -e ".[ml]"``). Raises a clear error if used without
LightGBM rather than failing obscurely.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson

from ..domain import MatchContext
from ..features.match_features import FeatureBuilder
from .dixon_coles import _DEFAULT_RHO, _tau
from .scoreline import ScorelineMatrix


class LightGBMGoalsModel:
    """Predict (home_xg, away_xg) via gradient boosting; emit a Dixon-Coles matrix."""

    def __init__(self, max_goals: int = 10, rho: float = _DEFAULT_RHO):
        self.max_goals = max_goals
        self.rho = rho
        self._home_model = None
        self._away_model = None
        self.builder = FeatureBuilder()
        self._fitted = False

    @staticmethod
    def _require_lgbm():
        try:
            import lightgbm  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional dep
            raise ImportError(
                'LightGBM not installed. Install with: pip install -e ".[ml]"'
            ) from exc

    def fit(
        self,
        results: pd.DataFrame,
        *,
        min_experience: int = 3,
        n_estimators: int = 400,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        random_state: int = 0,
    ) -> LightGBMGoalsModel:
        """Train two Poisson LightGBM regressors on the leakage-safe feature matrix."""
        self._require_lgbm()
        import lightgbm as lgb

        X, yh, ya = self.builder.build_training_matrix(results, min_experience=min_experience)
        params = dict(
            objective="poisson",
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            min_child_samples=40,
            subsample=0.8,
            colsample_bytree=0.9,
            random_state=random_state,
            verbosity=-1,
        )
        self._home_model = lgb.LGBMRegressor(**params).fit(X, yh)
        self._away_model = lgb.LGBMRegressor(**params).fit(X, ya)
        # Populate serving state from the full history.
        self.builder.fit_state(results)
        self._fitted = True
        return self

    def expected_goals(
        self, home: str, away: str, context: MatchContext | None = None
    ) -> tuple[float, float]:
        ctx = context or MatchContext()
        feat = self.builder.features_for(home, away, neutral=ctx.neutral)
        lh = float(self._home_model.predict(feat)[0]) * np.exp(ctx.home_logit_adj)
        la = float(self._away_model.predict(feat)[0]) * np.exp(ctx.away_logit_adj)
        return float(np.clip(lh, 0.05, 8.0)), float(np.clip(la, 0.05, 8.0))

    def predict_match(
        self, home: str, away: str, context: MatchContext | None = None
    ) -> ScorelineMatrix:
        if not self._fitted:
            raise RuntimeError("LightGBMGoalsModel must be fit before predicting.")
        ctx = context or MatchContext()
        lh, la = self.expected_goals(home, away, ctx)
        n = self.max_goals + 1
        mat = np.outer(poisson.pmf(np.arange(n), lh), poisson.pmf(np.arange(n), la))
        i = np.arange(n)[:, None] * np.ones((1, n), dtype=int)
        j = np.ones((n, 1), dtype=int) * np.arange(n)[None, :]
        mat = np.clip(mat * _tau(i, j, lh, la, self.rho), 0.0, None)
        return ScorelineMatrix(matrix=mat, home=home, away=away, data_tier=ctx.data_tier)
