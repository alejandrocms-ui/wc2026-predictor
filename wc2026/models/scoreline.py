"""Scoreline probability matrix and the derived betting/analysis markets.

A ``ScorelineMatrix`` is the canonical output of every model: ``P[i, j]`` is the joint
probability of ``home_goals == i`` and ``away_goals == j`` for ``i, j in 0..max_goals``.
All 1X2 / BTTS / Over-Under / exact-score quantities are pure functions of this matrix, so
downstream code (simulation, UI, backtest) never re-derives goal models — it reads markets
off the matrix. This keeps every market mutually consistent by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class ScorelineMatrix:
    """Joint scoreline distribution for one fixture.

    ``matrix`` is a square ``(n, n)`` array summing to 1 (rows = home goals, cols = away).
    """

    matrix: np.ndarray
    home: str = ""
    away: str = ""
    data_tier: str = "tier0"  # provenance for the UI badge

    def __post_init__(self) -> None:
        m = np.asarray(self.matrix, dtype=float)
        if m.ndim != 2 or m.shape[0] != m.shape[1]:
            raise ValueError("scoreline matrix must be square 2-D")
        total = m.sum()
        if total <= 0:
            raise ValueError("scoreline matrix has non-positive mass")
        # Normalise defensively (truncation of the Poisson tail loses a little mass).
        self.matrix = m / total

    # ── 1X2 ────────────────────────────────────────────────────────────────
    @property
    def prob_home_win(self) -> float:
        return float(np.tril(self.matrix, -1).sum())  # i > j

    @property
    def prob_draw(self) -> float:
        return float(np.trace(self.matrix))  # i == j

    @property
    def prob_away_win(self) -> float:
        return float(np.triu(self.matrix, 1).sum())  # i < j

    @property
    def one_x_two(self) -> tuple[float, float, float]:
        return (self.prob_home_win, self.prob_draw, self.prob_away_win)

    # ── BTTS ─────────────────────────────────────────────────────────────────
    @property
    def prob_btts(self) -> float:
        """Both teams to score: 1 - P(home=0) - P(away=0) + P(0-0)."""
        p_home_blank = self.matrix[0, :].sum()
        p_away_blank = self.matrix[:, 0].sum()
        p_nil_nil = self.matrix[0, 0]
        return float(1.0 - p_home_blank - p_away_blank + p_nil_nil)

    # ── Over / Under ─────────────────────────────────────────────────────────
    def prob_over(self, line: float = 2.5) -> float:
        """P(total goals > line). Use half-lines (2.5, 3.5...) to avoid pushes."""
        n = self.matrix.shape[0]
        i = np.arange(n)[:, None]
        j = np.arange(n)[None, :]
        return float(self.matrix[(i + j) > line].sum())

    def prob_under(self, line: float = 2.5) -> float:
        return float(1.0 - self.prob_over(line))

    # ── Exact score / summaries ──────────────────────────────────────────────
    def most_likely_scores(self, k: int = 5) -> list[tuple[int, int, float]]:
        """Top-k most probable exact scorelines as (home, away, prob)."""
        flat = self.matrix.ravel()
        n = self.matrix.shape[0]
        idx = np.argsort(flat)[::-1][:k]
        return [(int(p // n), int(p % n), float(flat[p])) for p in idx]

    @property
    def expected_home_goals(self) -> float:
        n = self.matrix.shape[0]
        return float((self.matrix.sum(axis=1) * np.arange(n)).sum())

    @property
    def expected_away_goals(self) -> float:
        n = self.matrix.shape[0]
        return float((self.matrix.sum(axis=0) * np.arange(n)).sum())

    def sample(self, rng: np.random.Generator, size: int = 1) -> np.ndarray:
        """Sample ``size`` scorelines, returned as an int array of shape (size, 2)."""
        n = self.matrix.shape[0]
        flat = self.matrix.ravel()
        draws = rng.choice(flat.size, size=size, p=flat)
        return np.stack([draws // n, draws % n], axis=1).astype(np.int64)
