# FEATURES.md

Every feature is computed **as-of pre-kickoff** — no information from the match being
predicted (or any later match) may enter its inputs. The automated leakage guard is the
`as_of` Elo test (`tests/test_ingest.py::test_elo_as_of_excludes_future_matches_no_leakage`)
plus the walk-forward backtest, which refits using only data dated strictly before each test
match.

Legend — **Tier**: 0 = free/no-key (default), 1 = free API, 2 = paid. **Status**: ✅ live,
🟡 scaffolded/flagged, ⛔ not yet wired.

## Strength

| Feature | Source / Tier | Status | Leakage check |
|---|---|---|---|
| Elo rating (as-of) | Derived from historical results (Tier 0) | ✅ | `compute_elo(..., as_of=date)` replays only prior matches |
| Elo trend / delta | Derived (Tier 0) | 🟡 | as-of replay; trailing window ends before kickoff |
| Model-fitted attack rating | Dixon-Coles MLE on prior window (Tier 0) | ✅ | fit window filtered to `date < cutoff` |
| Model-fitted defense rating | Dixon-Coles MLE (Tier 0) | ✅ | same |
| FIFA rank | Seed prior (Tier 0); live series ⛔ | 🟡 | cold-start prior only; no future data |

## Form / momentum

| Feature | Source / Tier | Status | Leakage check |
|---|---|---|---|
| Time-decayed results | Historical results (Tier 0) | ✅ | exponential decay over matches before kickoff; half-life tunable |
| Goals for/against (trailing) | Historical results (Tier 0) | 🟡 | trailing window strictly before kickoff |
| xG for/against (trailing) | FBref/StatsBomb (Tier 1) | ⛔ | as-of window when wired |

## Confederation adjustment

| Feature | Source / Tier | Status | Leakage check |
|---|---|---|---|
| Inter-confederation strength | Cross-confed results in fit (Tier 0) | 🟡 | captured implicitly via opponent attack/defense fit on prior data |

The Dixon-Coles fit estimates each team's strength against its *actual historical opponents*,
which already encodes confederation quality (beating a strong UEFA side raises the estimate
more than beating a weak side). An explicit confederation fixed-effect is a documented next
step.

## Context (match-level; adjusts Dixon-Coles log goal rates)

| Feature | Source / Tier | Status | Leakage check |
|---|---|---|---|
| Home / host advantage | Fixture `neutral` flag + host nation (Tier 0) | ✅ | known before kickoff (schedule) |
| Altitude | Venue altitude, e.g. Mexico City ~2240 m (Tier 0 seed) | ✅ | venue known in advance; acclimatised nations exempt |
| Travel distance | Venue lat/lon haversine (Tier 0 seed) | 🟡 | `haversine_km` available; schedule-derived |
| Rest days between matches | Fixture dates (Tier 0) | 🟡 | schedule-derived, pre-known |
| Neutrality | Fixture flag (Tier 0) | ✅ | schedule-derived |

Implemented in `wc2026/features/context.py`; injected via `MatchContext.home_logit_adj` /
`away_logit_adj` so the model stays decoupled from feature provenance.

## "Mindset" → measurable proxies (NO vague vibes)

| Proxy | Source / Tier | Status | Leakage check |
|---|---|---|---|
| Squad cohesion (shared caps, same-league %) | Squad lists (Tier 2) | ⛔ | computed at squad announcement (pre-tournament) |
| Manager tenure / tactical profile | Tier 2 | ⛔ | pre-tournament snapshot |
| Pressure record (knockouts, shootouts) | Historical results (Tier 0) | 🟡 | only matches before kickoff |
| Squad talent density (median market value, age curve) | Transfermarkt (Tier 2) | ⛔ | squad-announcement snapshot |
| Availability (injuries/suspensions) | API-Football (Tier 2) | ⛔ | as-of squad announcement |

All Tier-2 proxies are strictly additive and absent in the default build. They are listed so
the design is explicit about *measurable* proxies rather than unquantified "vibes".

## Leakage policy

1. Features may read only data with `date < kickoff`.
2. Elo and model fits are recomputed **as-of** each cutoff in the backtest.
3. The simulation samples from predicted distributions only — no realised group result feeds
   another match in the same simulated tournament beyond the standings it legitimately
   produces.
