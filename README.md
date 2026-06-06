# wc2026-predictor ⚽

Calibrated probabilistic predictions for the **2026 FIFA World Cup group stage** —
per-match scoreline distributions, 1X2 / BTTS / Over-Under markets, group standings
probabilities, and **qualification-to-Round-of-32** odds via vectorised Monte Carlo.

> **This is a decision-support and analytical tool, not a betting guarantee.** Uncertainty
> is irreducible and surfaced everywhere; predictions are weaker for teams with little
> recent data. See the Methodology / Model card page and `MODEL_REPORT.md`.

Design priority order: **(1) probability calibration & honesty → (2) reproducibility →
(3) clarity/maintainability → (4) UI polish.**

---

## Quickstart (runs with ZERO API keys)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[app]"          # core + Streamlit UI

# Build everything (fetches free data once, then caches; deterministic given the seed):
python -m wc2026.pipeline         # ingest → Elo → fit Dixon-Coles → predict → simulate → persist

# Launch the app (Spanish by default; switch to English in the sidebar):
streamlit run wc2026/app/main.py
```

Fully offline (uses the cached snapshot or the committed seed sample):

```bash
python -m wc2026.pipeline --offline
```

The app reads precomputed predictions from a local DuckDB store, so it loads instantly and
works offline after one pipeline run.

---

## What it produces

- **Per-match**: full `P(home=i, away=j)` scoreline matrix → 1X2, BTTS, Over/Under, most
  likely scores, expected goals. (`wc2026.models`)
- **Per-group**: P(win group), P(top-2), P(best third), P(reach R32), expected points / GD,
  and the full finishing-position distribution. (`wc2026.sim`)
- **Tournament-wide**: sortable dashboard of who tops their group / sneaks in as best third.

Exactly 32 teams reach the Round of 32 (24 top-two + 8 best thirds) — verified by the
simulation accounting tests.

---

## Data tiers (degrade gracefully; the app always runs on Tier-0)

| Tier | Source | Keys | Status |
|---|---|---|---|
| **0** | Historical international results 1872–present (martj42); Elo derived from them; FIFA-rank seed | none | **required, default** |
| 1 | football-data.org free tier / FBref via scrapers (xG, richer stats) | free token | optional, additive |
| 2 | API-Football (lineups, injuries, squads), Transfermarkt (market value) | paid | optional, additive |

Every prediction carries a **data-tier badge** in the UI. Provenance (source + fetch
timestamp + tier) is logged for every ingested dataset (`provenance` table).

> **Note on the "$10 DeepSeek key":** DeepSeek is an LLM, not a football-data source — it
> cannot provide lineups/injuries/market values, so it does **not** feed the statistical
> model. It is wired only as an optional *cosmetic* "explain this prediction" blurb
> (`WC2026_DEEPSEEK_API_KEY`, off by default). The model is pure Tier-0/1.

---

## Architecture

```
wc2026/
  ingest/      source adapters (tier0..2), caching, provenance, derived Elo
  features/    leakage-safe context builders (altitude, host, travel)
  models/      scoreline matrix, dixon_coles (primary), build (fit+coldstart), [gbm/bayesian: flagged]
  sim/         tiebreakers (FIFA), bracket (R32 hook), monte_carlo (vectorised)
  app/         Streamlit pages (i18n: es default)
  i18n/        string tables (es/en)
  engine.py    library surface: spec + model -> matrices -> simulation
  pipeline.py  one-command rebuild
  backtest.py  walk-forward, leakage-safe, RPS vs Elo baseline
data/seed/     committed verified seed (groups, teams, venues, sample results)
tests/         tiebreakers, third-place logic, no-leakage, simulation accounting, calibration sanity
```

### Model — calibrated ensemble

1. **Primary — Dixon-Coles bivariate Poisson** (`models/dixon_coles.py`): team-specific
   attack/defense, home advantage, the DC low-score correlation correction (τ), and
   **exponential time-decay** weighting. Fit by weighted MLE; falls back to an **Elo-derived
   prior** so it predicts with zero data and for cold-start teams.
2. **Tertiary — LightGBM** (`models/gbm.py`): two Poisson regressors on a leakage-safe
   as-of feature matrix (Elo, trailing form/goals, rest days, experience, neutrality →
   `features/match_features.py`), mapped to a Dixon-Coles scoreline.
3. **Ensemble + calibration** (`models/ensemble.py`, `models/train.py`): weights fit by
   **minimising out-of-sample RPS** on a validation split (not hand-picked), then **isotonic
   1X2 calibration** rescales the scoreline regions to the calibrated marginals. This is the
   model the pipeline trains and serves (`data/model.pkl`).
4. **Secondary — Bayesian hierarchical Poisson** (numpyro/pymc): flagged for later
   (`".[bayes]"`) — partial pooling for low-data teams. The Elo cold-start fill is the
   interim stand-in.

**Match context** adds host advantage by *venue country* (a host gets the boost even as the
nominal away team in its own country), altitude suppression for non-acclimatised teams at
high venues (Mexico City ~2,240 m), and rest/travel hooks — all leakage-safe.

### FastAPI / React migration seam

All prediction & simulation logic lives in the importable `wc2026` library; the Streamlit
app (`wc2026/app`) is a thin presentation layer that only calls `engine.run_tournament_simulation`,
`model.predict_match`, and the DuckDB store. A future FastAPI service can import the exact
same functions and serve JSON without touching the modelling code — no rewrite required.

---

## Reproducibility

- Pinned deps (`pyproject.toml` / `requirements.txt`).
- One command rebuilds everything: `python -m wc2026.pipeline`.
- **Deterministic given a seed** (`--seed`, default `20260611`). The only nondeterminism is
  the Monte Carlo draw, fully controlled by the seed.
- Validation: `python scripts/run_backtest.py` regenerates `MODEL_REPORT.md`.

## Configuration

Copy `.env.example` → `.env`. The app runs with everything blank (Tier-0). Keys are strictly
additive. No secrets are ever committed (`.env` is gitignored).

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

Covers: FIFA tiebreaker chain (incl. head-to-head re-application & drawing of lots),
third-place ranking & best-8 selection, round-robin fixture structure, scoreline-market
consistency, Dixon-Coles behaviour & MLE fit, **no-leakage** (`as_of` Elo), and the
**simulation accounting** (exactly 32 advance, 8 thirds, 2 per group).

## Ground-truth verification (confirmed Dec 2025)

- **Groups, the full 72-match fixture list (numbers, dates, venues), the 16 host stadiums,
  and the fixed R32 bracket** are committed as a **verified** seed (`data/seed/`), sourced
  from the official draw and cross-checked (ESPN/Wikipedia/FIFA). `data/seed/fixtures.json`
  is the authoritative schedule; the round-robin generator is only a fallback.
- **2026 tie-breaker order** is implemented correctly: head-to-head (points → GD → GF among
  tied teams) is applied **before** overall goal difference — the rule FIFA changed for 2026
  (first change since 1970). Covered by a dedicated test.
- **Not included / flagged:** exact kickoff times (unverified — only dates/venues are used);
  the final tie-breaker criterion (FIFA ranking vs drawing of lots, abstracted behind
  `lots`); and the full **R32 best-third allocation table** (495 combinations, FIFA Annex C)
  — the fixed pairings + third-place eligibility pools are captured in
  `data/seed/r32_bracket.json`; the full table is only needed for the knockout extension.

## License

MIT (code). Historical-results data is community-sourced; respect each source's ToS.
