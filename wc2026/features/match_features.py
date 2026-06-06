"""Leakage-safe per-match feature matrix for the gradient-boosted model.

A single chronological pass maintains per-team rolling state (Elo, trailing form/goals, rest
days, experience) and emits, for each match, a feature row computed from state **as it was
before that match** — then updates the state. By construction no feature can see the match it
describes or any later match, so the training matrix is leakage-free. The exact same
``_match_features`` function is used at predict time on the *final* state, guaranteeing
train/serve parity.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Elo constants mirror ingest/elo.py so the running Elo feature is self-consistent.
_K_BY_KEYWORD = [
    ("fifa world cup", 60), ("world cup qualification", 40), ("confederations cup", 45),
    ("uefa euro", 50), ("copa américa", 50), ("copa america", 50),
    ("african cup of nations", 50), ("afc asian cup", 50), ("gold cup", 45),
    ("uefa nations league", 40), ("qualification", 40), ("friendly", 20),
]
_DEFAULT_K = 30
_HOME_ADV_ELO = 100.0
_BASE_RATING = 1500.0
_WINDOW = 10  # trailing matches for form/goals

FEATURE_COLUMNS = [
    "elo_diff",
    "elo_home",
    "elo_away",
    "home_gf_avg",
    "home_ga_avg",
    "away_gf_avg",
    "away_ga_avg",
    "home_form_ppg",
    "away_form_ppg",
    "home_rest_days",
    "away_rest_days",
    "home_experience",
    "away_experience",
    "neutral",
]


def _k_factor(tournament: str) -> int:
    t = (tournament or "").lower()
    for kw, k in _K_BY_KEYWORD:
        if kw in t:
            return k
    return _DEFAULT_K


def _g_factor(goal_diff: int) -> float:
    gd = abs(int(goal_diff))
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


@dataclass(slots=True)
class TeamState:
    elo: float = _BASE_RATING
    gf: deque = field(default_factory=lambda: deque(maxlen=_WINDOW))
    ga: deque = field(default_factory=lambda: deque(maxlen=_WINDOW))
    pts: deque = field(default_factory=lambda: deque(maxlen=_WINDOW))
    last_date: pd.Timestamp | None = None
    played: int = 0

    def avg(self, dq: deque) -> float:
        return float(np.mean(dq)) if dq else np.nan


def _match_features(
    hs: TeamState, as_: TeamState, neutral: bool, date: pd.Timestamp
) -> dict[str, float]:
    """Feature row from pre-match state. Shared by training and serving (parity)."""
    def rest(state: TeamState) -> float:
        # Cap at 30 days: beyond a couple of weeks the rest effect plateaus, and capping
        # keeps serve-time values (months/years after the last cached match) in-distribution.
        if state.last_date is None:
            return np.nan
        return float(min((date - state.last_date).days, 30))

    return {
        "elo_diff": hs.elo - as_.elo + (0.0 if neutral else _HOME_ADV_ELO),
        "elo_home": hs.elo,
        "elo_away": as_.elo,
        "home_gf_avg": hs.avg(hs.gf),
        "home_ga_avg": hs.avg(hs.ga),
        "away_gf_avg": as_.avg(as_.gf),
        "away_ga_avg": as_.avg(as_.ga),
        "home_form_ppg": hs.avg(hs.pts),
        "away_form_ppg": as_.avg(as_.pts),
        "home_rest_days": rest(hs),
        "away_rest_days": rest(as_),
        "home_experience": float(hs.played),
        "away_experience": float(as_.played),
        "neutral": 1.0 if neutral else 0.0,
    }


def _update(state_h: TeamState, state_a: TeamState, hg: int, ag: int,
            date: pd.Timestamp, tournament: str, neutral: bool) -> None:
    # Elo update (same rule as ingest/elo.py).
    dr = state_h.elo - state_a.elo + (0.0 if neutral else _HOME_ADV_ELO)
    we = 1.0 / (10.0 ** (-dr / 400.0) + 1.0)
    w = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
    delta = _k_factor(tournament) * _g_factor(hg - ag) * (w - we)
    state_h.elo += delta
    state_a.elo -= delta
    # Rolling form/goals.
    ph = 3 if hg > ag else (1 if hg == ag else 0)
    pa = 3 if ag > hg else (1 if hg == ag else 0)
    state_h.gf.append(hg)
    state_h.ga.append(ag)
    state_h.pts.append(ph)
    state_a.gf.append(ag)
    state_a.ga.append(hg)
    state_a.pts.append(pa)
    state_h.last_date = date
    state_a.last_date = date
    state_h.played += 1
    state_a.played += 1


@dataclass(slots=True)
class FeatureBuilder:
    states: dict[str, TeamState] = field(default_factory=dict)

    def _state(self, team: str) -> TeamState:
        s = self.states.get(team)
        if s is None:
            s = TeamState()
            self.states[team] = s
        return s

    def build_training_matrix(
        self, results: pd.DataFrame, *, min_experience: int = 3
    ) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """Chronological pass → (X, y_home_goals, y_away_goals). Resets internal state.

        Rows where either side has < ``min_experience`` prior matches are dropped from the
        TRAINING set (too cold to be informative) but still update state.
        """
        self.states = {}
        df = results.sort_values("date").reset_index(drop=True)
        rows, yh, ya = [], [], []
        for r in df.itertuples(index=False):
            date = pd.Timestamp(r.date)
            neutral = bool(getattr(r, "neutral", False))
            hs, as_ = self._state(r.home), self._state(r.away)
            feat = _match_features(hs, as_, neutral, date)
            if hs.played >= min_experience and as_.played >= min_experience:
                rows.append(feat)
                yh.append(int(r.home_score))
                ya.append(int(r.away_score))
            _update(hs, as_, int(r.home_score), int(r.away_score),
                    date, getattr(r, "tournament", ""), neutral)
        X = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
        return X, np.array(yh, dtype=float), np.array(ya, dtype=float)

    def fit_state(self, results: pd.DataFrame) -> FeatureBuilder:
        """Replay all results to populate current per-team state (for serving)."""
        self.states = {}
        df = results.sort_values("date").reset_index(drop=True)
        for r in df.itertuples(index=False):
            neutral = bool(getattr(r, "neutral", False))
            hs, as_ = self._state(r.home), self._state(r.away)
            _update(hs, as_, int(r.home_score), int(r.away_score),
                    pd.Timestamp(r.date), getattr(r, "tournament", ""), neutral)
        return self

    def features_for(
        self, home: str, away: str, *, neutral: bool, as_of: pd.Timestamp | None = None
    ) -> pd.DataFrame:
        """Build a single feature row for a hypothetical fixture from current state."""
        date = as_of or pd.Timestamp.utcnow().tz_localize(None)
        hs, as_ = self._state(home), self._state(away)
        feat = _match_features(hs, as_, neutral, date)
        return pd.DataFrame([feat], columns=FEATURE_COLUMNS)
