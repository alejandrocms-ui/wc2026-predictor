"""Walk-forward backtest: does the fitted Dixon-Coles beat an Elo-only baseline?

Strictly leakage-safe: for each test match we use only data dated *before* kickoff. Elo is
replayed as-of the cutoff; the Dixon-Coles model is refit on a rolling window up to the
cutoff (refit at a coarse cadence for tractability, reused within each period).

Metrics (1X2, outcomes ordered Home > Draw > Away):
  * RPS  — Ranked Probability Score (primary; lower is better, rewards ordinal closeness)
  * Brier — multiclass Brier score
  * LogLoss — negative log-likelihood of the realised outcome

Baselines: the Elo-prior Dixon-Coles (``from_elo``) — i.e. goals implied purely by Elo, no
fit. The contest is therefore "does fitting team-specific attack/defense + decay add value
over the Elo prior?", which is exactly the project's acceptance bar. (A FIFA-rank-only
baseline is left as a documented TODO — no clean free historical FIFA-rank series is wired.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .ingest.elo import compute_elo
from .models.build import build_dixon_coles
from .models.dixon_coles import DixonColesModel

OUTCOMES = ("home", "draw", "away")


def outcome_index(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def rps(probs: np.ndarray, outcome_idx: int) -> float:
    """Ranked Probability Score for one ordered 3-outcome prediction."""
    obs = np.zeros(3)
    obs[outcome_idx] = 1.0
    cp = np.cumsum(probs)
    co = np.cumsum(obs)
    return float(np.sum((cp - co) ** 2) / (len(probs) - 1))


def brier(probs: np.ndarray, outcome_idx: int) -> float:
    obs = np.zeros(3)
    obs[outcome_idx] = 1.0
    return float(np.sum((probs - obs) ** 2))


def log_loss(probs: np.ndarray, outcome_idx: int, eps: float = 1e-12) -> float:
    return float(-np.log(max(probs[outcome_idx], eps)))


def _one_x_two(model: DixonColesModel, home: str, away: str, neutral: bool) -> np.ndarray:
    from .domain import MatchContext

    sm = model.predict_match(home, away, MatchContext(neutral=neutral))
    return np.array(sm.one_x_two)


@dataclass(slots=True)
class BacktestReport:
    n_matches: int
    test_start: str
    test_end: str
    metrics: dict[str, dict[str, float]]  # model -> {rps, brier, logloss}
    per_match: pd.DataFrame

    def beats_baseline(self) -> bool:
        return self.metrics["dixon_coles"]["rps"] < self.metrics["elo_only"]["rps"]


def run_backtest(
    results: pd.DataFrame,
    *,
    test_start: str = "2021-06-01",
    test_end: str = "2024-12-31",
    refit_freq: str = "QS",  # quarterly refit cadence
    fit_years: int = 10,
    halflife_days: float = 547.0,
    min_train: int = 2000,
) -> BacktestReport:
    df = results.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    ts, te = pd.Timestamp(test_start), pd.Timestamp(test_end)
    test = df[(df["date"] >= ts) & (df["date"] <= te)].copy()
    if test.empty:
        raise ValueError("no test matches in the requested window")

    # Refit period boundaries.
    periods = pd.date_range(ts, te, freq=refit_freq)
    if len(periods) == 0 or periods[0] > ts:
        periods = pd.DatetimeIndex([ts]).append(periods)

    rows = []
    for k, p_start in enumerate(periods):
        p_end = periods[k + 1] if k + 1 < len(periods) else te + pd.Timedelta(days=1)
        chunk = test[(test["date"] >= p_start) & (test["date"] < p_end)]
        if chunk.empty:
            continue
        train = df[df["date"] < p_start]
        if len(train) < min_train:
            continue

        # Leakage-safe as-of inputs.
        elo = compute_elo(train)
        elo_model = DixonColesModel.from_elo(elo)
        dc_model = build_dixon_coles(
            train, elo, fit_years=fit_years, halflife_days=halflife_days
        )

        for r in chunk.itertuples(index=False):
            neutral = bool(getattr(r, "neutral", False))
            oi = outcome_index(int(r.home_score), int(r.away_score))
            p_dc = _one_x_two(dc_model, r.home, r.away, neutral)
            p_elo = _one_x_two(elo_model, r.home, r.away, neutral)
            rows.append(
                {
                    "date": r.date,
                    "home": r.home,
                    "away": r.away,
                    "outcome": OUTCOMES[oi],
                    "rps_dc": rps(p_dc, oi),
                    "rps_elo": rps(p_elo, oi),
                    "brier_dc": brier(p_dc, oi),
                    "brier_elo": brier(p_elo, oi),
                    "ll_dc": log_loss(p_dc, oi),
                    "ll_elo": log_loss(p_elo, oi),
                }
            )

    per_match = pd.DataFrame(rows)
    metrics = {
        "dixon_coles": {
            "rps": float(per_match["rps_dc"].mean()),
            "brier": float(per_match["brier_dc"].mean()),
            "logloss": float(per_match["ll_dc"].mean()),
        },
        "elo_only": {
            "rps": float(per_match["rps_elo"].mean()),
            "brier": float(per_match["brier_elo"].mean()),
            "logloss": float(per_match["ll_elo"].mean()),
        },
    }
    return BacktestReport(
        n_matches=len(per_match),
        test_start=test_start,
        test_end=test_end,
        metrics=metrics,
        per_match=per_match,
    )


@dataclass(slots=True)
class HoldoutReport:
    n_train: int
    n_val: int
    n_test: int
    test_window: tuple[str, str]
    metrics: dict[str, dict[str, float]]  # model -> {rps, brier, logloss}
    ece: dict[str, float]  # model -> expected calibration error on P(home win)
    reliability_home: dict[str, list]  # model -> {mean_pred, emp_rate, counts}


def evaluate_holdout(
    results: pd.DataFrame,
    *,
    val_start: str = "2022-01-01",
    test_start: str = "2023-06-01",
    test_end: str = "2024-12-31",
    fit_years: int = 10,
    halflife_days: float = 547.0,
) -> HoldoutReport:
    """Clean 3-way temporal split: members fit on TRAIN (<val_start), ensemble weights +
    calibrators on VAL ([val_start, test_start)), everything evaluated on TEST
    (>=test_start). Fully out-of-sample — no leakage into TEST.

    Compares Elo-only, fitted Dixon-Coles, and the calibrated ensemble, with reliability
    on P(home win). Requires the ML extra for the ensemble member; if absent, the ensemble
    columns mirror Dixon-Coles.
    """
    from .domain import MatchContext
    from .ingest.elo import compute_elo
    from .models.calibration import reliability_table
    from .models.dixon_coles import DixonColesModel
    from .models.train import TrainConfig, train_calibrated_ensemble

    df = results.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    ts, te = pd.Timestamp(test_start), pd.Timestamp(test_end)
    pre_test = df[df["date"] < ts]
    test = df[(df["date"] >= ts) & (df["date"] <= te)]
    if test.empty:
        raise ValueError("no test matches in window")

    elo_pre = compute_elo(pre_test)
    elo_model = DixonColesModel.from_elo(elo_pre)
    ensemble = train_calibrated_ensemble(
        pre_test, elo_pre,
        config=TrainConfig(cutoff=val_start, fit_years=fit_years, halflife_days=halflife_days),
    )
    dc_model = ensemble.ensemble.members[0]  # the refit Dixon-Coles member

    models = {"elo_only": elo_model, "dixon_coles": dc_model, "calibrated_ensemble": ensemble}
    metrics: dict[str, dict[str, float]] = {}
    ece: dict[str, float] = {}
    reliability_home: dict[str, list] = {}

    outcomes = np.array(
        [outcome_index(int(r.home_score), int(r.away_score)) for r in test.itertuples(index=False)]
    )
    home_won = (outcomes == 0).astype(float)

    for name, model in models.items():
        probs = np.array(
            [
                model.predict_match(
                    r.home, r.away,
                    MatchContext(neutral=bool(getattr(r, "neutral", False))),
                ).one_x_two
                for r in test.itertuples(index=False)
            ]
        )
        metrics[name] = {
            "rps": float(np.mean([rps(p, o) for p, o in zip(probs, outcomes, strict=False)])),
            "brier": float(np.mean([brier(p, o) for p, o in zip(probs, outcomes, strict=False)])),
            "logloss": float(np.mean([log_loss(p, o) for p, o in zip(probs, outcomes, strict=False)])),
        }
        rt = reliability_table(probs[:, 0], home_won, n_bins=10)
        ece[name] = rt.ece
        reliability_home[name] = [
            [float(x) for x in rt.mean_predicted],
            [float(x) for x in rt.empirical_rate],
            [int(x) for x in rt.counts],
        ]

    return HoldoutReport(
        n_train=int((df["date"] < pd.Timestamp(val_start)).sum()),
        n_val=int(((df["date"] >= pd.Timestamp(val_start)) & (df["date"] < ts)).sum()),
        n_test=len(test),
        test_window=(test_start, test_end),
        metrics=metrics,
        ece=ece,
        reliability_home=reliability_home,
    )


def write_model_report(
    report: BacktestReport, path: str, holdout: HoldoutReport | None = None
) -> None:
    """Render MODEL_REPORT.md from a backtest report."""
    m = report.metrics
    dc, elo = m["dixon_coles"], m["elo_only"]
    verdict = (
        "✅ **The fitted Dixon-Coles beats the Elo-only baseline on RPS.**"
        if report.beats_baseline()
        else "⚠️ **The fitted model does NOT beat Elo-only on RPS in this window** — see notes."
    )
    rps_impr = (elo["rps"] - dc["rps"]) / elo["rps"] * 100

    lines = [
        "# MODEL_REPORT.md",
        "",
        "Auto-generated by `wc2026.backtest`. Walk-forward, leakage-safe (each match scored "
        "with data strictly before kickoff; Elo replayed as-of, Dixon-Coles refit quarterly).",
        "",
        f"- **Test window:** {report.test_start} → {report.test_end}",
        f"- **Matches scored:** {report.n_matches:,}",
        "- **Outcome space:** 1X2, ordered Home > Draw > Away",
        "",
        "## Headline",
        "",
        verdict,
        "",
        f"RPS improvement over Elo-only: **{rps_impr:+.2f}%**.",
        "",
        "## Metrics (lower is better)",
        "",
        "| Model | RPS | Brier | LogLoss |",
        "|---|---|---|---|",
        f"| Dixon-Coles (fitted) | {dc['rps']:.4f} | {dc['brier']:.4f} | {dc['logloss']:.4f} |",
        f"| Elo-only (prior)     | {elo['rps']:.4f} | {elo['brier']:.4f} | {elo['logloss']:.4f} |",
        "",
        "## Notes & limitations",
        "",
        "- **RPS** is the primary metric (ordinal, rewards being close on the Home–Draw–Away "
        "ladder). Brier and LogLoss are reported for completeness.",
        "- The Elo-only baseline is itself strong (it encodes decades of results), so margins "
        "are typically small; the value of the fit is mainly sharper goal/score-line markets "
        "(BTTS, O/U, exact score) and team-specific attack/defense, not just 1X2.",
        "- **FIFA-rank-only** and **bookmaker-implied** baselines are not yet wired (no clean "
        "free historical series); they are documented TODOs.",
        "- Predictions are weaker for low-data teams; the Elo cold-start fill (a stand-in for "
        "the flagged-for-later Bayesian partial-pooling model) mitigates but does not "
        "eliminate this.",
        "- Calibration: post-hoc isotonic calibration on 1X2 is applied in the calibrated "
        "ensemble (see the holdout section below); ECE quantifies the improvement.",
        "",
    ]

    if holdout is not None:
        hm = holdout.metrics
        order = ["elo_only", "dixon_coles", "calibrated_ensemble"]
        names = {
            "elo_only": "Elo-only (prior)",
            "dixon_coles": "Dixon-Coles (fitted)",
            "calibrated_ensemble": "Calibrated ensemble (DC + LightGBM)",
        }
        lines += [
            "## Out-of-sample holdout — calibrated ensemble vs members",
            "",
            "A clean 3-way temporal split (no leakage into TEST): members fit on TRAIN, "
            "ensemble weights + isotonic calibrators fit on VAL, all scored on TEST.",
            "",
            f"- **Split sizes:** train={holdout.n_train:,} · val={holdout.n_val:,} · "
            f"test={holdout.n_test:,}",
            f"- **Test window:** {holdout.test_window[0]} → {holdout.test_window[1]}",
            "",
            "| Model | RPS | Brier | LogLoss | ECE (P home win) |",
            "|---|---|---|---|---|",
        ]
        for k in order:
            m = hm[k]
            lines.append(
                f"| {names[k]} | {m['rps']:.4f} | {m['brier']:.4f} | {m['logloss']:.4f} "
                f"| {holdout.ece[k]:.4f} |"
            )
        best = min(order, key=lambda k: hm[k]["rps"])
        lines += [
            "",
            f"Best RPS on the holdout: **{names[best]}**. Lower ECE = better calibrated "
            "1X2 (the isotonic step targets exactly this).",
            "",
            "### Reliability (P home win), calibrated ensemble",
            "",
            "| Bin mean predicted | Empirical rate | N |",
            "|---|---|---|",
        ]
        mp, er, ct = holdout.reliability_home["calibrated_ensemble"]
        for p, e, n in zip(mp, er, ct, strict=False):
            if n > 0 and not np.isnan(p):  # skip empty / NaN bins
                lines.append(f"| {p:.3f} | {e:.3f} | {n} |")
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
