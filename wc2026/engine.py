"""High-level orchestration: turn a fitted model + tournament spec into predictions.

This is the public library surface a future FastAPI layer would call. It depends only on
the model contract (``predict_match``) and the domain types, so any model (Dixon-Coles,
ensemble, …) plugs in unchanged.
"""

from __future__ import annotations

from typing import Protocol

from .domain import MatchContext, TournamentSpec
from .features import build_context
from .models.scoreline import ScorelineMatrix
from .sim.monte_carlo import SimulationResult, simulate


class MatchModel(Protocol):
    """Anything that can turn (home, away, context) into a scoreline distribution."""

    def predict_match(
        self, home: str, away: str, context: MatchContext | None = ...
    ) -> ScorelineMatrix: ...


def build_fixture_matrices(
    spec: TournamentSpec,
    model: MatchModel,
    *,
    data_tier: str = "tier0",
) -> list[ScorelineMatrix]:
    """Predict every group fixture, returning matrices aligned 1:1 with ``spec.fixtures``."""
    matrices: list[ScorelineMatrix] = []
    for fx in spec.fixtures:
        ctx = build_context(fx, spec, data_tier=data_tier)
        matrices.append(model.predict_match(fx.home, fx.away, ctx))
    return matrices


def run_tournament_simulation(
    spec: TournamentSpec,
    model: MatchModel,
    *,
    n_sims: int = 50_000,
    seed: int = 20260611,
    data_tier: str = "tier0",
) -> tuple[list[ScorelineMatrix], SimulationResult]:
    """Build fixture matrices and run the Monte Carlo. Returns (matrices, result)."""
    matrices = build_fixture_matrices(spec, model, data_tier=data_tier)
    result = simulate(spec, matrices, n_sims=n_sims, seed=seed)
    return matrices, result
