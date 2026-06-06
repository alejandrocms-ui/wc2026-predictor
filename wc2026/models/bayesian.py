"""Secondary model — Bayesian hierarchical Poisson (FLAGGED FOR LATER).

Per the project decision, the Bayesian partial-pooling model ships behind a flag; the
interim stand-in for low-data teams is the Elo cold-start fill in ``models/build.py``.

When enabled (install ``".[bayes]"``), this fits attack/defense with **partial pooling** —
team parameters shrink toward a shared prior informed by Elo/FIFA rank, which prevents
overconfident estimates for teams with few recent comparable matches. The interface mirrors
``DixonColesModel`` (``predict_match -> ScorelineMatrix``) so it slots into the ensemble.

This is a documented stub: it raises a clear, actionable error until numpyro/pymc is wired,
rather than silently doing nothing.
"""

from __future__ import annotations

from ..domain import MatchContext
from .scoreline import ScorelineMatrix


class BayesianHierarchicalModel:
    enabled = False  # flip on once numpyro/pymc fit is implemented

    def __init__(self, *, draws: int = 1000, partial_pooling: bool = True):
        self.draws = draws
        self.partial_pooling = partial_pooling

    def fit(self, results, elo_prior=None):  # pragma: no cover - flagged
        raise NotImplementedError(
            "Bayesian hierarchical model is flagged for a later iteration. "
            "Install with pip install -e \".[bayes]\" and implement the numpyro/pymc fit. "
            "The Elo cold-start fill in models/build.py is the interim low-data stand-in."
        )

    def predict_match(  # pragma: no cover - flagged
        self, home: str, away: str, context: MatchContext | None = None
    ) -> ScorelineMatrix:
        raise NotImplementedError("Bayesian model not yet enabled (see fit()).")
