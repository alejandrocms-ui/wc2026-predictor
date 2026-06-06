"""Train the calibrated ensemble end-to-end (leakage-safe split).

Pipeline:
  1. Split history into TRAIN (< cutoff) and VALIDATION (cutoff .. end).
  2. Fit Dixon-Coles and (if available) LightGBM on TRAIN only.
  3. Predict the VALIDATION matches with each member → fit ensemble weights minimising
     out-of-sample RPS (never hand-picked).
  4. Blend VALIDATION predictions with those weights → fit isotonic 1X2 calibrators.
  5. Refit the members on the FULL history for serving; return a CalibratedEnsembleModel
     carrying the validation-fitted weights + calibrators.

Everything degrades gracefully: if LightGBM isn't installed the ensemble is Dixon-Coles
only (still calibrated), so the Tier-0 path never breaks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..domain import MatchContext
from .build import build_dixon_coles
from .calibration import IsotonicCalibrator
from .dixon_coles import DixonColesModel
from .ensemble import CalibratedEnsembleModel, EnsembleModel

try:  # optional ML extra
    from .gbm import LightGBMGoalsModel

    _HAS_GBM = True
except Exception:  # pragma: no cover
    _HAS_GBM = False


def _outcome_idx(hg: int, ag: int) -> int:
    return 0 if hg > ag else (1 if hg == ag else 2)


def _member_1x2(model, matches: pd.DataFrame) -> np.ndarray:
    out = np.empty((len(matches), 3))
    for r, row in enumerate(matches.itertuples(index=False)):
        neutral = bool(getattr(row, "neutral", False))
        sm = model.predict_match(row.home, row.away, MatchContext(neutral=neutral))
        out[r] = sm.one_x_two
    return out


@dataclass(slots=True)
class TrainConfig:
    cutoff: str = "2023-01-01"   # validation = matches on/after this date
    fit_years: int = 10
    halflife_days: float = 547.0
    use_gbm: bool = True
    gbm_window_years: int = 14
    gbm_estimators: int = 400
    verbose: bool = False


def train_calibrated_ensemble(
    results: pd.DataFrame,
    elo_full: dict[str, float],
    *,
    config: TrainConfig | None = None,
    teams_of_interest: list[str] | None = None,
) -> CalibratedEnsembleModel:
    cfg = config or TrainConfig()
    log = (lambda m: print(f"[train] {m}", flush=True)) if cfg.verbose else (lambda m: None)

    df = results.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    cutoff = pd.Timestamp(cfg.cutoff)
    train = df[df["date"] < cutoff]
    val = df[df["date"] >= cutoff]
    log(f"train={len(train)} val={len(val)}")

    use_gbm = cfg.use_gbm and _HAS_GBM

    # ── Fit members on TRAIN ────────────────────────────────────────────────
    from ..ingest.elo import compute_elo

    elo_train = compute_elo(train)
    dc_train = build_dixon_coles(
        train, elo_train, fit_years=cfg.fit_years, halflife_days=cfg.halflife_days,
        teams_of_interest=teams_of_interest,
    )
    members_train = [dc_train]
    if use_gbm:
        gbm_train = LightGBMGoalsModel().fit(
            train[train["date"] >= cutoff - pd.Timedelta(days=365 * cfg.gbm_window_years)],
            n_estimators=cfg.gbm_estimators,
        )
        members_train.append(gbm_train)
    log(f"members: {len(members_train)} (gbm={'on' if use_gbm else 'off'})")

    # ── Fit ensemble weights on VALIDATION (out-of-sample RPS) ───────────────
    if len(val) >= 200:
        member_probs = [_member_1x2(m, val) for m in members_train]
        outcomes = np.array(
            [_outcome_idx(int(r.home_score), int(r.away_score)) for r in val.itertuples(index=False)]
        )
        if len(members_train) > 1:
            weights = EnsembleModel.fit_weights(member_probs, outcomes)
        else:
            weights = np.array([1.0])
        log(f"weights={np.round(weights, 3).tolist()}")

        # Blend val predictions, fit isotonic calibrators per outcome.
        stack = np.stack(member_probs, axis=0)  # (M, N, 3)
        blended = np.tensordot(weights, stack, axes=(0, 0))  # (N, 3)
        calibrators = {}
        for i, key in enumerate(("home", "draw", "away")):
            y = (outcomes == i).astype(float)
            calibrators[key] = IsotonicCalibrator().fit(blended[:, i], y)
    else:  # pragma: no cover - tiny-data fallback
        weights = np.ones(len(members_train)) / len(members_train)
        calibrators = {}
        log("validation too small; equal weights, no calibration")

    # ── Refit members on FULL history for serving ───────────────────────────
    dc_full = build_dixon_coles(
        df, elo_full, fit_years=cfg.fit_years, halflife_days=cfg.halflife_days,
        teams_of_interest=teams_of_interest,
    )
    members_full = [dc_full]
    if use_gbm:
        gbm_full = LightGBMGoalsModel().fit(
            df[df["date"] >= df["date"].max() - pd.Timedelta(days=365 * cfg.gbm_window_years)],
            n_estimators=cfg.gbm_estimators,
        )
        members_full.append(gbm_full)

    return CalibratedEnsembleModel(
        members=members_full, weights=list(weights), calibrators=calibrators
    )


def fallback_model(elo_full: dict[str, float]) -> DixonColesModel:
    """Zero-data / no-fit fallback: the Elo-prior Dixon-Coles."""
    return DixonColesModel.from_elo(elo_full)
