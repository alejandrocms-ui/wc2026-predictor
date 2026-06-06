"""Generate MODEL_REPORT.md from a walk-forward backtest.

Usage:
    python scripts/run_backtest.py [--start 2021-06-01] [--end 2024-12-31]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wc2026.backtest import evaluate_holdout, run_backtest, write_model_report
from wc2026.config import get_settings
from wc2026.ingest.historical import HistoricalResultsAdapter


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2021-06-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--no-holdout", action="store_true",
                   help="skip the ensemble holdout (faster; walk-forward only)")
    args = p.parse_args()

    s = get_settings()
    adapter = HistoricalResultsAdapter(s.cache_dir, s.seed_dir, offline=args.offline)
    results = adapter.load().data
    print(f"[backtest] {len(results)} historical matches loaded")

    print("[backtest] walk-forward Dixon-Coles vs Elo-only…")
    report = run_backtest(results, test_start=args.start, test_end=args.end)
    report.per_match.to_parquet(s.cache_dir / "backtest_per_match.parquet", index=False)

    holdout = None
    if not args.no_holdout:
        print("[backtest] 3-way holdout (Elo vs Dixon-Coles vs calibrated ensemble)…")
        holdout = evaluate_holdout(results, test_start="2023-06-01", test_end=args.end)

    out = Path(__file__).resolve().parent.parent / "MODEL_REPORT.md"
    write_model_report(report, str(out), holdout=holdout)

    m = report.metrics
    print(f"[backtest] walk-forward scored {report.n_matches} matches")
    print(f"  Dixon-Coles  RPS={m['dixon_coles']['rps']:.4f}")
    print(f"  Elo-only     RPS={m['elo_only']['rps']:.4f}")
    print(f"  DC beats Elo on RPS: {report.beats_baseline()}")
    if holdout:
        hm = holdout.metrics
        print(f"[backtest] holdout ({holdout.n_test} test matches):")
        for k in ("elo_only", "dixon_coles", "calibrated_ensemble"):
            print(f"  {k:20s} RPS={hm[k]['rps']:.4f}  ECE={holdout.ece[k]:.4f}")
    print(f"[backtest] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
