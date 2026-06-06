"""DuckDB persistence for the canonical schema (with Parquet snapshots).

Tables: ``matches``, ``ratings``, ``fixtures_2026``, ``predictions``, ``simulations``,
``provenance``. The store is the durable layer between ingest/modelling and the app, so the
Streamlit UI reads precomputed predictions instantly and the whole app works offline after
one ``pipeline`` run.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .domain import TournamentSpec
from .sim.monte_carlo import SimulationResult


class WC2026Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    # ── writes ──────────────────────────────────────────────────────────────
    def save_matches(self, df: pd.DataFrame) -> None:
        with self._conn() as con:
            con.execute("CREATE OR REPLACE TABLE matches AS SELECT * FROM df")

    def save_ratings(self, ratings: dict[str, float], as_of: str, kind: str = "elo") -> None:
        rows = pd.DataFrame(
            {"team": list(ratings), "value": list(ratings.values())}
        )
        rows["kind"] = kind
        rows["as_of"] = as_of
        with self._conn() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS ratings (team VARCHAR, value DOUBLE, kind VARCHAR, as_of VARCHAR)"
            )
            con.execute("DELETE FROM ratings WHERE kind = ?", [kind])
            con.execute("INSERT INTO ratings SELECT team, value, kind, as_of FROM rows")

    def save_fixtures(self, spec: TournamentSpec) -> None:
        df = pd.DataFrame(  # noqa: F841 — read by DuckDB via `SELECT * FROM df`
            [
                {
                    "match_id": f.match_id,
                    "group": f.group,
                    "matchday": f.matchday,
                    "home": f.home,
                    "away": f.away,
                    "date": f.date,
                    "venue_city": f.venue_city,
                    "neutral": f.neutral,
                }
                for f in spec.fixtures
            ]
        )
        with self._conn() as con:
            con.execute("CREATE OR REPLACE TABLE fixtures_2026 AS SELECT * FROM df")

    def save_predictions(self, df: pd.DataFrame) -> None:
        with self._conn() as con:
            con.execute("CREATE OR REPLACE TABLE predictions AS SELECT * FROM df")

    def save_simulation(self, result: SimulationResult) -> None:
        df = pd.DataFrame(
            [
                {
                    "team": t.team,
                    "group": t.group,
                    "p_win_group": t.p_win_group,
                    "p_runner_up": t.p_runner_up,
                    "p_top2": t.p_top2,
                    "p_best_third": t.p_best_third,
                    "p_reach_r32": t.p_reach_r32,
                    "exp_points": t.exp_points,
                    "exp_gd": t.exp_gd,
                    "exp_gf": t.exp_gf,
                    "p_finish_1": t.finish_dist[0],
                    "p_finish_2": t.finish_dist[1],
                    "p_finish_3": t.finish_dist[2],
                    "p_finish_4": t.finish_dist[3],
                }
                for t in result.teams.values()
            ]
        )
        df["n_sims"] = result.n_sims
        df["seed"] = result.seed
        with self._conn() as con:
            con.execute("CREATE OR REPLACE TABLE simulations AS SELECT * FROM df")

    def save_provenance(self, rows: list[dict]) -> None:
        if not rows:
            return
        df = pd.DataFrame(rows)  # noqa: F841 — read by DuckDB via `SELECT * FROM df`
        with self._conn() as con:
            con.execute("CREATE OR REPLACE TABLE provenance AS SELECT * FROM df")

    # ── reads ───────────────────────────────────────────────────────────────
    def _read(self, table: str) -> pd.DataFrame:
        with self._conn() as con:
            try:
                return con.execute(f"SELECT * FROM {table}").df()
            except duckdb.CatalogException:
                return pd.DataFrame()

    def load_simulation(self) -> pd.DataFrame:
        return self._read("simulations")

    def load_predictions(self) -> pd.DataFrame:
        return self._read("predictions")

    def load_fixtures(self) -> pd.DataFrame:
        return self._read("fixtures_2026")

    def load_provenance(self) -> pd.DataFrame:
        return self._read("provenance")

    def has_predictions(self) -> bool:
        return not self.load_predictions().empty
