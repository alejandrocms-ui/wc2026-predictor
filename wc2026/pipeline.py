"""One-command rebuild: ingest → ratings → fit model → predict → simulate → persist.

Run with::

    python -m wc2026.pipeline            # full Tier-0 build (fetches once, then cached)
    python -m wc2026.pipeline --offline  # use cached/seed data only
    python -m wc2026.pipeline --n-sims 100000 --seed 7

Everything is deterministic given ``--seed``. Outputs land in the DuckDB store and are read
instantly by the Streamlit app.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import asdict

from .config import get_settings
from .engine import build_fixture_matrices
from .ingest.elo import EloRatingsAdapter
from .ingest.historical import HistoricalResultsAdapter
from .models.build import build_dixon_coles
from .predictions import predictions_frame
from .sim.monte_carlo import simulate
from .store import WC2026Store
from .tournament import load_spec


def run_pipeline(
    *,
    n_sims: int | None = None,
    seed: int | None = None,
    offline: bool | None = None,
    refresh: bool = False,
    fit: bool = True,
    ensemble: bool = True,
) -> None:
    settings = get_settings()
    settings.ensure_dirs()
    n_sims = n_sims or settings.n_simulations
    seed = seed if seed is not None else settings.random_seed
    offline = settings.offline if offline is None else offline

    log = lambda m: print(f"[pipeline] {m}", flush=True)  # noqa: E731
    t0 = time.time()
    provenance_rows: list[dict] = []

    # 1) Tournament structure (verified seed; offline-safe).
    spec = load_spec(settings)
    log(f"loaded spec: {len(spec.teams)} teams, {len(spec.groups)} groups, "
        f"{len(spec.fixtures)} fixtures")

    store = WC2026Store(settings.duckdb_path)
    store.save_fixtures(spec)

    # 2) Tier-0 ingest: historical results.
    hist = HistoricalResultsAdapter(settings.cache_dir, settings.seed_dir, offline=offline)
    hr = hist.load(force_refresh=refresh)
    results = hr.data
    log(f"results: {len(results)} matches [{hr.provenance.tier}] {hr.provenance.note}")
    provenance_rows.append(asdict(hr.provenance))
    store.save_matches(results)

    # 3) Tier-0 Elo (derived from results).
    elo_adapter = EloRatingsAdapter(settings.cache_dir, offline=offline)
    er = elo_adapter.load(results, seed_ratings=None)
    elo = er.data
    # Ensure every 2026 team has a rating (fall back to seed Elo for any absentee).
    for name, t in spec.teams.items():
        elo.setdefault(name, t.elo_seed)
    log(f"elo computed for {len(elo)} teams [{er.provenance.tier}]")
    provenance_rows.append(asdict(er.provenance))
    store.save_ratings(elo, as_of=er.provenance.fetched_at, kind="elo")

    # 4) Build the predictive model.
    teams_of_interest = list(spec.teams)
    model_desc = "elo-prior dixon-coles"
    if fit and not results.empty and ensemble:
        log("training calibrated ensemble (Dixon-Coles + LightGBM, weights by val RPS)…")
        from .models.train import TrainConfig, train_calibrated_ensemble

        cfg = TrainConfig(halflife_days=settings.decay_halflife_days, verbose=True)
        model = train_calibrated_ensemble(
            results, elo, config=cfg, teams_of_interest=teams_of_interest
        )
        w = ", ".join(f"{x:.3f}" for x in model.weights)
        model_desc = f"calibrated ensemble (weights=[{w}], calibrated={bool(model.calibrators)})"
    elif fit and not results.empty:
        log("fitting Dixon-Coles (time-decay weighted MLE)…")
        model = build_dixon_coles(
            results, elo, halflife_days=settings.decay_halflife_days,
            teams_of_interest=teams_of_interest,
        )
        model_desc = "fitted dixon-coles"
    else:
        from .models.dixon_coles import DixonColesModel

        log("using Elo-prior Dixon-Coles (no fit)")
        model = DixonColesModel.from_elo(elo)
    log(f"model: {model_desc}")
    provenance_rows.append(
        {"source": f"model: {model_desc}", "url": None, "tier": "model",
         "fetched_at": er.provenance.fetched_at, "note": model_desc}
    )

    # 5) Persist the trained model so the app serves the exact same predictions.
    try:
        import joblib

        model_path = settings.data_dir / "model.pkl"
        joblib.dump(model, model_path)
        log(f"saved model → {model_path}")
    except Exception as exc:  # pragma: no cover - non-fatal
        log(f"model persist skipped ({exc!r})")

    # 6) Predict every fixture → markets table.
    matrices = build_fixture_matrices(spec, model, data_tier=hr.provenance.tier)
    preds = predictions_frame(spec, matrices)
    store.save_predictions(preds)
    log(f"predictions: {len(preds)} fixtures")

    # 6) Monte Carlo simulation.
    log(f"simulating {n_sims:,} tournaments (seed={seed})…")
    result = simulate(spec, matrices, n_sims=n_sims, seed=seed)
    store.save_simulation(result)

    # 7) Provenance.
    store.save_provenance(provenance_rows)

    log(f"done in {time.time() - t0:.1f}s → {settings.duckdb_path}")
    _print_top(result)


def _print_top(result) -> None:
    rows = sorted(result.teams.values(), key=lambda r: -r.p_reach_r32)[:8]
    print("\nMost likely to reach Round of 32:")
    for r in rows:
        print(f"  {r.team:24s} grp {r.group}  R32 {r.p_reach_r32*100:5.1f}%  "
              f"win-grp {r.p_win_group*100:5.1f}%  xpts {r.exp_points:.2f}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rebuild wc2026 predictions end-to-end.")
    p.add_argument("--n-sims", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true", help="force re-fetch of remote data")
    p.add_argument("--no-fit", action="store_true", help="skip MLE; use Elo-prior model")
    p.add_argument("--no-ensemble", action="store_true",
                   help="use Dixon-Coles only (skip LightGBM + calibration)")
    args = p.parse_args(argv)
    run_pipeline(
        n_sims=args.n_sims,
        seed=args.seed,
        offline=args.offline or None,
        refresh=args.refresh,
        fit=not args.no_fit,
        ensemble=not args.no_ensemble,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
