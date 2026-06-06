# LAUNCH.md — running & deploying wc2026-predictor

A step-by-step guide from a fresh clone to a live app, plus a pre-launch checklist and how
to refresh data right before kickoff. Everything works with **zero API keys**.

---

## 0. One-time setup (≈3 min)

```bash
cd wc2026-predictor
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[app,ml]"           # core + Streamlit UI + LightGBM ensemble
```

> Python **3.11+** required (tested on 3.14). The `ml` extra adds LightGBM + scikit-learn for
> the tertiary model, ensemble, and calibration. Omit it (`pip install -e ".[app]"`) for a
> lighter Dixon-Coles-only install — the app still runs.

---

## 1. Build the predictions (one command)

```bash
python -m wc2026.pipeline                 # fetches free data once, caches, then builds
```

What it does, in order: loads the verified tournament structure → fetches the open
historical-results dataset (≈49k matches, cached to Parquet) → derives Elo → trains the
calibrated ensemble (Dixon-Coles + LightGBM, weights chosen by validation RPS, isotonic 1X2
calibration) → predicts all 72 fixtures → runs 50,000 Monte Carlo tournaments → writes
everything to `data/wc2026.duckdb` and saves the model to `data/model.pkl`.

Runtime ≈ 30–40 s. Useful flags:

```bash
python -m wc2026.pipeline --offline       # no network: use cached snapshot / committed seed
python -m wc2026.pipeline --no-ensemble    # Dixon-Coles only (fast, ~10s)
python -m wc2026.pipeline --n-sims 100000 --seed 7
```

It is **deterministic** given `--seed`.

## 2. (Optional) Regenerate the model report

```bash
python scripts/run_backtest.py            # walk-forward RPS vs Elo + 3-way calibrated holdout
```

Writes `MODEL_REPORT.md` (RPS / Brier / LogLoss / ECE + reliability). Takes a few minutes.

## 3. Launch the app

```bash
streamlit run wc2026/app/main.py
```

Opens at <http://localhost:8501>. Spanish by default; switch to English in the sidebar.
Pages: **Match predictor**, **Group explorer**, **Tournament dashboard**, **Methodology /
model card**.

---

## Pre-launch checklist

- [ ] `pytest -q` is green (run `pip install -e ".[dev]"` first).
- [ ] `python -m wc2026.pipeline` completes and prints a sensible "most likely to reach R32".
- [ ] App loads all four pages with no errors; the data-tier badge shows 🟢 Tier 0.
- [ ] `MODEL_REPORT.md` shows the model beating the Elo-only baseline on RPS.
- [ ] Re-verify the seed against official FIFA before going public (see "Accuracy" below).
- [ ] Confirm the responsible-use / not-betting disclaimer is visible (it is, on every page).

## Accuracy / data-freshness before the tournament

- **Groups, fixtures, venues, R32 bracket** are committed as a *verified* seed
  (`data/seed/*.json`, confirmed Dec 2025). Re-check against fifa.com if anything changed.
- **Refresh form right before kickoff** so injuries-of-form and recent results are included:
  ```bash
  python -m wc2026.pipeline --refresh        # re-fetch the latest historical results
  ```
- **Tie-breakers**: 2026 uses head-to-head BEFORE overall goal difference (implemented).
  The exact final criterion (FIFA ranking vs drawing of lots) is abstracted; verify vs the
  FIFA regulations PDF if a knife-edge group matters to you.
- **Kickoff times** are intentionally omitted from the fixture seed (unverified); only dates
  and venues are used (for rest-day and altitude features).

---

## Deploy option A — Streamlit Community Cloud (free)

1. Push the repo to GitHub (the `.gitignore` keeps secrets and heavy data out).
2. Commit a built store so the cloud app has data without running the pipeline there, **or**
   add a small startup step. Simplest: commit `data/wc2026.duckdb` and `data/model.pkl`
   (a few MB) by force-adding them:
   ```bash
   git add -f data/wc2026.duckdb data/model.pkl
   ```
   (They are gitignored by default; force-add only if you want the cloud app pre-built.)
3. On <https://share.streamlit.io>, point at `wc2026/app/main.py`.
4. `requirements.txt` and the committed `packages.txt` (system `libgomp1` for LightGBM) are
   picked up automatically. Set `WC2026_LANG`, `WC2026_N_SIMULATIONS`, etc. as app secrets if
   you want to override defaults.

## Deploy option B — Docker / VPS

```bash
docker build -t wc2026 .
docker run -p 8501:8501 wc2026            # pipeline runs at build time; app serves on :8501
```

The `Dockerfile` installs deps, runs `python -m wc2026.pipeline` during the build so the
image ships with predictions, and launches Streamlit. Mount a volume at `/app/data` to
persist/refresh the store across runs.

## Deploy option C — keep it local

Nothing more to do — `streamlit run wc2026/app/main.py` after the pipeline is the whole app.

---

## Enriching with optional data (additive, never required)

Copy `.env.example` → `.env` and fill any of:
- `WC2026_FOOTBALL_DATA_TOKEN` (free) — Tier-1 richer stats when wired.
- `WC2026_API_FOOTBALL_KEY` (paid) — Tier-2 lineups/injuries/squads.
- `WC2026_DEEPSEEK_API_KEY` — optional cosmetic "explain this prediction" text only; it does
  **not** feed the statistical model.

The app always degrades gracefully to Tier-0 and badges which tier produced each prediction.
